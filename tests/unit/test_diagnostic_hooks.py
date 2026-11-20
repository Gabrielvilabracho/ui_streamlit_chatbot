from __future__ import annotations

import itertools
import logging
from types import SimpleNamespace

import pytest

from rag_chat.application.defaults import BaselineGuardrail
from rag_chat.application.hooks.diagnostics import DiagnosticDispatcher, DiagnosticHook
from rag_chat.application.hooks.events import (
    ErrorEvent,
    GuardrailRejectionEvent,
    SourcesEvent,
    TimingEvent,
    TokenUsageEvent,
)
from rag_chat.application.hooks.logging import log_diagnostic_event
from rag_chat.application.hooks.observer import HookObserver
from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.domain.errors import GuardrailRule, GuardrailViolation
from rag_chat.domain.models import GenerationResult, OrchestrationStep, SourceDocument, TokenUsage


def test_error_hook_reports_stage_and_category_without_exception_content() -> None:
    events = []
    observer = HookObserver(DiagnosticDispatcher((events.append,)))
    error = RuntimeError("sensitive-provider-diagnostics")

    def fail() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        observer.run(OrchestrationStep.RETRIEVE_CONTEXT, fail)
    assert caught.value is error
    assert events[0] == ErrorEvent(OrchestrationStep.RETRIEVE_CONTEXT, "unexpected")
    assert "sensitive-provider-diagnostics" not in repr(events)


def test_timing_hook_reports_actual_success_and_failure_duration() -> None:
    events = []
    ticks = iter((1.0, 1.125, 2.0, 2.250))
    observer = HookObserver(DiagnosticDispatcher((events.append,)), clock=lambda: next(ticks))
    assert observer.run(OrchestrationStep.RETRIEVE_CONTEXT, lambda: "result") == "result"

    def fail() -> None:
        raise TimeoutError("private")

    with pytest.raises(TimeoutError):
        observer.run(OrchestrationStep.GENERATE_ANSWER, fail)
    assert events == [
        TimingEvent(OrchestrationStep.RETRIEVE_CONTEXT, 125.0, True),
        ErrorEvent(OrchestrationStep.GENERATE_ANSWER, "timeout"),
        TimingEvent(OrchestrationStep.GENERATE_ANSWER, 250.0, False),
    ]


def test_token_and_source_hooks_report_only_available_counts() -> None:
    events = []
    service = RagOrchestrator(
        retriever=SimpleNamespace(retrieve=lambda *args, **kwargs: ()),
        generator=SimpleNamespace(
            generate=lambda **kwargs: GenerationResult("private answer", "model", TokenUsage(4, 2))
        ),
        guardrail=BaselineGuardrail(),
        telemetry=SimpleNamespace(record_success=lambda **kwargs: None),
        diagnostic_hooks=(events.append,),
    )
    progress = []
    answer = service.answer(question="private question", model="model", on_progress=progress.append)
    assert answer.content == "private answer"
    assert len(progress) == 10
    assert [event for event in events if isinstance(event, TokenUsageEvent)] == [
        TokenUsageEvent(TokenUsage(4, 2))
    ]
    assert [event for event in events if isinstance(event, SourcesEvent)] == [
        SourcesEvent(0, "retrieved")
    ]
    assert len([event for event in events if isinstance(event, TimingEvent)]) == 6
    assert "private" not in repr(events)


@pytest.mark.parametrize(
    "direction,value,rule",
    [
        ("input", " ", GuardrailRule.INPUT_EMPTY),
        ("input", "x" * 8001, GuardrailRule.INPUT_MAX_CHARACTERS),
        ("output", " ", GuardrailRule.OUTPUT_EMPTY),
        ("output", "x" * 32001, GuardrailRule.OUTPUT_MAX_CHARACTERS),
    ],
)
def test_rejection_hook_identifies_rule_and_preserves_exception(
    direction: str, value: str, rule: GuardrailRule
) -> None:
    events = []
    observer = HookObserver(DiagnosticDispatcher((events.append,)))
    stage = (
        OrchestrationStep.VALIDATE_INPUT
        if direction == "input"
        else OrchestrationStep.VALIDATE_OUTPUT
    )
    with pytest.raises(GuardrailViolation) as caught:
        observer.run(stage, lambda: getattr(BaselineGuardrail(), f"validate_{direction}")(value))
    assert caught.value.rule is rule
    assert events[0] == GuardrailRejectionEvent(stage, rule)
    assert events[1] == ErrorEvent(stage, "guardrail")


def test_diagnostic_hook_failure_cannot_mask_application_failure_or_skip_other_hooks(
    caplog,
) -> None:
    events = []

    def broken(event) -> None:
        raise RuntimeError("private observer error")

    observer = HookObserver(DiagnosticDispatcher((broken, events.append)))

    def fail() -> None:
        raise GuardrailViolation("private rejection")

    with pytest.raises(GuardrailViolation, match="private rejection"):
        observer.run(OrchestrationStep.VALIDATE_INPUT, fail)
    assert isinstance(events[0], GuardrailRejectionEvent)
    assert "private" not in caplog.text


