import hashlib

import pytest
from streamlit.testing.v1 import AppTest

from rag_chat.application.guardrails.privacy import protect_text
from rag_chat.domain.models import SourceDocument
from rag_chat.ui.state import UiMessage


@pytest.mark.parametrize("raw", ["DNI 12345678Z", "NIE X1234567L", "passport ABC123456"])
def test_identity_label_is_stable(raw):
    protected = protect_text(raw)
    assert protected == "[IDENTITY]"
    assert protect_text(protected) == protected


def test_identity_verification_is_not_an_identifier():
    value = "Explain identity verification"
    assert protect_text(value) == value


def test_rejected_secret_preserves_protected_conversation():
    script = """
from rag_chat.ui.streamlit_app import run_app
class NeverCalled:
    def answer(self, **kwargs):
        raise AssertionError("Rejected input reached the service")
run_app(orchestrator_factory=NeverCalled, models=("m",), configuration_error=None)
"""
    app = AppTest.from_string(script, default_timeout=15).run()
    app.session_state["messages"] = [
        UiMessage(
            "a",
            "assistant",
            "Evidence [1]",
            prompt="Policy?",
            sources=(SourceDocument("doc", "Evidence", "DNI 12345678Z"),),
        )
    ]
    app.run()
    before = hashlib.sha256(repr(app.session_state["messages"]).encode()).hexdigest()
    app.chat_input[0].set_value("password=canary-secret").run()
    assert not app.exception
    assert app.error[0].value == "Detected credentials or secrets; remove them before continuing."
    after = hashlib.sha256(repr(app.session_state["messages"]).encode()).hexdigest()
    assert after == before
