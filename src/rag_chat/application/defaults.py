"""Safe local defaults that can be replaced through dependency injection."""

from __future__ import annotations

import logging

from rag_chat.application.guardrails import BaselineGuardrail as BaselineGuardrail
from rag_chat.domain.models import RagAnswer


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
