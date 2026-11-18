"""Caller-bound, non-streaming Cortex Agent implementation of AnswerService.

The caller session is injected by Streamlit, never constructed from owner credentials.
Deployment must separately prove caller grants and policy-isolated agent/Search objects.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rag_chat.application.defaults import BaselineGuardrail
from rag_chat.domain.errors import ConfigurationError, ProviderResponseError
from rag_chat.domain.models import (
    ChatMessage,
    OrchestrationStep,
    ProgressEvent,
    ProgressState,
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


def _query(session: Any, sql: str, params: list[str] | None = None) -> list[Any]:
    try:
        return list(session.sql(sql, params=params).collect(statement_params=_TIMEOUT))
    except Exception as error:
        translate_timeout(error, operation="Cortex Agent caller connection")
        raise ProviderResponseError(
            "The Snowflake caller connection failed. Check the runtime and caller grants."
        ) from error


def identify_viewer(session: Any) -> Viewer:
    """Use the default primary role only; no secondary-role or owner escalation."""
    _query(session, "USE SECONDARY ROLES NONE")
    rows = _query(session, "SELECT CURRENT_USER() AS VIEWER, CURRENT_ROLE() AS ACCESS_ROLE")
    if len(rows) != 1:
        raise ConfigurationError("Snowflake did not return a verified viewer identity.")
    user, role = rows[0]["VIEWER"], rows[0]["ACCESS_ROLE"]
    if not isinstance(user, str) or not user.strip() or role not in _POLICIES:
        raise ConfigurationError("The viewer's default role has no approved document policy.")
    return Viewer(user=user, role=role, policy=_POLICIES[role])


class CortexAgentService:
    """One viewer, one approved policy, one named agent; no fallback or retries."""

    def __init__(self, *, session: Any, viewer: Viewer) -> None:
        self._session = session
        self._viewer = viewer

    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        if model != AGENT_MODEL:
            raise ConfigurationError("Choose the model in the agent configuration, not the app.")
        guardrail = BaselineGuardrail()
        guardrail.validate_input(question)
        if identify_viewer(self._session) != self._viewer:
            raise ConfigurationError(
                "The viewer identity changed. Reload and start a new conversation."
            )
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
        started = time.perf_counter()
        if on_progress:
            on_progress(ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED))
        rows = _query(
            self._session,
            "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS RESPONSE",
            [self._viewer.agent, request],
        )
        if len(rows) != 1:
            raise ProviderResponseError("Cortex Agent returned no complete answer.")
        payload = _payload(rows[0]["RESPONSE"])
        text, sources = _text_and_sources(payload)
        guardrail.validate_output(text)
        usage, reported = _usage(payload)
        answer = RagAnswer(
            content=text,
            model=AGENT_MODEL,
            sources=sources,
            usage=usage,
            latency_ms=(time.perf_counter() - started) * 1000,
            usage_reported=reported,
        )
        if on_progress:
            on_progress(ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.COMPLETED))
        return answer


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
