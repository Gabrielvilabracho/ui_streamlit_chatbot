from __future__ import annotations

import pytest

from rag_chat.domain.errors import ConfigurationError
from rag_chat.infrastructure.snowflake.settings import SnowflakeSettings


def test_settings_load_nested_streamlit_secrets_without_exposing_password() -> None:
    settings = SnowflakeSettings.from_sources(
        secrets={
            "snowflake": {
                "account": "org-account",
                "user": "rag_user",
                "password": "very-secret",
                "warehouse": "RAG_WH",
                "database": "CONTAVIA",
                "schema": "KNOWLEDGE",
                "role": "RAG_APP_ROLE",
                "search_service": "DOCUMENT_SEARCH",
            }
        },
        environ={"SNOWFLAKE_ACCOUNT": "ignored-environment-account"},
    )

    assert settings.account == "org-account"
    assert settings.search_service == "DOCUMENT_SEARCH"
    assert settings.connection_parameters["password"] == "very-secret"
    assert "very-secret" not in repr(settings)


def test_settings_report_missing_names_without_echoing_secret_values() -> None:
    with pytest.raises(ConfigurationError, match="SNOWFLAKE_DATABASE") as error:
        SnowflakeSettings.from_sources(
            secrets={},
            environ={
                "SNOWFLAKE_ACCOUNT": "org-account",
                "SNOWFLAKE_USER": "rag_user",
                "SNOWFLAKE_PASSWORD": "must-not-leak",
            },
        )

    assert "must-not-leak" not in str(error.value)
