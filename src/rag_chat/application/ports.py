"""Dependency-inversion ports implemented by infrastructure adapters."""

from __future__ import annotations

from typing import Protocol

from rag_chat.domain.models import GenerationResult, RagAnswer, SourceDocument


class Retriever(Protocol):
    def retrieve(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]: ...


class Generator(Protocol):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout_seconds: float,
    ) -> GenerationResult: ...


class Guardrail(Protocol):
    def validate_input(self, value: str) -> None: ...

    def validate_output(self, value: str) -> None: ...


class Telemetry(Protocol):
    def record_success(self, *, question: str, answer: RagAnswer) -> None: ...

    def record_failure(
        self,
        *,
        question: str,
        error: Exception,
        latency_ms: float,
    ) -> None: ...
