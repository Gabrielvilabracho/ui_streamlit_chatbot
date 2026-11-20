"""Application use case coordinating retrieval, generation, policy, and telemetry."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from rag_chat.application.hooks import HookDispatcher, ProgressHook
from rag_chat.application.hooks.diagnostics import (
    DEFAULT_DIAGNOSTIC_HOOKS,
    DiagnosticDispatcher,
    DiagnosticHook,
)
from rag_chat.application.hooks.events import SourcesEvent, TokenUsageEvent
from rag_chat.application.hooks.observer import HookObserver
from rag_chat.application.ports import Generator, Guardrail, Retriever, Telemetry
from rag_chat.domain.errors import RagTimeoutError
from rag_chat.domain.models import ChatMessage, OrchestrationStep, ProgressEvent, RagAnswer
from rag_chat.domain.prompts import build_rag_prompt


class RagOrchestrator:
    """Execute one grounded-answer request through injected ports."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        generator: Generator,
        guardrail: Guardrail,
        telemetry: Telemetry,
        retrieval_limit: int = 5,
        timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.perf_counter,
        hooks: Sequence[ProgressHook] = (),
        diagnostic_hooks: Sequence[DiagnosticHook] = DEFAULT_DIAGNOSTIC_HOOKS,
        hook_clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._guardrail = guardrail
        self._telemetry = telemetry
        self._retrieval_limit = retrieval_limit
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._hooks = HookDispatcher(hooks=tuple(hooks))
        self._diagnostics = DiagnosticDispatcher(hooks=tuple(diagnostic_hooks))
        self._hook_clock = hook_clock

    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        """Return a grounded answer or an application-safe expected failure."""
        observer = HookObserver(
            self._diagnostics, progress=self._hooks, on_progress=on_progress, clock=self._hook_clock
        )
        return observer.run(
            None,
            lambda: self._answer(
                question=question, model=model, history=history, observer=observer
            ),
            progress=False,
        )

    def _answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage],
        observer: HookObserver,
    ) -> RagAnswer:
        started_at = self._clock()
        try:
            observer.run(
                OrchestrationStep.VALIDATE_INPUT, lambda: self._guardrail.validate_input(question)
            )
            sources = observer.run(
                OrchestrationStep.RETRIEVE_CONTEXT,
                lambda: tuple(self._retriever.retrieve(question, limit=self._retrieval_limit)),
            )
            self._diagnostics.emit(SourcesEvent(len(sources), "retrieved"))
            prompt = build_rag_prompt(question=question, sources=sources, history=history)
            generation = observer.run(
                OrchestrationStep.GENERATE_ANSWER,
                lambda: self._generator.generate(
                    model=model, prompt=prompt, timeout_seconds=self._timeout_seconds
                ),
            )
            self._diagnostics.emit(
                TokenUsageEvent(generation.usage if generation.usage_reported else None)
            )
            observer.run(
                OrchestrationStep.VALIDATE_OUTPUT,
                lambda: self._guardrail.validate_output(generation.content),
            )
            answer = RagAnswer(
                content=generation.content,
                model=generation.model,
                sources=sources,
                usage=generation.usage,
                latency_ms=(self._clock() - started_at) * 1_000,
            )
            observer.run(
                OrchestrationStep.RECORD_TELEMETRY,
                lambda: self._telemetry.record_success(question=question, answer=answer),
            )
            return answer
        except (TimeoutError, RagTimeoutError) as error:
            timeout_error = (
                error
                if isinstance(error, RagTimeoutError)
                else RagTimeoutError("The RAG request timed out. Please retry.")
            )
            self._telemetry.record_failure(
                question=question,
                error=timeout_error,
                latency_ms=(self._clock() - started_at) * 1_000,
            )
            if timeout_error is error:
                raise
            raise timeout_error from error
        except Exception as error:
            self._telemetry.record_failure(
                question=question,
                error=error,
                latency_ms=(self._clock() - started_at) * 1_000,
            )
            raise
