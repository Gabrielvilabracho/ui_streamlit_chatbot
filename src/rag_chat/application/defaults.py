"""Safe local defaults that can be replaced through dependency injection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rag_chat.domain.errors import GuardrailViolation
from rag_chat.domain.models import RagAnswer


@dataclass(frozen=True, slots=True)
class BaselineGuardrail:
    """Reject empty or excessively large values before provider calls."""

    max_input_characters: int = 8_000
    max_output_characters: int = 32_000

    def validate_input(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise GuardrailViolation("The question cannot be empty.")
        if len(normalized) > self.max_input_characters:
            raise GuardrailViolation("The question is too long to process safely.")

    def validate_output(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise GuardrailViolation("The model returned an empty response.")
        if len(normalized) > self.max_output_characters:
            raise GuardrailViolation("The model response exceeded the safe output limit.")


class LoggingTelemetry:
    """Log request metadata without recording prompts, answers, or credentials."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("rag_chat.telemetry")

    def record_success(self, *, question: str, answer: RagAnswer) -> None:
        self._logger.info(
            "rag_request_completed",
            extra={
                "model": answer.model,
                "source_count": len(answer.sources),
                "prompt_tokens": answer.usage.prompt_tokens,
                "completion_tokens": answer.usage.completion_tokens,
                "latency_ms": answer.latency_ms,
                "question_length": len(question),
            },
        )

    def record_failure(
        self,
        *,
        question: str,
        error: Exception,
        latency_ms: float,
    ) -> None:
        self._logger.warning(
            "rag_request_failed",
            extra={
                "error_type": type(error).__name__,
                "latency_ms": latency_ms,
                "question_length": len(question),
            },
        )
