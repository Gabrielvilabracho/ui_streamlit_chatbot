from __future__ import annotations

import pytest

from rag_chat.domain.errors import ConfigurationError
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings


def test_observability_is_disabled_by_default() -> None:
    settings = ObservabilitySettings.from_sources(secrets={}, environ={})

    assert settings.enabled is False
    assert settings.app_name == "SOFIA_RAG"
    assert settings.app_version == "v1"


def test_observability_settings_load_nested_streamlit_secrets() -> None:
    settings = ObservabilitySettings.from_sources(
        secrets={
            "trulens": {
                "enabled": True,
                "app_name": "SOFIA_CUSTOM_RAG",
                "app_version": "release-7",
            }
        },
        environ={"TRULENS_APP_NAME": "ignored-environment-name"},
    )

    assert settings.enabled is True
    assert settings.app_name == "SOFIA_CUSTOM_RAG"
    assert settings.app_version == "release-7"


def test_observability_settings_reject_ambiguous_boolean_values() -> None:
    with pytest.raises(ConfigurationError, match="TRULENS_ENABLED"):
        ObservabilitySettings.from_sources(
            secrets={},
            environ={"TRULENS_ENABLED": "sometimes"},
        )
