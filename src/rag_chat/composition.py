"""Provider composition kept outside domain, application, and presentation code."""

from __future__ import annotations

from rag_chat.application.defaults import BaselineGuardrail, LoggingTelemetry
from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.infrastructure.snowflake.cortex_complete import CortexCompleteGenerator
from rag_chat.infrastructure.snowflake.cortex_search import CortexSearchRetriever
from rag_chat.infrastructure.snowflake.session import (
    create_snowpark_session,
    get_cortex_search_service,
)
from rag_chat.infrastructure.snowflake.settings import SnowflakeSettings


def build_orchestrator(settings: SnowflakeSettings) -> RagOrchestrator:
    """Construct the concrete runtime at the application's outermost boundary."""

    session = create_snowpark_session(settings)
    search_service = get_cortex_search_service(session, settings)
    return RagOrchestrator(
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
