from __future__ import annotations

from types import SimpleNamespace

from rag_chat import composition
from rag_chat.application.defaults import BaselineGuardrail
from rag_chat.application.guardrails import GuardrailPipeline
from rag_chat.domain.models import GenerationResult, ProgressEvent, TokenUsage


def test_composition_wires_registered_hooks_and_guardrails(monkeypatch) -> None:
    monkeypatch.setattr(composition, "create_snowpark_session", lambda settings: object())
    monkeypatch.setattr(composition, "get_cortex_search_service", lambda *args: object())
    monkeypatch.setattr(
        composition,
        "CortexSearchRetriever",
        lambda **kwargs: SimpleNamespace(retrieve=lambda query, limit: ()),
    )
    monkeypatch.setattr(
        composition,
        "CortexCompleteGenerator",
        lambda **kwargs: SimpleNamespace(
            generate=lambda **args: GenerationResult("answer", "model", TokenUsage())
        ),
    )
    settings = SimpleNamespace(
        content_column="content",
        id_column="id",
        title_column="title",
        uri_column="uri",
    )
    calls = []
    registered: list[ProgressEvent] = []
    progress: list[ProgressEvent] = []
    diagnostics = []
    baseline = BaselineGuardrail()
    policy = GuardrailPipeline(
        input_rules=(baseline.validate_input, lambda value: calls.append(("input", value))),
        output_rules=(baseline.validate_output, lambda value: calls.append(("output", value))),
    )
    service = composition.build_orchestrator(
        settings,
        hooks=(registered.append,),
        guardrail=policy,
        diagnostic_hooks=(diagnostics.append,),
    )

    answer = service.answer(question="question", model="model", on_progress=progress.append)

    assert answer.content == "answer"
    assert calls == [("input", "question"), ("output", "answer")]
    assert registered == progress
    assert len(progress) == 10
    assert len(diagnostics) == 8
    default_service = composition.build_orchestrator(settings)
    assert default_service.answer(question="question", model="model").content == answer.content
