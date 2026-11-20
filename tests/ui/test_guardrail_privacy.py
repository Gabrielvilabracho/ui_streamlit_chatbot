from streamlit.testing.v1 import AppTest

SCRIPT = """
import streamlit as st
from rag_chat.domain.models import RagAnswer, SourceDocument, TokenUsage
from rag_chat.ui.streamlit_app import run_app
class Service:
    def answer(self, *, question, model, history=(), on_progress=None):
        st.session_state['received'] = (question, history)
        return RagAnswer('Contact reply@example.org [1].', model,
            (SourceDocument('doc', 'Call +34 612 345 678', 'reply@example.org'),),
            TokenUsage(), 1)
run_app(orchestrator_factory=Service, models=('test',), configuration_error=None)
"""


def test_input_is_protected_before_storage_display_and_service_invocation():
    app = AppTest.from_string(SCRIPT, default_timeout=10).run()
    app.chat_input[0].set_value("Contact person@example.org").run()
    assert not app.exception
    assert "person@example.org" not in repr(app.session_state["messages"])
    assert "person@example.org" not in repr(app.session_state["received"])
    assert "reply@example.org" not in repr(app.session_state["messages"])
    assert "+34 612 345 678" not in repr(app.session_state["messages"])
    assert all("person@example.org" not in item.value for item in app.markdown)


def test_rejected_secret_is_never_added_to_application_history_or_sent():
    app = AppTest.from_string(SCRIPT, default_timeout=10).run()
    app.chat_input[0].set_value("password=hunter2").run()
    assert not app.exception
    assert app.session_state["messages"] == []
    assert "received" not in app.session_state
    assert app.error and "hunter2" not in app.error[0].value


def test_old_history_is_protected_before_rendering_and_retry():
    from rag_chat.ui.state import UiMessage

    app = AppTest.from_string(SCRIPT, default_timeout=10).run()
    app.session_state["messages"] = [
        UiMessage("u", "user", "person@example.org"),
        UiMessage("a", "assistant", "password=hunter2", prompt="password=hunter2"),
    ]
    app.run()
    assert not app.exception
    assert "person@example.org" not in repr(app.session_state["messages"])
    assert "hunter2" not in repr(app.session_state["messages"])
    assert all("hunter2" not in item.value for item in app.markdown)
