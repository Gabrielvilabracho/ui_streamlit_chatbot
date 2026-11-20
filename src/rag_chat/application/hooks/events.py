"""Content-free diagnostic events, separate from legacy UI progress events."""

from dataclasses import dataclass
from typing import Literal, TypeAlias

from rag_chat.domain.errors import GuardrailRule
from rag_chat.domain.models import OrchestrationStep, TokenUsage

HookStage: TypeAlias = OrchestrationStep | Literal["Validate model", "Verify identity"] | None
ErrorCategory: TypeAlias = Literal[
    "guardrail", "timeout", "configuration", "provider", "unexpected"
]


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    stage: HookStage
    category: ErrorCategory


@dataclass(frozen=True, slots=True)
class TimingEvent:
    stage: HookStage
    duration_ms: float
    succeeded: bool


@dataclass(frozen=True, slots=True)
class TokenUsageEvent:
    usage: TokenUsage | None


@dataclass(frozen=True, slots=True)
class SourcesEvent:
    count: int
    kind: Literal["retrieved", "cited"]


@dataclass(frozen=True, slots=True)
class GuardrailRejectionEvent:
    stage: HookStage
    rule: GuardrailRule


DiagnosticEvent: TypeAlias = (
    ErrorEvent | TimingEvent | TokenUsageEvent | SourcesEvent | GuardrailRejectionEvent
)
