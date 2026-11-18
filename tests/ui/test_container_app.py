from streamlit.testing.v1 import AppTest


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
