from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.domain.errors import RagTimeoutError
from rag_chat.domain.models import (
    ChatMessage,
    GenerationResult,
    OrchestrationStep,
    ProgressEvent,
    ProgressState,
    SourceDocument,
    TokenUsage,
)
from rag_chat.domain.prompts import SYSTEM_PROMPT


@dataclass
class StubRetriever:
    documents: tuple[SourceDocument, ...]

    def retrieve(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        assert query == "How do I close the books?"
        assert limit == 4
        return self.documents


@dataclass
class StubGenerator:
    result: GenerationResult | None = None
    error: Exception | None = None
    prompts: list[str] = field(default_factory=list)

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout_seconds: float,
    ) -> GenerationResult:
        assert model == "llama3.3-70b"
        assert timeout_seconds == 30.0
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class RecordingGuardrail:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def validate_input(self, value: str) -> None:
        self.calls.append(("input", value))

    def validate_output(self, value: str) -> None:
        self.calls.append(("output", value))


@dataclass
class RecordingTelemetry:
    successes: list[object] = field(default_factory=list)
    failures: list[tuple[str, str, float]] = field(default_factory=list)

    def record_success(self, *, question: str, answer: object) -> None:
        self.successes.append((question, answer))

    def record_failure(self, *, question: str, error: Exception, latency_ms: float) -> None:
        self.failures.append((question, type(error).__name__, latency_ms))


def test_orchestrator_returns_grounded_answer_and_reports_every_step() -> None:
    documents = (
        SourceDocument(
            document_id="close-001",
            content="Close receivables before posting the final journal.",
            title="Month-end close",
            uri="snowflake://knowledge/close-001",
        ),
    )
    generator = StubGenerator(
        result=GenerationResult(
            content="Close receivables first [1].",
            model="llama3.3-70b",
            usage=TokenUsage(prompt_tokens=120, completion_tokens=18),
        )
    )
    guardrail = RecordingGuardrail()
    telemetry = RecordingTelemetry()
    progress: list[ProgressEvent] = []
    clock_values = iter((10.0, 10.245))
    orchestrator = RagOrchestrator(
        retriever=StubRetriever(documents),
        generator=generator,
        guardrail=guardrail,
        telemetry=telemetry,
        retrieval_limit=4,
        timeout_seconds=30.0,
        clock=lambda: next(clock_values),
    )

    answer = orchestrator.answer(
        question="How do I close the books?",
        model="llama3.3-70b",
        history=(ChatMessage(role="user", content="We are preparing month-end."),),
        on_progress=progress.append,
    )

    assert answer.content == "Close receivables first [1]."
    assert answer.sources == documents
    assert answer.usage.total_tokens == 138
    assert answer.latency_ms == pytest.approx(245.0)
    assert progress == [
        event
        for step in OrchestrationStep
        for event in (
            ProgressEvent(step=step, state=ProgressState.STARTED),
            ProgressEvent(step=step, state=ProgressState.COMPLETED),
        )
    ]
    assert guardrail.calls == [
        ("input", "How do I close the books?"),
        ("output", "Close receivables first [1]."),
    ]
    assert SYSTEM_PROMPT in generator.prompts[0]
    assert "Month-end close" in generator.prompts[0]
    assert "Close receivables before posting" in generator.prompts[0]
    assert telemetry.successes == [("How do I close the books?", answer)]


def test_orchestrator_translates_timeout_and_records_failure() -> None:
    telemetry = RecordingTelemetry()
    clock_values = iter((20.0, 20.5))
    orchestrator = RagOrchestrator(
        retriever=StubRetriever(()),
        generator=StubGenerator(error=TimeoutError("request deadline exceeded")),
        guardrail=RecordingGuardrail(),
        telemetry=telemetry,
        retrieval_limit=4,
        timeout_seconds=30.0,
        clock=lambda: next(clock_values),
    )

    progress: list[ProgressEvent] = []
    with pytest.raises(RagTimeoutError, match="timed out"):
        orchestrator.answer(
            question="How do I close the books?",
            model="llama3.3-70b",
            on_progress=progress.append,
        )

    assert telemetry.failures == [
        ("How do I close the books?", "RagTimeoutError", 500.0)
    ]
    assert progress[-1] == ProgressEvent(
        step=OrchestrationStep.GENERATE_ANSWER,
        state=ProgressState.STARTED,
    )


def test_configured_hooks_receive_same_events_as_each_request_callback() -> None:
    registered: list[ProgressEvent] = []
    first: list[ProgressEvent] = []
    second: list[ProgressEvent] = []
    hooks = [registered.append]
    service = RagOrchestrator(
        retriever=StubRetriever(()),
        generator=StubGenerator(result=GenerationResult("Answer", "llama3.3-70b", TokenUsage())),
        guardrail=RecordingGuardrail(),
        telemetry=RecordingTelemetry(),
        retrieval_limit=4,
        hooks=hooks,
    )
    hooks.clear()
    for callback in (first.append, second.append):
        service.answer(
            question="How do I close the books?", model="llama3.3-70b", on_progress=callback
        )
    assert first == second
    assert len(first) == 10
    assert registered == first + second
