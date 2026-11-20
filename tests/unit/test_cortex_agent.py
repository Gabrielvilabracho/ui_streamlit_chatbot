from __future__ import annotations

import json
from typing import Any

import pytest

from rag_chat.domain.errors import ConfigurationError, GuardrailViolation, ProviderResponseError
from rag_chat.domain.models import ChatMessage, ProgressEvent, ProgressState
from rag_chat.infrastructure.snowflake.cortex_agent import (
    AGENT_MODEL,
    CortexAgentService,
    identify_viewer,
)

ROLE = "GG_APP_SOYOU_DATALAB_USER"


class FakeSession:
    def __init__(self, payload: object = None, role: str = ROLE) -> None:
        self.payload = payload or {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Grounded answer [7].",
                    "annotations": [
                        {
                            "type": "cortex_search_citation",
                            "index": 7,
                            "doc_id": "d1",
                            "doc_title": "Policy",
                            "text": "Approved evidence",
                        }
                    ],
                }
            ],
        }
        self.role = role
        self.calls: list[tuple[str, Any]] = []
        self.statement_params: list[Any] = []

    def sql(self, query: str, params: object = None) -> Any:
        self.calls.append((query, params))
        return self

    def collect(self, *, statement_params: object) -> list[dict[str, object]]:
        self.statement_params.append(statement_params)
        query = self.calls[-1][0]
        if "CURRENT_USER" in query:
            return [{"VIEWER": "viewer", "ACCESS_ROLE": self.role}]
        if "DATA_AGENT_RUN" in query:
            return [{"RESPONSE": json.dumps(self.payload)}]
        return []


@pytest.mark.parametrize(
    "role,policy",
    [
        (ROLE, "GENERAL"),
        ("GG_APP_SOYOU_DATALAB_DPO", "PRIVACY"),
        ("GG_APP_SP_DATALAB_CREDIT_AFTERSALES", "CREDIT_AFTERSALES"),
    ],
)
def test_viewer_uses_exact_approved_policy(role: str, policy: str) -> None:
    session = FakeSession(role=role)
    viewer = identify_viewer(session)
    assert (viewer.user, viewer.role, viewer.policy) == ("viewer", role, policy)
    assert viewer.agent == f"DATALAB.SPAIN.SOFIA_{policy}_AGENT"
    assert session.calls[0][0] == "USE SECONDARY ROLES NONE"


@pytest.mark.parametrize("role", ["ACCOUNTADMIN", "AGENT_STUDIO_USER", "", "general"])
def test_unknown_role_is_denied_without_agent_call(role: str) -> None:
    session = FakeSession(role=role)
    with pytest.raises(ConfigurationError, match="approved document policy"):
        identify_viewer(session)
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)


def test_agent_preserves_history_citations_and_truthful_progress() -> None:
    session = FakeSession()
    service = CortexAgentService(session=session, viewer=identify_viewer(session))
    events = []
    history = (ChatMessage("user", "Earlier"), ChatMessage("assistant", "Earlier answer"))
    answer = service.answer(
        question="What's approved?", model=AGENT_MODEL, history=history, on_progress=events.append
    )
    query, params = session.calls[-1]
    assert "SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?)" in query
    assert params[0] == "DATALAB.SPAIN.SOFIA_GENERAL_AGENT"
    request = json.loads(params[1])
    assert request == {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Earlier"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Earlier answer"}]},
            {"role": "user", "content": [{"type": "text", "text": "What's approved?"}]},
        ],
        "stream": False,
    }
    assert answer.content == "Grounded answer [7]."
    assert answer.sources[0].citation_label == "7"
    assert answer.sources[0].content == "Approved evidence"
    assert answer.model == AGENT_MODEL
    assert not answer.usage_reported
    assert answer.latency_ms >= 0
    assert [event.state for event in events] == [ProgressState.STARTED, ProgressState.COMPLETED]
    assert session.statement_params[-1] == {"STATEMENT_TIMEOUT_IN_SECONDS": "60"}


