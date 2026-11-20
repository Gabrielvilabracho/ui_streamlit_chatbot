"""Application use case coordinating retrieval, generation, policy, and telemetry."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from rag_chat.application.hooks import HookDispatcher, ProgressHook
from rag_chat.application.ports import Generator, Guardrail, Retriever, Telemetry
from rag_chat.domain.errors import RagTimeoutError
from rag_chat.domain.models import (
    ChatMessage,
    OrchestrationStep,
    ProgressEvent,
    ProgressState,
    RagAnswer,
)
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
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._guardrail = guardrail
        self._telemetry = telemetry
        self._retrieval_limit = retrieval_limit
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._hooks = HookDispatcher(hooks=tuple(hooks))

    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        """Return a grounded answer or an application-safe expected failure."""

        started_at = self._clock()

        def mark(step: OrchestrationStep, state: ProgressState) -> None:
            self._hooks.emit(ProgressEvent(step=step, state=state), on_progress=on_progress)

        try:
            mark(OrchestrationStep.VALIDATE_INPUT, ProgressState.STARTED)
            self._guardrail.validate_input(question)
            mark(OrchestrationStep.VALIDATE_INPUT, ProgressState.COMPLETED)

            mark(OrchestrationStep.RETRIEVE_CONTEXT, ProgressState.STARTED)
            sources = tuple(
                self._retriever.retrieve(question, limit=self._retrieval_limit)
            )
            mark(OrchestrationStep.RETRIEVE_CONTEXT, ProgressState.COMPLETED)

            prompt = build_rag_prompt(question=question, sources=sources, history=history)
            mark(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED)
            generation = self._generator.generate(
                model=model,
                prompt=prompt,
                timeout_seconds=self._timeout_seconds,
            )
            mark(OrchestrationStep.GENERATE_ANSWER, ProgressState.COMPLETED)

            mark(OrchestrationStep.VALIDATE_OUTPUT, ProgressState.STARTED)
            self._guardrail.validate_output(generation.content)
            mark(OrchestrationStep.VALIDATE_OUTPUT, ProgressState.COMPLETED)

            answer = RagAnswer(
                content=generation.content,
                model=generation.model,
                sources=sources,
                usage=generation.usage,
                latency_ms=(self._clock() - started_at) * 1_000,
            )
            mark(OrchestrationStep.RECORD_TELEMETRY, ProgressState.STARTED)
            self._telemetry.record_success(question=question, answer=answer)
            mark(OrchestrationStep.RECORD_TELEMETRY, ProgressState.COMPLETED)
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
