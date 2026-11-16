"""Secret-safe Snowflake configuration loading."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rag_chat.domain.errors import ConfigurationError

_REQUIRED_NAMES = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_SEARCH_SERVICE",
)


@dataclass(frozen=True, slots=True)
class SnowflakeSettings:
    account: str
    user: str
    password: str = field(repr=False)
    warehouse: str
    database: str
    schema: str
    search_service: str
    role: str | None = None
    content_column: str = "CHUNK"
    id_column: str = "CHUNK_ID"
    title_column: str = "TITLE"
    uri_column: str = "SOURCE_URL"

    @property
    def connection_parameters(self) -> dict[str, str]:
        parameters = {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
        }
        if self.role:
            parameters["role"] = self.role
        return parameters

    @classmethod
    def from_sources(
        cls,
        *,
        secrets: Mapping[str, Any],
        environ: Mapping[str, str] | None = None,
    ) -> SnowflakeSettings:
        environment = environ if environ is not None else os.environ
        nested = secrets.get("snowflake", {})
        nested_secrets = nested if isinstance(nested, Mapping) else {}

        def value(name: str, *, default: str | None = None) -> str | None:
            short_name = name.removeprefix("SNOWFLAKE_").lower()
            raw = nested_secrets.get(short_name, secrets.get(name, environment.get(name, default)))
            if raw is None:
                return None
            normalized = str(raw).strip()
            return normalized or None

        missing = [name for name in _REQUIRED_NAMES if value(name) is None]
        if missing:
            raise ConfigurationError(
                "Missing required Snowflake configuration: " + ", ".join(missing)
            )

        values = {name: value(name) for name in _REQUIRED_NAMES}
        return cls(
            account=_required(values["SNOWFLAKE_ACCOUNT"]),
            user=_required(values["SNOWFLAKE_USER"]),
            password=_required(values["SNOWFLAKE_PASSWORD"]),
            warehouse=_required(values["SNOWFLAKE_WAREHOUSE"]),
            database=_required(values["SNOWFLAKE_DATABASE"]),
            schema=_required(values["SNOWFLAKE_SCHEMA"]),
            search_service=_required(values["SNOWFLAKE_SEARCH_SERVICE"]),
            role=value("SNOWFLAKE_ROLE"),
            content_column=_required(value("SNOWFLAKE_CONTENT_COLUMN", default="CHUNK")),
            id_column=_required(value("SNOWFLAKE_ID_COLUMN", default="CHUNK_ID")),
            title_column=_required(value("SNOWFLAKE_TITLE_COLUMN", default="TITLE")),
            uri_column=_required(value("SNOWFLAKE_URI_COLUMN", default="SOURCE_URL")),
        )


def _required(value: str | None) -> str:
    if value is None:
        raise ConfigurationError("Required Snowflake configuration was empty.")
    return value