def test_retry_does_not_duplicate_last_user_question() -> None:
    session = FakeSession()
    service = CortexAgentService(session=session, viewer=identify_viewer(session))
    service.answer(
        question="Question", model=AGENT_MODEL, history=(ChatMessage("user", "Question"),)
    )
    assert len(json.loads(session.calls[-1][1][1])["messages"]) == 1


def test_agent_uses_configured_hooks_without_retaining_request_callbacks() -> None:
    session = FakeSession()
    registered: list[ProgressEvent] = []
    first: list[ProgressEvent] = []
    second: list[ProgressEvent] = []
    hooks = [registered.append]
    service = CortexAgentService(session=session, viewer=identify_viewer(session), hooks=hooks)
    hooks.clear()
    for callback in (first.append, second.append):
        service.answer(question="Question", model=AGENT_MODEL, on_progress=callback)
    assert len(first) == 2
    assert first == second
    assert registered == first + second


def test_agent_diagnostics_report_cited_sources_and_unknown_tokens_without_ui_changes() -> None:
    from rag_chat.application.hooks import SourcesEvent, TimingEvent, TokenUsageEvent

    session = FakeSession()
    events = []
    progress = []
    service = CortexAgentService(
        session=session, viewer=identify_viewer(session), diagnostic_hooks=(events.append,)
    )
    service.answer(question="Question", model=AGENT_MODEL, on_progress=progress.append)
    assert SourcesEvent(1, "cited") in events
    assert TokenUsageEvent(None) in events
    assert len(progress) == 2
    assert len([event for event in events if isinstance(event, TimingEvent)]) == 6


def test_agent_output_rejection_emits_one_error_and_rejection_with_available_usage() -> None:
    from rag_chat.application.guardrails import BaselineGuardrail
    from rag_chat.application.hooks import ErrorEvent, GuardrailRejectionEvent, TokenUsageEvent
    from rag_chat.domain.errors import GuardrailRule
    from rag_chat.domain.models import OrchestrationStep, TokenUsage

    session = FakeSession()
    session.payload["metadata"] = {
        "usage": {
            "tokens_consumed": [{"input_tokens": {"total": 3}, "output_tokens": {"total": 1}}]
        }
    }
    events = []
    progress = []
    service = CortexAgentService(
        session=session,
        viewer=identify_viewer(session),
        diagnostic_hooks=(events.append,),
        guardrail=BaselineGuardrail(max_output_characters=1),
    )
    with pytest.raises(GuardrailViolation, match="response exceeded"):
        service.answer(question="Question", model=AGENT_MODEL, on_progress=progress.append)
    assert TokenUsageEvent(TokenUsage(3, 1)) in events
    assert [event for event in events if isinstance(event, GuardrailRejectionEvent)] == [
        GuardrailRejectionEvent(
            OrchestrationStep.VALIDATE_OUTPUT, GuardrailRule.OUTPUT_MAX_CHARACTERS
        )
    ]
    assert [event for event in events if isinstance(event, ErrorEvent)] == [
        ErrorEvent(OrchestrationStep.VALIDATE_OUTPUT, "guardrail")
    ]
    assert [event.state for event in progress] == [ProgressState.STARTED]


def test_agent_diagnostics_report_identity_failure_before_generation() -> None:
    from rag_chat.application.hooks import ErrorEvent

    session = FakeSession()
    events = []
    service = CortexAgentService(
        session=session, viewer=identify_viewer(session), diagnostic_hooks=(events.append,)
    )
    session.role = "ACCOUNTADMIN"
    with pytest.raises(ConfigurationError):
        service.answer(question="Question", model=AGENT_MODEL)
    assert [event for event in events if isinstance(event, ErrorEvent)] == [
        ErrorEvent("Verify identity", "configuration")
    ]
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)


def test_agent_uses_injected_guardrails_at_input_and_output_boundaries() -> None:
    from rag_chat.application.guardrails import BaselineGuardrail

    session = FakeSession()
    service = CortexAgentService(
        session=session,
        viewer=identify_viewer(session),
        guardrail=BaselineGuardrail(max_input_characters=2, max_output_characters=2),
    )
    with pytest.raises(GuardrailViolation, match="question is too long"):
        service.answer(question="long", model=AGENT_MODEL)
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)
    with pytest.raises(GuardrailViolation, match="response exceeded"):
        service.answer(question="ok", model=AGENT_MODEL)
    assert sum("DATA_AGENT_RUN" in sql for sql, _ in session.calls) == 1


