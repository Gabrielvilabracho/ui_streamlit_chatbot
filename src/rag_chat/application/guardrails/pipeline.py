"""Compose general validators behind the existing Guardrail port."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from rag_chat.application.guardrails.input import InputGuardrail
from rag_chat.application.guardrails.output import OutputGuardrail

Validator = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class GuardrailPipeline:
    """Run each boundary's explicitly configured rules; stop at the first rejection."""

    input_rules: tuple[Validator, ...]
    output_rules: tuple[Validator, ...]

    def validate_input(self, value: str) -> None:
        for validate in self.input_rules:
            validate(value)

    def validate_output(self, value: str) -> None:
        for validate in self.output_rules:
            validate(value)


@dataclass(frozen=True, slots=True)
class BaselineGuardrail:
    """Keep the existing limits and API while composing reusable validators."""

    max_input_characters: int = 8_000
    max_output_characters: int = 32_000
    _pipeline: GuardrailPipeline = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_pipeline",
            GuardrailPipeline(
                input_rules=(InputGuardrail(self.max_input_characters).validate,),
                output_rules=(OutputGuardrail(self.max_output_characters).validate,),
            ),
        )

    def validate_input(self, value: str) -> None:
        self._pipeline.validate_input(value)

    def validate_output(self, value: str) -> None:
        self._pipeline.validate_output(value)
