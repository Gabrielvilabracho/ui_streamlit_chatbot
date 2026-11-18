"""Streamlit composition root for the Sof~IA RAG application."""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

import streamlit as st

from rag_chat.application.ports import AnswerService
from rag_chat.composition import build_orchestrator
from rag_chat.domain.errors import ConfigurationError
from rag_chat.infrastructure.snowflake.settings import SnowflakeSettings
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings
from rag_chat.ui.model_status import parse_model_context_limits
from rag_chat.ui.streamlit_app import OrchestratorFactory, run_app

DEFAULT_MODELS = ("llama3.3-70b", "mistral-large2", "snowflake-arctic")
BRAND_MARK = Path(__file__).resolve().parent / "static" / "brand" / "sofinco-mark.png"


@st.cache_resource(show_spinner=False)
def _cached_orchestrator(
    settings: SnowflakeSettings,
    observability_settings: ObservabilitySettings,
) -> AnswerService:
    return build_orchestrator(settings, observability_settings)


def _secret_values() -> Mapping[str, Any]:
    try:
        return st.secrets.to_dict()
    except Exception:
        return {}


st.set_page_config(
    page_title="Sof~IA Knowledge",
    page_icon=str(BRAND_MARK),
    layout="centered",
    initial_sidebar_state="expanded",
)

configuration_error: str | None = None
orchestrator_factory: OrchestratorFactory | None = None
user_identifier: str | None = None
access_role: str | None = None
secret_values = _secret_values()
try:
    snowflake_settings = SnowflakeSettings.from_sources(
        secrets=secret_values,
        environ=os.environ,
    )
except ConfigurationError as error:
    configuration_error = str(error)
else:
    try:
        observability_settings = ObservabilitySettings.from_sources(
            secrets=secret_values,
            environ=os.environ,
        )
    except ConfigurationError:
        observability_settings = ObservabilitySettings()
    orchestrator_factory = partial(
        _cached_orchestrator,
        snowflake_settings,
        observability_settings,
    )
    user_identifier = snowflake_settings.user
    access_role = snowflake_settings.role

configured_models = tuple(
    model.strip()
    for model in os.getenv("RAG_MODELS", ",".join(DEFAULT_MODELS)).split(",")
    if model.strip()
)

run_app(
    orchestrator_factory=orchestrator_factory,
    models=configured_models or DEFAULT_MODELS,
    configuration_error=configuration_error,
    user_identifier=user_identifier,
    access_role=access_role,
    model_context_limits=parse_model_context_limits(
        os.getenv("RAG_MODEL_CONTEXT_LIMITS", "")
    ),
)
