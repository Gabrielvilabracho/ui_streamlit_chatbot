from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from trulens.otel.semconv.trace import GenAIAttributes, SpanAttributes

from rag_chat.composition import with_observability
from rag_chat.domain.models import GenerationResult, RagAnswer, SourceDocument, TokenUsage
from rag_chat.infrastructure.trulens.instrumentation import (
    FailureIsolatedRecording,
    create_trulens_service,
    generation_span_attributes,
    record_root_span_attributes,
    retrieval_span_attributes,
)
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings


def _answer() -> RagAnswer:
    return RagAnswer(
        content="Grounded answer [1].",
        model="llama3.3-70b",
        sources=(),
        usage=TokenUsage(prompt_tokens=12, completion_tokens=4),
        latency_ms=25.0,
    )


def test_retrieval_attributes_map_query_and_context_without_adapter_objects() -> None:
    documents = (
        SourceDocument(
            document_id="doc-1",
            content="Approved invoices are posted after validation.",
            title="Invoice policy",
        ),
    )

    attributes = retrieval_span_attributes(
        documents,
        None,
        query="When are invoices posted?",
        limit=5,
    )

    assert attributes == {
        SpanAttributes.RETRIEVAL.QUERY_TEXT: "When are invoices posted?",
        SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: [
            "Approved invoices are posted after validation."
        ],
        SpanAttributes.RETRIEVAL.NUM_CONTEXTS: 1,
    }


def test_generation_attributes_map_model_tokens_and_snowflake_provider() -> None:
    result = GenerationResult(
        content="Grounded answer [1].",
        model="llama3.3-70b",
        usage=TokenUsage(prompt_tokens=44, completion_tokens=9),
    )

    attributes = generation_span_attributes(
        result,
        None,
        model="llama3.3-70b",
        prompt="Trusted prompt",
        timeout_seconds=30.0,
    )

    assert attributes[SpanAttributes.COST.MODEL] == "llama3.3-70b"
    assert attributes[SpanAttributes.COST.NUM_PROMPT_TOKENS] == 44
    assert attributes[SpanAttributes.COST.NUM_COMPLETION_TOKENS] == 9
    assert attributes[SpanAttributes.COST.NUM_TOKENS] == 53
    assert attributes[GenAIAttributes.SYSTEM.NAME] == "snowflake"


def test_record_root_attributes_map_only_question_answer_and_error_type() -> None:
    success = record_root_span_attributes(
        _answer(),
        None,
        question="How do I post an invoice?",
        model="llama3.3-70b",
    )
    failure = record_root_span_attributes(
        None,
        RuntimeError("sensitive provider detail"),
        question="How do I post an invoice?",
        model="llama3.3-70b",
    )

    assert success[SpanAttributes.RECORD_ROOT.INPUT] == "How do I post an invoice?"
    assert success[SpanAttributes.RECORD_ROOT.OUTPUT] == "Grounded answer [1]."
    assert failure[SpanAttributes.RECORD_ROOT.ERROR] == "RuntimeError"
    assert "sensitive provider detail" not in str(failure)


def test_disabled_tracing_import_does_not_emit_record_root_warning() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import rag_chat.composition"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Cannot explicitly set 'record_root' span type" not in result.stderr


@dataclass
class FakeContext:
    enter_error: Exception | None = None
    exit_error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def __enter__(self) -> object:
        self.calls.append("enter")
        if self.enter_error:
            raise self.enter_error
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.calls.append("exit")
        if self.exit_error:
            raise self.exit_error
        return False


def test_recording_entry_failure_runs_request_once_without_tracing(caplog) -> None:
    context = FakeContext(enter_error=RuntimeError("telemetry unavailable"))
    recording = FailureIsolatedRecording(context)
    calls = 0

    def operation() -> RagAnswer:
        nonlocal calls
        calls += 1
        return _answer()

    assert recording.invoke(operation) == _answer()
    assert calls == 1
    assert context.calls == ["enter"]
    assert "telemetry unavailable" not in caplog.text


def test_recording_exit_failure_keeps_successful_response() -> None:
    context = FakeContext(exit_error=RuntimeError("export failed"))
    recording = FailureIsolatedRecording(context)

    assert recording.invoke(_answer) == _answer()
    assert context.calls == ["enter", "exit"]


def test_application_failure_is_not_retried_or_replaced_by_recording_failure() -> None:
    context = FakeContext(exit_error=RuntimeError("export failed"))
    recording = FailureIsolatedRecording(context)
    calls = 0

    def operation() -> RagAnswer:
        nonlocal calls
        calls += 1
        raise ValueError("application failed")

    with pytest.raises(ValueError, match="application failed"):
        recording.invoke(operation)

    assert calls == 1
    assert context.calls == ["enter", "exit"]


class FakeAnswerService:
    def answer(self, **_: Any) -> RagAnswer:
        return _answer()


def test_create_trulens_service_reuses_session_and_registers_named_app() -> None:
    snowpark_session = object()
    connector = object()
    tru_session = object()
    recorder = FakeContext()
    captured: dict[str, object] = {}

    def connector_factory(session: object) -> object:
        captured["snowpark_session"] = session
        return connector

    def session_factory(*, connector: object) -> object:
        captured["connector"] = connector
        return tru_session

    def recorder_factory(app: object, **kwargs: object) -> FakeContext:
        captured["app"] = app
        captured.update(kwargs)
        return recorder

    service = create_trulens_service(
        delegate=FakeAnswerService(),
        snowpark_session=snowpark_session,
        settings=ObservabilitySettings(
            enabled=True,
            app_name="SOFIA_CUSTOM_RAG",
            app_version="release-7",
        ),
        connector_factory=connector_factory,
        session_factory=session_factory,
        recorder_factory=recorder_factory,
    )

    answer = service.answer(question="Question", model="llama3.3-70b")

    assert answer == _answer()
    assert captured["snowpark_session"] is snowpark_session
    assert captured["connector"] is connector
    assert captured["session"] is tru_session
    assert captured["app_name"] == "SOFIA_CUSTOM_RAG"
    assert captured["app_version"] == "release-7"
    assert callable(captured["main_method"])
    assert recorder.calls == ["enter", "exit"]


def test_disabled_observability_does_not_construct_trulens_service() -> None:
    service = FakeAnswerService()

    def unexpected_factory(**_: object) -> FakeAnswerService:
        raise AssertionError("TruLens factory must not run while disabled")

    result = with_observability(
        service=service,
        snowpark_session=object(),
        settings=ObservabilitySettings(enabled=False),
        service_factory=unexpected_factory,
    )

    assert result is service


def test_setup_failure_returns_uninstrumented_service(caplog) -> None:
    service = FakeAnswerService()

    def failing_factory(**_: object) -> FakeAnswerService:
        raise RuntimeError("connector unavailable")

    result = with_observability(
        service=service,
        snowpark_session=object(),
        settings=ObservabilitySettings(enabled=True),
        service_factory=failing_factory,
    )

    assert result is service
    assert "connector unavailable" not in caplog.text
