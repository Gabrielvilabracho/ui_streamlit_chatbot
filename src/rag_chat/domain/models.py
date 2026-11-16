"""Immutable domain values used by the RAG workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A message included in conversational context."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """A retrieved knowledge chunk and its citation metadata."""

    document_id: str
    content: str
    title: str
    uri: str | None = None
    score: float | None = None


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Input and output token counts reported by the model provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Provider-neutral model output."""

    content: str
    model: str
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class RagAnswer:
    """A grounded answer returned to the presentation layer."""

    content: str
    model: str
    sources: tuple[SourceDocument, ...]
    usage: TokenUsage
    latency_ms: float


class OrchestrationStep(StrEnum):
    """Stable workflow steps exposed to progress presenters and telemetry."""

    VALIDATE_INPUT = "Validate request"
    RETRIEVE_CONTEXT = "Retrieve trusted context"
    GENERATE_ANSWER = "Generate grounded answer"
    VALIDATE_OUTPUT = "Apply response guardrails"
    RECORD_TELEMETRY = "Record observability data"
