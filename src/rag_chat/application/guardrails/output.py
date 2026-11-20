"""General answer validation, independent of model providers."""

from dataclasses import dataclass

from rag_chat.domain.errors import GuardrailViolation


@dataclass(frozen=True, slots=True)
class OutputGuardrail:
    max_characters: int = 32_000

    def validate(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise GuardrailViolation("The model returned an empty response.")
        if len(normalized) > self.max_characters:
            raise GuardrailViolation("The model response exceeded the safe output limit.")