def test_default_logging_records_all_five_event_types_with_safe_metadata(caplog) -> None:
    events = [
        ErrorEvent(OrchestrationStep.GENERATE_ANSWER, "provider"),
        TimingEvent(OrchestrationStep.GENERATE_ANSWER, 25.0, False),
        TokenUsageEvent(None),
        TokenUsageEvent(TokenUsage(0, 0)),
        SourcesEvent(3, "cited"),
        GuardrailRejectionEvent(OrchestrationStep.VALIDATE_INPUT, GuardrailRule.INPUT_EMPTY),
    ]
    with caplog.at_level(logging.INFO, logger="rag_chat.hooks"):
        for event in events:
            log_diagnostic_event(event)
    assert [record.hook_event for record in caplog.records] == [
        "error",
        "timing",
        "tokens",
        "tokens",
        "sources",
        "guardrail_rejection",
    ]
    assert caplog.records[2].usage_reported is False
    assert caplog.records[2].prompt_tokens is None
    assert caplog.records[3].usage_reported is True
    assert caplog.records[3].prompt_tokens == 0
    assert caplog.records[4].source_kind == "cited"


def test_request_diagnostics_do_not_accumulate_between_calls() -> None:
    events = []
    hooks: list[DiagnosticHook] = [events.append]
    ticks = itertools.count()
    service = RagOrchestrator(
        retriever=SimpleNamespace(retrieve=lambda *args, **kwargs: ()),
        generator=SimpleNamespace(
            generate=lambda **kwargs: GenerationResult("answer", "model", TokenUsage(), False)
        ),
        guardrail=BaselineGuardrail(),
        telemetry=SimpleNamespace(record_success=lambda **kwargs: None),
        diagnostic_hooks=hooks,
        hook_clock=lambda: next(ticks) / 1000,
    )
    hooks.clear()
    for _ in range(2):
        service.answer(question="question", model="model")
    assert [event for event in events if isinstance(event, TokenUsageEvent)] == [
        TokenUsageEvent(None),
        TokenUsageEvent(None),
    ]
    assert len([event for event in events if isinstance(event, TimingEvent)]) == 12


@pytest.mark.parametrize("failed_stage", list(OrchestrationStep))
def test_orchestrator_errors_identify_the_real_stage_once(failed_stage: OrchestrationStep) -> None:
    events = []
    progress = []
    failures = []
    error = RuntimeError("sensitive failure details")

    def operation(stage, value=None):
        if stage == failed_stage:
            raise error
        return value

    service = RagOrchestrator(
        retriever=SimpleNamespace(
            retrieve=lambda *args, **kwargs: operation(
                OrchestrationStep.RETRIEVE_CONTEXT,
                (SourceDocument("secret-id", "secret-document", "secret-title"),),
            )
        ),
        generator=SimpleNamespace(
            generate=lambda **kwargs: operation(
                OrchestrationStep.GENERATE_ANSWER,
                GenerationResult("secret-answer", "model", TokenUsage(2, 1)),
            )
        ),
        guardrail=SimpleNamespace(
            validate_input=lambda value: operation(OrchestrationStep.VALIDATE_INPUT),
            validate_output=lambda value: operation(OrchestrationStep.VALIDATE_OUTPUT),
        ),
        telemetry=SimpleNamespace(
            record_success=lambda **kwargs: operation(OrchestrationStep.RECORD_TELEMETRY),
            record_failure=lambda **kwargs: failures.append(kwargs),
        ),
        diagnostic_hooks=(events.append,),
    )
    with pytest.raises(RuntimeError) as caught:
        service.answer(question="secret-question", model="model", on_progress=progress.append)
    assert caught.value is error
    assert failures[0]["error"] is error
    assert [event for event in events if isinstance(event, ErrorEvent)] == [
        ErrorEvent(failed_stage, "unexpected")
    ]
    assert progress[-1].step == failed_stage
    assert progress[-1].state.value == "started"
    assert "secret" not in repr(events)
    assert "sensitive" not in repr(events)


def test_retrieval_hook_reports_count_without_document_identifiers_or_content() -> None:
    events = []
    service = RagOrchestrator(
        retriever=SimpleNamespace(
            retrieve=lambda *args, **kwargs: (
                SourceDocument("private-id", "private-document", "private-title"),
            )
        ),
        generator=SimpleNamespace(
            generate=lambda **kwargs: GenerationResult("answer", "model", TokenUsage(2, 1))
        ),
        guardrail=BaselineGuardrail(),
        telemetry=SimpleNamespace(record_success=lambda **kwargs: None),
        diagnostic_hooks=(events.append,),
    )
    service.answer(question="private-question", model="model")
    assert SourcesEvent(1, "retrieved") in events
    assert "private" not in repr(events)
