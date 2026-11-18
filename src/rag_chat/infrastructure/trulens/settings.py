"""Configuration for opt-in Snowflake AI Observability recording."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rag_chat.domain.errors import ConfigurationError

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    """Non-secret identifiers controlling optional TruLens recording."""

    enabled: bool = False
    app_name: str = "SOFIA_RAG"
    app_version: str = "v1"

    @classmethod
    def from_sources(
        cls,
        *,
        secrets: Mapping[str, Any],
        environ: Mapping[str, str] | None = None,
    ) -> ObservabilitySettings:
        environment = environ if environ is not None else os.environ
        nested = secrets.get("trulens", {})
        nested_secrets = nested if isinstance(nested, Mapping) else {}

        def value(name: str, *, default: str | bool) -> object:
            short_name = name.removeprefix("TRULENS_").lower()
            return nested_secrets.get(short_name, secrets.get(name, environment.get(name, default)))

        return cls(
            enabled=_parse_boolean(value("TRULENS_ENABLED", default=False)),
            app_name=_non_empty_text(
                value("TRULENS_APP_NAME", default="SOFIA_RAG"),
                name="TRULENS_APP_NAME",
            ),
            app_version=_non_empty_text(
                value("TRULENS_APP_VERSION", default="v1"),
                name="TRULENS_APP_VERSION",
            ),
        )


def _parse_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(
        "TRULENS_ENABLED must be one of: true, false, 1, 0, yes, no, on, off."
    )


def _non_empty_text(value: object, *, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ConfigurationError(f"{name} must not be empty.")
    return normalized
