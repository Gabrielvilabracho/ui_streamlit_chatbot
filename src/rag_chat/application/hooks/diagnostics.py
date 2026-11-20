"""Failure-isolated diagnostic dispatch; progress callback semantics stay unchanged."""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

from rag_chat.application.hooks.events import DiagnosticEvent
from rag_chat.application.hooks.logging import log_diagnostic_event, logger

DiagnosticHook = Callable[[DiagnosticEvent], None]
DEFAULT_DIAGNOSTIC_HOOKS: tuple[DiagnosticHook, ...] = (log_diagnostic_event,)


@dataclass(frozen=True, slots=True)
class DiagnosticDispatcher:
    hooks: tuple[DiagnosticHook, ...] = DEFAULT_DIAGNOSTIC_HOOKS

    def emit(self, event: DiagnosticEvent) -> None:
        for hook in self.hooks:
            try:
                hook(event)
            except Exception:
                # A failing exporter must neither mask the primary error nor reveal its text.
                with suppress(Exception):
                    logger.warning("diagnostic_hook_failed")
