"""Caller-bound, non-streaming Cortex Agent implementation of AnswerService.

The caller session is injected by Streamlit, never constructed from owner credentials.
Deployment must separately prove caller grants and policy-isolated agent/Search objects.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rag_chat.application.guardrails import BaselineGuardrail
from rag_chat.application.guardrails.runtime import (
    GREETING,
    RequestDeadline,
    RuntimeGuardrails,
    UsageTicket,
)
from rag_chat.application.hooks import HookDispatcher, ProgressHook
from rag_chat.application.hooks.diagnostics import (
    DEFAULT_DIAGNOSTIC_HOOKS,
    DiagnosticDispatcher,
    DiagnosticHook,
)
from rag_chat.application.hooks.events import SourcesEvent, TokenUsageEvent
from rag_chat.application.hooks.observer import HookObserver
from rag_chat.application.ports import Guardrail
from rag_chat.domain.errors import ConfigurationError, ProviderResponseError
from rag_chat.domain.models import (
    ChatMessage,
    OrchestrationStep,
    ProgressEvent,
    RagAnswer,
    SourceDocument,
    TokenUsage,
)
from rag_chat.infrastructure.snowflake._errors import translate_timeout

AGENT_MODEL = "Managed by Cortex Agent"
_POLICIES = {
    "GG_APP_SOYOU_DATALAB_USER": "GENERAL",
    "GG_APP_SOYOU_DATALAB_DPO": "PRIVACY",
    "GG_APP_SP_DATALAB_CREDIT_AFTERSALES": "CREDIT_AFTERSALES",
}
_TIMEOUT = {"STATEMENT_TIMEOUT_IN_SECONDS": "60"}


@dataclass(frozen=True, slots=True)
class Viewer:
    user: str
    role: str
    policy: str

    @property
    def agent(self) -> str:
        return f"DATALAB.SPAIN.SOFIA_{self.policy}_AGENT"


def _query(
    session: Any,
    sql: str,
    params: list[str] | None = None,
    *,
    deadline: RequestDeadline | None = None,
) -> list[Any]:
    timeout = (
        _TIMEOUT
        if deadline is None
        else {"STATEMENT_TIMEOUT_IN_SECONDS": str(min(60, max(1, math.ceil(deadline.remaining()))))}
    )
    try:
        rows = list(session.sql(sql, params=params).collect(statement_params=timeout))
    except Exception as error:
        translate_timeout(error, operation="Cortex Agent caller connection")
        raise ProviderResponseError(
            "The Snowflake caller connection failed. Check the runtime and caller grants."
        ) from error
    if deadline:
        deadline.remaining()
    return rows


def identify_viewer(session: Any, *, deadline: RequestDeadline | None = None) -> Viewer:
    """Use the default primary role only; no secondary-role or owner escalation."""
    _query(session, "USE SECONDARY ROLES NONE", deadline=deadline)
    rows = _query(
        session, "SELECT CURRENT_USER() AS VIEWER, CURRENT_ROLE() AS ACCESS_ROLE", deadline=deadline
    )
    if len(rows) != 1:
        raise ConfigurationError("Snowflake did not return a verified viewer identity.")
    user, role = rows[0]["VIEWER"], rows[0]["ACCESS_ROLE"]
    if not isinstance(user, str) or not user.strip() or role not in _POLICIES:
        raise ConfigurationError("The viewer's default role has no approved document policy.")
    return Viewer(user=user, role=role, policy=_POLICIES[role])


class CortexAgentService:
    """One viewer, one approved policy, one named agent; no fallback or retries."""

    def __init__(
        self,
        *,
        session: Any,
        viewer: Viewer,
        hooks: Sequence[ProgressHook] = (),
        guardrail: Guardrail | None = None,
        diagnostic_hooks: Sequence[DiagnosticHook] = DEFAULT_DIAGNOSTIC_HOOKS,
        hook_clock: Callable[[], float] = time.perf_counter,
        safety: RuntimeGuardrails | None = None,
    ) -> None:
        self._session = session
        self._viewer = viewer
        self._hooks = HookDispatcher(hooks=tuple(hooks))
        self._guardrail = guardrail if guardrail is not None else BaselineGuardrail()
        self._diagnostics = DiagnosticDispatcher(hooks=tuple(diagnostic_hooks))
        self._hook_clock = hook_clock
        self._safety = safety

    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        observer = HookObserver(
            self._diagnostics, progress=self._hooks, on_progress=on_progress, clock=self._hook_clock
        )
        return observer.run(
            None,
            lambda: self._answer(
                question=question, model=model, history=history, observer=observer
            ),
            progress=False,
        )

    def _validate_model(self, model: str) -> None:
        if model != AGENT_MODEL:
            raise ConfigurationError("Choose the model in the agent configuration, not the app.")

    def _verify_viewer(self, deadline: RequestDeadline | None = None) -> None:
        if identify_viewer(self._session, deadline=deadline) != self._viewer:
            raise ConfigurationError(
                "The viewer identity changed. Reload and start a new conversation."
            )

    def _answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage],
        observer: HookObserver,
    ) -> RagAnswer:
        safety = self._safety
        deadline = safety.deadline() if safety else None
        ticket: UsageTicket | None = None
        observer.run("Validate model", lambda: self._validate_model(model), progress=False)
        observer.run(
            OrchestrationStep.VALIDATE_INPUT,
            lambda: self._guardrail.validate_input(question),
            progress=False,
        )
        if safety:
            question, history = observer.run(
                OrchestrationStep.VALIDATE_INPUT,
                lambda: safety.prepare(question, history),
                progress=False,
            )
        observer.run("Verify identity", lambda: self._verify_viewer(deadline), progress=False)
        if safety and safety.is_greeting(question):
            ticket = observer.run(
                OrchestrationStep.VALIDATE_INPUT,
                lambda: safety.reserve("agent:" + self._viewer.user),
                progress=False,
            )
            ticket.finish(TokenUsage())
            return RagAnswer(GREETING, AGENT_MODEL, (), TokenUsage(), 0.0)
        # Retry history already contains the current question; ordinary submissions do not.
        messages = list(history)
        if not messages or messages[-1] != ChatMessage("user", question):
            messages.append(ChatMessage("user", question))
        request = json.dumps(
            {
                "messages": [
                    {"role": item.role, "content": [{"type": "text", "text": item.content}]}
                    for item in messages
                ],
                "stream": False,
            }
        )
        if safety:
            observer.run(
                OrchestrationStep.VALIDATE_INPUT,
                lambda: safety.check_context(request),
                progress=False,
            )
            ticket = observer.run(
                OrchestrationStep.VALIDATE_INPUT,
                lambda: safety.reserve("agent:" + self._viewer.user),
                progress=False,
            )
        started = time.perf_counter()

        def generate() -> RagAnswer:
            rows = _query(
                self._session,
                "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS RESPONSE",
                [self._viewer.agent, request],
                deadline=deadline,
            )
            if len(rows) != 1:
                raise ProviderResponseError("Cortex Agent returned no complete answer.")
            payload = _payload(rows[0]["RESPONSE"])
            usage, reported = _usage(payload)
            if ticket:
                ticket.finish(usage if reported else None)
            self._diagnostics.emit(TokenUsageEvent(usage if reported else None))
            text, sources = _text_and_sources(payload)
            self._diagnostics.emit(SourcesEvent(len(sources), "cited"))
            observer.run(
                OrchestrationStep.VALIDATE_OUTPUT,
                lambda: self._guardrail.validate_output(text),
                progress=False,
            )
            if safety:
                text, sources = observer.run(
                    OrchestrationStep.VALIDATE_OUTPUT,
                    lambda: safety.ground(text, sources, native=True),
                    progress=False,
                )
            if deadline:
                deadline.remaining()
            return RagAnswer(
                content=text,
                model=AGENT_MODEL,
                sources=sources,
                usage=usage,
                latency_ms=(time.perf_counter() - started) * 1000,
                usage_reported=reported,
            )

        try:
            return observer.run(OrchestrationStep.GENERATE_ANSWER, generate)
        finally:
            if ticket:
                ticket.finish()


def _payload(raw: object) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError) as error:
        raise ProviderResponseError("Cortex Agent returned invalid JSON.") from error
    if not isinstance(payload, Mapping) or payload.get("role") != "assistant":
        raise ProviderResponseError("Cortex Agent returned an invalid answer.")
    if payload.get("status") not in (None, "completed") or payload.get("error"):
        raise ProviderResponseError("Cortex Agent did not complete the answer. Retry the request.")
    if payload.get("warnings"):
        # Never present a degraded answer as grounded or expose raw tool diagnostics.
        raise ProviderResponseError(
            "Cortex Agent reported a tool warning; the answer was withheld. "
            "Contact the app administrator."
        )
    return payload


def _text_and_sources(payload: Mapping[str, Any]) -> tuple[str, tuple[SourceDocument, ...]]:
    blocks = payload.get("content")
    if not isinstance(blocks, list):
        raise ProviderResponseError("Cortex Agent returned invalid content.")
    texts: list[str] = []
    sources: dict[int, SourceDocument] = {}
    for block in blocks:
        if not isinstance(block, Mapping) or block.get("type") != "text":
            continue  # Thinking and raw tool results are never rendered as answer text.
        text = block.get("text")
        if not isinstance(text, str):
            raise ProviderResponseError("Cortex Agent returned invalid text.")
        texts.append(text)
        annotations = block.get("annotations", [])
        if not isinstance(annotations, list):
            raise ProviderResponseError("Cortex Agent returned invalid citations.")
        for citation in annotations:
            if not isinstance(citation, Mapping):
                raise ProviderResponseError("Cortex Agent returned invalid citations.")
            if citation.get("type") != "cortex_search_citation":
                continue
            index = citation.get("index")
            if type(index) is not int or index < 0:
                raise ProviderResponseError("Cortex Agent returned invalid citation identifiers.")
            source = SourceDocument(
                document_id=str(
                    citation.get("doc_id") or citation.get("search_result_id") or index
                ),
                title=str(citation.get("doc_title") or "Agent source"),
                content=str(citation.get("text") or "Source preview unavailable."),
                citation_label=str(index),
            )
            if index in sources and sources[index] != source:
                raise ProviderResponseError("Cortex Agent returned conflicting citations.")
            sources[index] = source
    text = "\n\n".join(texts).strip()
    if not text:
        raise ProviderResponseError("Cortex Agent returned no answer text.")
    return text, tuple(sources.values())


def _usage(payload: Mapping[str, Any]) -> tuple[TokenUsage, bool]:
    metadata = payload.get("metadata", {})
    usage = metadata.get("usage", {}) if isinstance(metadata, Mapping) else {}
    entries = usage.get("tokens_consumed") if isinstance(usage, Mapping) else None
    if not isinstance(entries, list) or not entries:
        return TokenUsage(), False
    inputs, outputs = 0, 0
    for entry in entries:
        if not isinstance(entry, Mapping):
            return TokenUsage(), False
        input_tokens, output_tokens = entry.get("input_tokens"), entry.get("output_tokens")
        if not isinstance(input_tokens, Mapping) or not isinstance(output_tokens, Mapping):
            return TokenUsage(), False
        incoming, outgoing = input_tokens.get("total"), output_tokens.get("total")
        if type(incoming) is not int or type(outgoing) is not int or min(incoming, outgoing) < 0:
            return TokenUsage(), False
        inputs += incoming
        outputs += outgoing
    return TokenUsage(inputs, outputs), True
