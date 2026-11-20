"""Context-aware policies shared by the direct RAG and managed Agent runtimes."""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from threading import Lock
from typing import Any

from rag_chat.application.guardrails.privacy import (
    protect_source,
    protect_text,
    validate_untrusted,
)
from rag_chat.domain.errors import (
    ConfigurationError,
    GuardrailRule,
    GuardrailViolation,
    RagTimeoutError,
)
from rag_chat.domain.models import ChatMessage, SourceDocument, TokenUsage

ABSTENTION = "The available sources do not contain enough evidence to answer this question."
GREETING = "Hello! Ask a question about an approved policy, process, or document."
_GREETINGS = {"hola", "hello", "hi", "hey", "buenos días", "buenas tardes", "gracias", "thanks"}


@dataclass(frozen=True, slots=True)
class GuardrailSettings:
    max_context_bytes: int = 48_000
    requests_per_window: int = 10
    rate_window_seconds: float = 60.0
    token_quota: int = 524_288
    quota_window_seconds: float = 3_600.0
    token_reservation: int = 65_536
    deadline_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ConfigurationError(f"Guardrail setting {name} must be positive and finite.")
            integer_fields = {
                "max_context_bytes",
                "requests_per_window",
                "token_quota",
                "token_reservation",
            }
            if name in integer_fields and type(value) is not int:
                raise ConfigurationError(f"Guardrail setting {name} must be an integer.")
        if self.token_reservation > self.token_quota:
            raise ConfigurationError("The token reservation cannot exceed the token quota.")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> GuardrailSettings:
        environment = os.environ if environ is None else environ
        defaults = cls()
        values: dict[str, Any] = {}
        for name in cls.__dataclass_fields__:
            raw = environment.get(f"RAG_GUARDRAIL_{name.upper()}")
            if raw is not None:
                try:
                    values[name] = (
                        float(raw) if isinstance(getattr(defaults, name), float) else int(raw)
                    )
                except ValueError as error:
                    raise ConfigurationError(f"Invalid guardrail setting {name}.") from error
        return replace(defaults, **values)


@dataclass
class _Account:
    opened: float
    calls: deque[float] = field(default_factory=deque)
    tokens: int = 0
    active: int = 0
    expires: float = 0.0


class UsageTicket:
    def __init__(self, ledger: UsageLedger, account: _Account, reserved: int) -> None:
        self._ledger = ledger
        self._account = account
        self._reserved = reserved
        self._settled = False

    def finish(self, usage: TokenUsage | None = None) -> None:
        # On failure or unknown usage keep the reservation: absence is not zero.
        with self._ledger.lock:
            if self._settled:
                return
            self._settled = True
            if usage is not None:
                self._account.tokens += max(0, usage.total_tokens) - self._reserved
            self._account.active -= 1


class UsageLedger:
    """Atomic, bounded process-local accounting; never evict an active quota window."""

    def __init__(self, *, max_subjects: int = 4096) -> None:
        self.lock = Lock()
        self._accounts: dict[str, _Account] = {}
        self._max_subjects = max_subjects

    def reserve(self, subject: str, settings: GuardrailSettings, now: float) -> UsageTicket:
        key = hashlib.sha256(subject.encode()).hexdigest()
        with self.lock:
            expired = [
                key
                for key, account in self._accounts.items()
                if not account.active and now >= account.expires
            ]
            for stale in expired:
                del self._accounts[stale]
            if key not in self._accounts:
                if len(self._accounts) >= self._max_subjects:
                    raise GuardrailViolation(
                        "Request capacity reached. Retry later.", rule=GuardrailRule.RATE_LIMIT
                    )
                self._accounts[key] = _Account(now)
            account = self._accounts[key]
            while account.calls and now - account.calls[0] >= settings.rate_window_seconds:
                account.calls.popleft()
            if len(account.calls) >= settings.requests_per_window:
                raise GuardrailViolation(
                    "Request rate limit reached. Retry later.", rule=GuardrailRule.RATE_LIMIT
                )
            if account.tokens + settings.token_reservation > settings.token_quota:
                raise GuardrailViolation(
                    "The user's token quota is exhausted. Retry later.",
                    rule=GuardrailRule.TOKEN_QUOTA,
                )
            account.calls.append(now)
            account.tokens += settings.token_reservation
            account.active += 1
            account.expires = max(
                account.expires,
                account.opened + settings.quota_window_seconds,
                now + settings.rate_window_seconds,
            )
            return UsageTicket(self, account, settings.token_reservation)


PROCESS_LEDGER = UsageLedger()


@dataclass(frozen=True, slots=True)
class RequestDeadline:
    expires: float
    clock: Callable[[], float]

    def remaining(self) -> float:
        seconds = self.expires - self.clock()
        if seconds <= 0:
            raise RagTimeoutError("The request exceeded its total deadline. Please retry.")
        return seconds


class RuntimeGuardrails:
    def __init__(
        self,
        *,
        settings: GuardrailSettings | None = None,
        ledger: UsageLedger = PROCESS_LEDGER,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or GuardrailSettings()
        self.ledger = ledger
        self.clock = clock

    def deadline(self) -> RequestDeadline:
        return RequestDeadline(self.clock() + self.settings.deadline_seconds, self.clock)

    def prepare(
        self, question: str, history: Sequence[ChatMessage]
    ) -> tuple[str, tuple[ChatMessage, ...]]:
        self.check_context(question + "\n" + "\n".join(item.content for item in history))
        safe_question = protect_text(question)
        validate_untrusted(safe_question)
        messages = []
        for message in history:
            if message.role not in {"user", "assistant"}:
                raise GuardrailViolation(
                    "Unsupported conversation role.", rule=GuardrailRule.INJECTION
                )
            content = protect_text(message.content)
            validate_untrusted(content)
            messages.append(ChatMessage(message.role, content))
        self.check_context(safe_question + "\n" + "\n".join(item.content for item in messages))
        return safe_question, tuple(messages)

    def sources(self, sources: Sequence[SourceDocument]) -> tuple[SourceDocument, ...]:
        self.check_context(
            "\n".join(
                f"{source.document_id}\n{source.title}\n{source.content}\n{source.uri or ''}"
                for source in sources
            )
        )
        result = []
        for source in sources:
            protected = protect_source(source)
            validate_untrusted(protected.content + "\n" + protected.title)
            result.append(protected)
        return tuple(result)

    def check_context(self, serialized: str) -> None:
        if len(serialized.encode("utf-8")) > self.settings.max_context_bytes:
            raise GuardrailViolation(
                "The complete context exceeds the safe request budget.",
                rule=GuardrailRule.CONTEXT_LIMIT,
            )

    def reserve(self, subject: str) -> UsageTicket:
        return self.ledger.reserve(subject, self.settings, self.clock())

    def ground(
        self, content: str, sources: tuple[SourceDocument, ...], *, native: bool = False
    ) -> tuple[str, tuple[SourceDocument, ...]]:
        safe_content = protect_text(content)
        safe_sources = self.sources(sources)
        references = set(re.findall(r"\[(\d+)\]", safe_content))
        available = {
            source.citation_label if native else str(index)
            for index, source in enumerate(safe_sources, start=1)
        }
        if references - available:
            raise GuardrailViolation(
                "The response contains an unavailable citation.", rule=GuardrailRule.CITATION
            )
        if not safe_sources or not references:
            return ABSTENTION, ()
        return safe_content, safe_sources

    @staticmethod
    def is_greeting(question: str) -> bool:
        return question.strip().rstrip("!.?¡¿").casefold() in _GREETINGS
