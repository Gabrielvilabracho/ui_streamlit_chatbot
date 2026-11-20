"""Allowlisted diagnostic metadata; never exception text or request content."""

import logging

from rag_chat.application.hooks.events import (
    DiagnosticEvent,
    ErrorEvent,
    SourcesEvent,
    TimingEvent,
    TokenUsageEvent,
)

logger = logging.getLogger("rag_chat.hooks")


def log_diagnostic_event(event: DiagnosticEvent) -> None:
    fields: dict[str, object]
    if isinstance(event, ErrorEvent):
        fields = {"hook_event": "error", "stage": event.stage, "error_category": event.category}
    elif isinstance(event, TimingEvent):
        fields = {
            "hook_event": "timing",
            "stage": event.stage,
            "duration_ms": event.duration_ms,
            "succeeded": event.succeeded,
        }
    elif isinstance(event, TokenUsageEvent):
        fields = {
            "hook_event": "tokens",
            "usage_reported": event.usage is not None,
            "prompt_tokens": event.usage.prompt_tokens if event.usage is not None else None,
            "completion_tokens": event.usage.completion_tokens if event.usage is not None else None,
        }
    elif isinstance(event, SourcesEvent):
        fields = {"hook_event": "sources", "source_count": event.count, "source_kind": event.kind}
    else:
        fields = {
            "hook_event": "guardrail_rejection",
            "stage": event.stage,
            "rule": event.rule.value,
        }
    logger.info("rag_hook_event", extra=fields)
