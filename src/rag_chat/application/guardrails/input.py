"""General question validation, independent of model providers."""

from dataclasses import dataclass

from rag_chat.domain.errors import GuardrailViolation


@dataclass(frozen=True, slots=True)
class InputGuardrail:
    max_characters: int = 8_000

    def validate(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise GuardrailViolation("The question cannot be empty.")
        if len(normalized) > self.max_characters:
            raise GuardrailViolation("The question is too long to process safely.")
