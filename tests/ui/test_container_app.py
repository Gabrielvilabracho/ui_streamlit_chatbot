from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[2]


def test_container_entrypoint_never_falls_back_to_owner_credentials() -> None:
    with patch("streamlit.connection", side_effect=RuntimeError("private details")) as connection:
        app = AppTest.from_file(ROOT / "snowflake_app.py", default_timeout=10).run()
    assert not app.exception
    connection.assert_called_once_with("snowflake-callers-rights")
    assert app.chat_input[0].disabled
    assert not app.selectbox
    assert "private details" not in app.error[0].value


def test_agent_ui_hides_model_override_and_unreported_usage_and_clears_scope() -> None:
    script = """
import streamlit as st
from rag_chat.domain.models import RagAnswer, TokenUsage, SourceDocument
from rag_chat.ui.streamlit_app import run_app
class Service:
    def answer(self, *, question, model, history=(), on_progress=None):
        return RagAnswer("Answer [7]", model,
            (SourceDocument("d1", "Evidence", "Policy", citation_label="7"),),
            TokenUsage(), 1, usage_reported=False)
run_app(orchestrator_factory=Service, models=("Managed by Cortex Agent",),
    configuration_error=None, agent_mode=True,
    conversation_scope=st.session_state.get("test_scope", "viewer-general"))
"""
    app = AppTest.from_string(script, default_timeout=10).run()
    assert not app.exception
    assert not app.selectbox
    app.chat_input[0].set_value("Question").run()
    assert not app.exception
    assert any("[7] Policy" in item.value for item in app.markdown)
    assert any("Tokens unavailable" in item.value for item in app.caption)
    assert not any("Input 0" in item.value for item in app.html)
    app.session_state["test_scope"] = "viewer-privacy"
    app.run()
    assert not app.session_state["messages"]
    assert not any(item.value == "Answer [7]" for item in app.markdown)


def test_container_entrypoint_binds_factory_to_viewer_without_global_cache() -> None:
    from rag_chat.infrastructure.snowflake.cortex_agent import AGENT_MODEL

    session = Mock()
    session.sql.return_value.collect.return_value = [
        {"VIEWER": "alice", "ACCESS_ROLE": "GG_APP_SOYOU_DATALAB_USER"}
    ]
    connection = Mock()
    connection.session.return_value = session
    with patch("streamlit.connection", return_value=connection):
        app = AppTest.from_file(ROOT / "snowflake_app.py", default_timeout=10).run()
    assert not app.exception
    assert not app.error
    assert not app.chat_input[0].disabled
    assert not app.selectbox
    assert any(AGENT_MODEL in item.value for item in app.markdown)
    assert all("DATA_AGENT_RUN" not in call.args[0] for call in session.sql.call_args_list)


@pytest.mark.parametrize("identity_change", ["user", "policy", "denied", "failure"])
def test_container_clears_old_sources_on_identity_change(identity_change: str) -> None:
    """Retain the independent verifier's real-entrypoint isolation/retry probe."""
    import json

    user, role = "alice", "GG_APP_SOYOU_DATALAB_USER"
    fail = False
    requests: list[dict[str, object]] = []
    session = Mock()

    def query(sql, params=None):
        if fail:
            raise RuntimeError("private details")
        if "CURRENT_USER" in sql:
            rows = [{"VIEWER": user, "ACCESS_ROLE": role}]
        elif "DATA_AGENT_RUN" in sql:
            requests.append(json.loads(params[1]))
            rows = [
                {
                    "RESPONSE": json.dumps(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Evidence [0].",
                                    "annotations": [
                                        {
                                            "type": "cortex_search_citation",
                                            "index": 0,
                                            "doc_id": "42",
                                            "doc_title": "Policy",
                                            "text": "Trusted",
                                        }
                                    ],
                                }
                            ],
                        }
                    )
                }
            ]
        else:
            rows = []
        return Mock(collect=Mock(return_value=rows))

    session.sql.side_effect = query
    connection = Mock()
    connection.session.return_value = session
    with patch("streamlit.connection", return_value=connection) as connect:
        app = AppTest.from_file(ROOT / "snowflake_app.py", default_timeout=10).run()
        app.chat_input[0].set_value("Question").run()
        assert not app.exception
        assert len(app.get("status")) == 1
        assert any("[0] Policy" in item.value for item in app.markdown)
        next(button for button in app.button if button.label == "Retry").click().run()
        assert not app.exception
        assert len(requests) == 2
        assert len(requests[-1]["messages"]) == 1  # type: ignore[arg-type]
        if identity_change == "user":
            user = "bob"
        elif identity_change == "policy":
            role = "GG_APP_SOYOU_DATALAB_DPO"
        elif identity_change == "denied":
            role = "ACCOUNTADMIN"
        else:
            fail = True
        app.run()
        assert not app.exception
        assert not app.session_state["messages"]
        assert not any(
            "Evidence [0]." in item.value or "[0] Policy" in item.value for item in app.markdown
        )
        assert len(requests) == 2
        if identity_change in ("denied", "failure"):
            assert app.chat_input[0].disabled
            assert "private details" not in app.error[0].value
        assert all(call.args == ("snowflake-callers-rights",) for call in connect.call_args_list)
