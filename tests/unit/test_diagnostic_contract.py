import logging
from types import SimpleNamespace

import pytest

from rag_chat.application.guardrails import BaselineGuardrail
from rag_chat.application.hooks import GuardrailRejectionEvent, TokenUsageEvent
from rag_chat.application.hooks.logging import log_diagnostic_event
from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.domain.errors import GuardrailViolation
from rag_chat.domain.models import GenerationResult, TokenUsage


@pytest.mark.parametrize("reported", [False, True])
@pytest.mark.parametrize("reject", [False, True])
def test_diagnostics_log_schema_and_legacy_progress(reported, reject, caplog):
    private = "independent-private-content"
    events, order = [], []
    service = RagOrchestrator(
        retriever=SimpleNamespace(retrieve=lambda *a, **kw: ()),
        generator=SimpleNamespace(
            generate=lambda **kw: GenerationResult(private, "model", TokenUsage(), reported)
        ),
        guardrail=BaselineGuardrail(max_output_characters=1 if reject else 32000),
        telemetry=SimpleNamespace(
            record_success=lambda **kw: None, record_failure=lambda **kw: None
        ),
        hooks=(lambda e: order.append(("registered", e)),),
        diagnostic_hooks=(events.append, log_diagnostic_event),
    )
    with caplog.at_level(logging.INFO, logger="rag_chat.hooks"):
        if reject:
            with pytest.raises(GuardrailViolation, match="safe output limit"):
                service.answer(
                    question=private,
                    model="model",
                    on_progress=lambda e: order.append(("request", e)),
                )
        else:
            service.answer(
                question=private,
                model="model",
                on_progress=lambda e: order.append(("request", e)),
            )
    assert [kind for kind, _ in order] == ["registered", "request"] * (7 if reject else 10)
    assert [e.usage for e in events if isinstance(e, TokenUsageEvent)] == [
        TokenUsage() if reported else None
    ]
    assert [e.rule.value for e in events if isinstance(e, GuardrailRejectionEvent)] == (
        ["output.max_characters"] if reject else []
    )
    records = [record for record in caplog.records if record.name == "rag_chat.hooks"]
    assert records and private not in repr([record.__dict__ for record in records])
    standard = set(logging.LogRecord("n", 20, "p", 1, "m", (), None).__dict__) | {"message"}
    schema = {
        "error": {"stage", "error_category"},
        "timing": {"stage", "duration_ms", "succeeded"},
        "sources": {"source_count", "source_kind"},
        "tokens": {"usage_reported", "prompt_tokens", "completion_tokens"},
        "guardrail_rejection": {"stage", "rule"},
    }
    for record in records:
        assert set(record.__dict__) - standard == schema[record.hook_event] | {"hook_event"}
        assert record.message == record.msg == "rag_hook_event"
        assert record.levelno == logging.INFO
        assert record.args == () and record.exc_info is None and record.stack_info is None
