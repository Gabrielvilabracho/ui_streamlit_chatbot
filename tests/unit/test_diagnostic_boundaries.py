import gc
import itertools
import logging
import weakref
from types import SimpleNamespace

import pytest

from rag_chat.application.hooks.events import (
    ErrorEvent,
    GuardrailRejectionEvent,
    SourcesEvent,
    TimingEvent,
    TokenUsageEvent,
)
from rag_chat.application.hooks.logging import log_diagnostic_event
from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.domain.errors import GuardrailRule, GuardrailViolation
from rag_chat.domain.models import GenerationResult, OrchestrationStep, SourceDocument, TokenUsage
from rag_chat.infrastructure.snowflake.cortex_agent import AGENT_MODEL, CortexAgentService, Viewer


@pytest.mark.parametrize("agent", [False, True])
def test_cached_service_failure_privacy_and_retry_boundary(agent, caplog):
    # Exercise consecutive rejections, recovery, and private metadata in both services.
    secret = "PRIVATE_SENTINEL_93847"  # gitleaks:allow -- deterministic test sentinel
    events, rejecting = [], [True]
    error = GuardrailViolation(secret, 17, rule=secret)

    def validate_output(value):
        if rejecting[0]:
            raise error

    def broken_exporter(event):
        raise RuntimeError(secret)

    citation = {"type": "cortex_search_citation", "index": 1, "doc_id": secret}
    payload = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": secret, "annotations": [citation, citation]},
        ],
    }
    viewer = Viewer(secret, "GG_APP_SOYOU_DATALAB_USER", "GENERAL")
    provider_calls = []

    def sql(query, params=None):
        if "CURRENT_USER" in query:
            rows = [{"VIEWER": viewer.user, "ACCESS_ROLE": viewer.role}]
        elif "SECONDARY" in query:
            rows = []
        else:
            provider_calls.append(params)
            rows = [{"RESPONSE": payload}]
        return SimpleNamespace(collect=lambda **kwargs: rows)

    options = dict(
        guardrail=SimpleNamespace(
            validate_input=lambda value: None, validate_output=validate_output
        ),
        diagnostic_hooks=[broken_exporter, events.append, log_diagnostic_event],
        hook_clock=itertools.count().__next__,
    )
    if agent:
        service = CortexAgentService(session=SimpleNamespace(sql=sql), viewer=viewer, **options)
    else:
        document = SourceDocument(secret, secret, secret)
        service = RagOrchestrator(
            retriever=SimpleNamespace(retrieve=lambda *args, **kwargs: [document, document]),
            generator=SimpleNamespace(
                generate=lambda **kwargs: GenerationResult(secret, "model", TokenUsage(), False)
            ),
            telemetry=SimpleNamespace(
                record_success=lambda **kwargs: None, record_failure=lambda **kwargs: None
            ),
            **options,
        )
    options["diagnostic_hooks"].clear()

    def callback(event):
        pass

    reference = weakref.ref(callback)
    with caplog.at_level(logging.INFO, logger="rag_chat.hooks"):
        for _ in range(2):
            with pytest.raises(GuardrailViolation) as caught:
                service.answer(question=secret, model=AGENT_MODEL, on_progress=callback)
            assert caught.value is error
            assert caught.value.args == (secret, 17)
        rejecting[0] = False
        assert service.answer(question=secret, model=AGENT_MODEL).content == secret
    # Release test-owned exception tracebacks before checking service retention.
    error.__traceback__ = None
    del caught
    del callback
    gc.collect()
    assert reference() is None
    assert [e.stage for e in events if isinstance(e, ErrorEvent)] == [
        OrchestrationStep.VALIDATE_OUTPUT,
        OrchestrationStep.VALIDATE_OUTPUT,
    ]
    assert [e.rule for e in events if isinstance(e, GuardrailRejectionEvent)] == [
        GuardrailRule.CUSTOM,
        GuardrailRule.CUSTOM,
    ]
    assert [e.succeeded for e in events if isinstance(e, TimingEvent) and e.stage is None] == [
        False,
        False,
        True,
    ]
    assert [e.usage for e in events if isinstance(e, TokenUsageEvent)] == [None] * 3
    assert [e for e in events if isinstance(e, SourcesEvent)] == [
        SourcesEvent(1, "cited") if agent else SourcesEvent(2, "retrieved"),
    ] * 3
    assert not agent or len(provider_calls) == 3
    assert secret not in repr(events)
    records = [r for r in caplog.records if r.name == "rag_chat.hooks"]
    assert records and secret not in repr([r.__dict__ for r in records])
    assert all(r.exc_info is None and r.stack_info is None for r in records)
