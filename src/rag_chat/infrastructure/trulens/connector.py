"""Lazy TruLens connector construction using the application's Snowpark session."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast


def create_snowflake_connector(snowpark_session: Any) -> object:
    """Create a TruLens connector without duplicating Snowflake credentials."""

    module = importlib.import_module("trulens.connectors.snowflake")
    connector_type = cast(Callable[..., object], module.SnowflakeConnector)
    return connector_type(snowpark_session=snowpark_session)
