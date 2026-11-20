"""TruLens tracing adapters for the existing provider-neutral RAG service."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol, TypeVar, cast

from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import GenAIAttributes, SpanAttributes

from rag_chat.application.guardrails.privacy import trace_text
from rag_chat.application.ports import AnswerService
from rag_chat.domain.models import (
    ChatMessage,
    GenerationResult,
    ProgressEvent,
    RagAnswer,
    SourceDocument,
)
from rag_chat.infrastructure.trulens.connector import create_snowflake_connector
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings

logger = logging.getLogger(__name__)
Result = TypeVar("Result")


class RecordingContext(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class FailureIsolatedRecording:
    """Keep tracing failures from changing or repeating application work."""

    def __init__(self, context: RecordingContext) -> None:
        self._context = context

    def invoke(self, operation: Callable[[], Result]) -> Result:
        try:
            self._context.__enter__()
        except Exception as error:
            _log_recording_failure("start", error)
            return operation()

        try:
            result = operation()
        except BaseException:
            exception_type, exception, traceback = sys.exc_info()
            try:
                self._context.__exit__(exception_type, exception, traceback)
            except Exception as recording_error:
                _log_recording_failure("finish after application failure", recording_error)
            raise

        try:
            self._context.__exit__(None, None, None)
        except Exception as error:
            _log_recording_failure("export", error)
        return result


class InstrumentedAnswerService:
    """Expose the existing application service as a TruLens record root."""

    def __init__(self, delegate: AnswerService) -> None:
        self._delegate = delegate

    @instrument(
        name="sofia.answer",
        attributes=lambda result, error, *_args, **kwargs: record_root_span_attributes(
            result, error, **kwargs
        ),
    )
    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        return self._delegate.answer(
            question=question,
            model=model,
            history=history,
            on_progress=on_progress,
        )


class RecordedAnswerService:
    """Open a failure-isolated recording around each instrumented request."""

    def __init__(
        self,
        *,
        app: InstrumentedAnswerService,
        recording: FailureIsolatedRecording,
    ) -> None:
        self._app = app
        self._recording = recording

    def answer(
        self,
        *,
        question: str,
        model: str,
        history: Sequence[ChatMessage] = (),
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RagAnswer:
        return cast(
            RagAnswer,
            self._recording.invoke(
                lambda: self._app.answer(
                    question=question,
                    model=model,
                    history=history,
                    on_progress=on_progress,
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class TruLensRuntime:
    """Keep the recording service and registered TruApp in one composition result."""

    service: AnswerService
    tru_app: Any


def create_trulens_service(
    *,
    delegate: AnswerService,
    snowpark_session: Any,
    settings: ObservabilitySettings,
    connector_factory: Callable[[Any], object] = create_snowflake_connector,
    session_factory: Callable[..., object] | None = None,
    recorder_factory: Callable[..., RecordingContext] | None = None,
) -> AnswerService:
    """Register and return the existing app through TruApp using one session."""

    return create_trulens_runtime(
        delegate=delegate,
        snowpark_session=snowpark_session,
        settings=settings,
        connector_factory=connector_factory,
        session_factory=session_factory,
        recorder_factory=recorder_factory,
    ).service


def create_trulens_runtime(
    *,
    delegate: AnswerService,
    snowpark_session: Any,
    settings: ObservabilitySettings,
    connector_factory: Callable[[Any], object] = create_snowflake_connector,
    session_factory: Callable[..., object] | None = None,
    recorder_factory: Callable[..., RecordingContext] | None = None,
) -> TruLensRuntime:
    """Register the app and expose its recorder for explicit offline evaluation."""

    connector = connector_factory(snowpark_session)
    session_builder = session_factory or _create_tru_session
    recorder_builder = recorder_factory or _create_tru_app
    tru_session = session_builder(connector=connector)
    app = InstrumentedAnswerService(delegate)
    recorder = recorder_builder(
        app,
        app_name=settings.app_name,
        app_version=settings.app_version,
        session=tru_session,
        main_method=app.answer,
    )
    return TruLensRuntime(
        service=RecordedAnswerService(
            app=app,
            recording=FailureIsolatedRecording(recorder),
        ),
        tru_app=recorder,
    )


def retrieval_span_attributes(
    result: tuple[SourceDocument, ...] | None,
    error: BaseException | None,
    *_args: object,
    **kwargs: object,
) -> dict[str, object]:
    del error
    documents = result or ()
    return {
        SpanAttributes.RETRIEVAL.QUERY_TEXT: trace_text(str(kwargs.get("query", ""))),
        SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: [
            trace_text(document.content) for document in documents
        ],
        SpanAttributes.RETRIEVAL.NUM_CONTEXTS: len(documents),
    }


def generation_span_attributes(
    result: GenerationResult | None,
    error: BaseException | None,
    *_args: object,
    **kwargs: object,
) -> dict[str, object]:
    del error
    requested_model = str(kwargs.get("model", ""))
    model = result.model if result else requested_model
    usage = result.usage if result and result.usage_reported else None
    return {
        SpanAttributes.COST.MODEL: model,
        SpanAttributes.COST.NUM_PROMPT_TOKENS: usage.prompt_tokens if usage else None,
        SpanAttributes.COST.NUM_COMPLETION_TOKENS: usage.completion_tokens if usage else None,
        SpanAttributes.COST.NUM_TOKENS: usage.total_tokens if usage else None,
        GenAIAttributes.SYSTEM.NAME: "snowflake",
        GenAIAttributes.OPERATION.NAME: "text_completion",
        "prompt": trace_text(str(kwargs.get("prompt", ""))),
        "output": trace_text(result.content) if result else "",
    }


def record_root_span_attributes(
    result: RagAnswer | None,
    error: BaseException | None,
    *_args: object,
    **kwargs: object,
) -> dict[str, object]:
    attributes: dict[str, object] = {
        SpanAttributes.RECORD_ROOT.INPUT: trace_text(str(kwargs.get("question", ""))),
        SpanAttributes.COST.MODEL: result.model if result else str(kwargs.get("model", "")),
    }
    if result:
        attributes[SpanAttributes.RECORD_ROOT.OUTPUT] = trace_text(result.content)
    if error:
        attributes[SpanAttributes.RECORD_ROOT.ERROR] = type(error).__name__
    return attributes


def _create_tru_session(*, connector: object) -> object:
    from trulens.core import TruSession

    return TruSession(connector=cast(Any, connector))


def _create_tru_app(app: object, **kwargs: object) -> RecordingContext:
    from trulens.apps.app import TruApp

    return cast(RecordingContext, TruApp(app, **cast(Any, kwargs)))


def _log_recording_failure(stage: str, error: BaseException) -> None:
    logger.warning(
        "TruLens recording could not %s; continuing without telemetry (%s).",
        stage,
        type(error).__name__,
    )
