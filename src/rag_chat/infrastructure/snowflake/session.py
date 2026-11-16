"""Composition helpers that isolate optional Snowflake SDK imports."""

from __future__ import annotations

from typing import Any

from rag_chat.infrastructure.snowflake.settings import SnowflakeSettings


def create_snowpark_session(settings: SnowflakeSettings) -> Any:
    from snowflake.snowpark import Session

    return Session.builder.configs(settings.connection_parameters).create()


def get_cortex_search_service(session: Any, settings: SnowflakeSettings) -> Any:
    from snowflake.core import Root

    root = Root(session)
    return (
        root.databases[settings.database]
        .schemas[settings.schema]
        .cortex_search_services[settings.search_service]
    )
