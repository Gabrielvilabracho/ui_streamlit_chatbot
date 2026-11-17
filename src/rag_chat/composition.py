"""Provider composition kept outside domain, application, and presentation code."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from rag_chat.application.defaults import BaselineGuardrail, LoggingTelemetry
from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.application.ports import AnswerService
from rag_chat.infrastructure.snowflake.cortex_complete import CortexCompleteGenerator
from rag_chat.infrastructure.snowflake.cortex_search import CortexSearchRetriever
from rag_chat.infrastructure.snowflake.session import (
    create_snowpark_session,
    get_cortex_search_service,
)
from rag_chat.infrastructure.snowflake.settings import SnowflakeSettings
from rag_chat.infrastructure.trulens.instrumentation import create_trulens_service
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings

logger = logging.getLogger(__name__)


def build_orchestrator(
    settings: SnowflakeSettings,
    observability_settings: ObservabilitySettings | None = None,
) -> AnswerService:
    """Construct the concrete runtime at the application's outermost boundary."""

    session = create_snowpark_session(settings)
    search_service = get_cortex_search_service(session, settings)
    orchestrator = RagOrchestrator(
        retriever=CortexSearchRetriever(
            service=search_service,
            content_column=settings.content_column,
            id_column=settings.id_column,
            title_column=settings.title_column,
            uri_column=settings.uri_column,
        ),
        generator=CortexCompleteGenerator(session=session),
        guardrail=BaselineGuardrail(),
        telemetry=LoggingTelemetry(),
    )
    return with_observability(
        service=orchestrator,
        snowpark_session=session,
        settings=observability_settings or ObservabilitySettings(),
    )


def with_observability(
    *,
    service: AnswerService,
    snowpark_session: Any,
    settings: ObservabilitySettings,
    service_factory: Callable[..., AnswerService] = create_trulens_service,
) -> AnswerService:
    """Enable TruLens when configured without making chat depend on telemetry."""

    if not settings.enabled:
        return service
    try:
        return service_factory(
            delegate=service,
            snowpark_session=snowpark_session,
            settings=settings,
        )
    except Exception as error:
        logger.warning(
            "TruLens setup failed; continuing without observability (%s).",
            type(error).__name__,
        )
        return service
