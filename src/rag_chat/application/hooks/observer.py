"""Request-local observation of real operations, without retaining request content."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from rag_chat.application.hooks.diagnostics import DiagnosticDispatcher
from rag_chat.application.hooks.dispatcher import HookDispatcher
from rag_chat.application.hooks.events import (
    ErrorCategory,
    ErrorEvent,
    GuardrailRejectionEvent,
    HookStage,
    TimingEvent,
)
from rag_chat.application.hooks.progress import ProgressHook
from rag_chat.domain.errors import (
    ConfigurationError,
    GuardrailRule,
    GuardrailViolation,
    ProviderResponseError,
    RagTimeoutError,
)
from rag_chat.domain.models import OrchestrationStep, ProgressEvent, ProgressState

Result = TypeVar("Result")


class HookObserver:
    def __init__(
        self,
        diagnostics: DiagnosticDispatcher,
        *,
        progress: HookDispatcher | None = None,
        on_progress: ProgressHook | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.diagnostics = diagnostics
        self._progress = progress if progress is not None else HookDispatcher()
        self._on_progress = on_progress
        self._clock = clock
        self._failure_recorded = False

    def run(
        self, stage: HookStage, operation: Callable[[], Result], *, progress: bool = True
    ) -> Result:
        started = self._clock()
        succeeded = False
        try:
            if progress and isinstance(stage, OrchestrationStep):
                self._progress.emit(
                    ProgressEvent(stage, ProgressState.STARTED), on_progress=self._on_progress
                )
            result = operation()
            if progress and isinstance(stage, OrchestrationStep):
                self._progress.emit(
                    ProgressEvent(stage, ProgressState.COMPLETED), on_progress=self._on_progress
                )
            succeeded = True
            return result
        except Exception as error:
            if not self._failure_recorded:
                self._failure_recorded = True
                if isinstance(error, GuardrailViolation):
                    rule = (
                        error.rule
                        if isinstance(error.rule, GuardrailRule)
                        else GuardrailRule.CUSTOM
                    )
                    self.diagnostics.emit(GuardrailRejectionEvent(stage, rule))
                self.diagnostics.emit(ErrorEvent(stage, _category(error)))
            raise
        finally:
            self.diagnostics.emit(
                TimingEvent(stage, max(0.0, (self._clock() - started) * 1000), succeeded)
            )


def _category(error: Exception) -> ErrorCategory:
    if isinstance(error, GuardrailViolation):
        return "guardrail"
    if isinstance(error, (TimeoutError, RagTimeoutError)):
        return "timeout"
    if isinstance(error, ConfigurationError):
        return "configuration"
    if isinstance(error, ProviderResponseError):
        return "provider"
    return "unexpected"
