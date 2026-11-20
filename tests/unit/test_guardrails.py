from __future__ import annotations

import pytest

from rag_chat.application.defaults import BaselineGuardrail as LegacyGuardrail
from rag_chat.application.guardrails import BaselineGuardrail, GuardrailPipeline
from rag_chat.application.guardrails.input import InputGuardrail
from rag_chat.application.guardrails.output import OutputGuardrail
from rag_chat.domain.errors import GuardrailViolation


@pytest.mark.parametrize(
    "direction,value,message",
    [
        ("input", "", "The question cannot be empty."),
        ("input", " \n ", "The question cannot be empty."),
        ("input", "x" * 8_001, "The question is too long to process safely."),
        ("output", "", "The model returned an empty response."),
        ("output", " \n ", "The model returned an empty response."),
        ("output", "x" * 32_001, "The model response exceeded the safe output limit."),
    ],
)
def test_baseline_preserves_rejections(direction: str, value: str, message: str) -> None:
    with pytest.raises(GuardrailViolation) as caught:
        getattr(BaselineGuardrail(), f"validate_{direction}")(value)
    assert str(caught.value) == message


def test_baseline_preserves_limits_normalization_and_old_import() -> None:
    assert LegacyGuardrail is BaselineGuardrail
    baseline = BaselineGuardrail()
    baseline.validate_input(" " + "x" * 8_000 + " ")
    baseline.validate_output(" " + "x" * 32_000 + " ")
    custom = BaselineGuardrail(max_input_characters=1, max_output_characters=2)
    custom.validate_input(" x ")
    custom.validate_output(" xx ")
    for validate, value in [(custom.validate_input, "xx"), (custom.validate_output, "xxx")]:
        with pytest.raises(GuardrailViolation):
            validate(value)


def test_pipeline_runs_only_matching_rules_in_order_and_stops_on_rejection() -> None:
    calls = []
    pipeline = GuardrailPipeline(
        input_rules=(InputGuardrail(max_characters=2).validate, calls.append),
        output_rules=(OutputGuardrail(max_characters=3).validate, calls.append),
    )
    pipeline.validate_input("ok")
    pipeline.validate_output("yes")
    assert calls == ["ok", "yes"]
    for validate, value in [(pipeline.validate_input, "bad"), (pipeline.validate_output, "long")]:
        with pytest.raises(GuardrailViolation):
            validate(value)
    assert calls == ["ok", "yes"]
