"""Snowsight container entrypoint. Never use the local password/owner connection."""

from functools import partial
from pathlib import Path

import streamlit as st

from rag_chat.domain.errors import RagError
from rag_chat.infrastructure.snowflake.cortex_agent import (
    AGENT_MODEL,
    CortexAgentService,
    identify_viewer,
)
from rag_chat.ui.streamlit_app import OrchestratorFactory, run_app

st.set_page_config(
    page_title="Sof~IA Knowledge",
    page_icon=str(Path(__file__).parent / "static" / "brand" / "sofinco-mark.png"),
    layout="centered",
    initial_sidebar_state="expanded",
)

# Execute during each script run, not at import-time in a shared module or global cache.
# The viewer token is short-lived; obtain this connection before rendering any page.
factory: OrchestratorFactory | None = None
configuration_error: str | None = None
user_identifier: str | None = None
access_role: str | None = None
scope = "container:unavailable"
try:
    connection = st.connection("snowflake-callers-rights")
    caller_session = connection.session()
    viewer = identify_viewer(caller_session)
    factory = partial(CortexAgentService, session=caller_session, viewer=viewer)
    user_identifier, access_role = viewer.user, viewer.role
    scope = repr(("container", viewer.user, viewer.role, viewer.agent))
except RagError as error:
    configuration_error = str(error)
except Exception:
    configuration_error = (
        "A Snowflake container runtime with restricted caller's rights is required. "
        "Check caller grants and reopen the app. Owner execution is not used as a fallback."
    )

run_app(
    orchestrator_factory=factory,
    models=(AGENT_MODEL,),
    configuration_error=configuration_error,
    user_identifier=user_identifier,
    access_role=access_role,
    agent_mode=True,
    conversation_scope=scope,
)