@pytest.mark.parametrize("denied", ["model", "role", "identity"])
def test_custom_pipeline_cannot_bypass_agent_access_controls(denied: str) -> None:
    from rag_chat.application.guardrails import GuardrailPipeline

    session = FakeSession()
    events: list[ProgressEvent] = []
    service = CortexAgentService(
        session=session,
        viewer=identify_viewer(session),
        guardrail=GuardrailPipeline(input_rules=(), output_rules=()),
        hooks=(events.append,),
    )
    if denied == "role":
        session.role = "ACCOUNTADMIN"
    elif denied == "identity":
        session.role = "GG_APP_SOYOU_DATALAB_DPO"
    with pytest.raises(ConfigurationError):
        service.answer(question="Question", model="override" if denied == "model" else AGENT_MODEL)
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)
    assert not events


def test_identity_change_and_model_override_reject_before_agent_call() -> None:
    session = FakeSession()
    service = CortexAgentService(session=session, viewer=identify_viewer(session))
    with pytest.raises(ConfigurationError, match="agent configuration"):
        service.answer(question="Question", model="ignored-override")
    session.role = "GG_APP_SOYOU_DATALAB_DPO"
    with pytest.raises(ConfigurationError, match="changed"):
        service.answer(question="Question", model=AGENT_MODEL)
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "assistant", "content": []},
        {"role": "assistant", "content": [{"type": "thinking", "text": "private"}]},
        {
            "role": "assistant",
            "status": "timed_out",
            "content": [{"type": "text", "text": "partial"}],
        },
        {
            "role": "assistant",
            "warnings": [{"message": "private tool failure"}],
            "content": [{"type": "text", "text": "degraded"}],
        },
        {"role": "user", "content": [{"type": "text", "text": "wrong role"}]},
    ],
)
def test_partial_or_malformed_agent_output_is_not_an_answer(payload: object) -> None:
    session = FakeSession(payload)
    service = CortexAgentService(session=session, viewer=identify_viewer(session))
    with pytest.raises(ProviderResponseError):
        service.answer(question="Question", model=AGENT_MODEL)


def test_provider_failure_is_safe_and_does_not_retry() -> None:
    session = FakeSession()
    viewer = identify_viewer(session)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret prompt and account details")

    session.sql = fail  # type: ignore[method-assign,assignment]
    with pytest.raises(ProviderResponseError, match="caller connection") as error:
        CortexAgentService(session=session, viewer=viewer).answer(question="Q", model=AGENT_MODEL)
    assert "secret" not in str(error.value)


def test_agent_counts_only_reported_aggregate_usage() -> None:
    session = FakeSession(
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "Answer"}],
            "metadata": {
                "usage": {
                    "tokens_consumed": [
                        {"input_tokens": {"total": 20}, "output_tokens": {"total": 5}},
                        {"input_tokens": {"total": 10}, "output_tokens": {"total": 3}},
                    ]
                }
            },
        }
    )
    answer = CortexAgentService(session=session, viewer=identify_viewer(session)).answer(
        question="Question",
        model=AGENT_MODEL,
    )
    assert answer.usage_reported
    assert (answer.usage.prompt_tokens, answer.usage.completion_tokens) == (30, 8)


def test_conflicting_citation_indices_do_not_relabel_evidence() -> None:
    session = FakeSession(
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Answer [7]",
                    "annotations": [
                        {"type": "cortex_search_citation", "index": 7, "doc_id": "a"},
                        {"type": "cortex_search_citation", "index": 7, "doc_id": "b"},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ProviderResponseError, match="conflicting citations"):
        CortexAgentService(session=session, viewer=identify_viewer(session)).answer(
            question="Question",
            model=AGENT_MODEL,
        )
