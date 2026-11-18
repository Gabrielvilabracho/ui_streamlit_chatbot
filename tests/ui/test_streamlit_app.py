from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parents[2]


def test_root_app_renders_onboarding_and_safe_configuration_error() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10).run()

    assert not app.exception
    assert app.title[0].value == "Ask Sof~IA"
    assert len(app.get("image")) == 2
    assert app.get("image")[0].proto.imgs[0].alt == "Sofinco mark"
    assert app.sidebar.get("image")[0].proto.imgs[0].alt == "Sofinco wordmark"
    assert app.selectbox(key="model_selector").value
    assert "Snowflake configuration" in app.error[0].value
    assert app.chat_input[0].disabled is True


def test_invalid_optional_trulens_configuration_does_not_disable_chat(
    monkeypatch,
) -> None:
    for name in (
        "ACCOUNT",
        "USER",
        "PASSWORD",
        "WAREHOUSE",
        "DATABASE",
        "SCHEMA",
        "SEARCH_SERVICE",
    ):
        monkeypatch.setenv(f"SNOWFLAKE_{name}", "test")
    monkeypatch.setenv("TRULENS_ENABLED", "malformed")

    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10).run()

    assert not app.exception
    assert not app.error
    assert app.chat_input[0].disabled is False


def test_fake_chat_flow_renders_checklist_sources_controls_and_metrics() -> None:
    def fake_app() -> None:
        from rag_chat.domain.models import (
            OrchestrationStep,
            ProgressEvent,
            ProgressState,
            RagAnswer,
            SourceDocument,
            TokenUsage,
        )
        from rag_chat.ui.streamlit_app import run_app

        class FakeOrchestrator:
            def answer(self, *, question, model, history=(), on_progress=None):
                del history
                if on_progress:
                    for step in OrchestrationStep:
                        on_progress(ProgressEvent(step=step, state=ProgressState.STARTED))
                        on_progress(ProgressEvent(step=step, state=ProgressState.COMPLETED))
                return RagAnswer(
                    content="Grounded answer [1].",
                    model=model,
                    sources=(
                        SourceDocument(
                            document_id="source-1",
                            content="Trusted source content.",
                            title="Source title",
                            uri="https://docs.example.test/source-1",
                        ),
                    ),
                    usage=TokenUsage(prompt_tokens=20, completion_tokens=5),
                    latency_ms=125.0,
                )

        run_app(
            orchestrator_factory=FakeOrchestrator,
            models=("test-model",),
            configuration_error=None,
            user_identifier="rag_user",
            access_role="RAG_APP_ROLE",
            model_context_limits={"test-model": 100},
        )

    app = AppTest.from_function(fake_app, default_timeout=10).run()
    app.chat_input[0].set_value("What does the source say?").run(timeout=10)

    assert not app.exception
    assert any(item.value == "Grounded answer [1]." for item in app.markdown)
    assert any("Source title" in item.value for item in app.markdown)
    assert any("Source title" in item.value for item in app.sidebar.markdown)
    assert any("rag\\_user" in item.value for item in app.sidebar.markdown)
    assert any("RAG_APP_ROLE" in item.value for item in app.sidebar.markdown)
    assert app.sidebar.get("image")[0].proto.imgs[0].alt == "Sofinco wordmark"
    assert len(app.get("status")) == 5
    status_labels = [item.value for item in app.markdown]
    assert any("Last response · Input 20 / Output 5" in label for label in status_labels)
    assert any("Context · 25 / 100 (25.0%)" in label for label in status_labels)
    assert len(app.feedback) == 1
    assert any(item.label == "Retry" for item in app.button)
    html_values = [item.value for item in app.html]
    assert any("Input 20" in value and "Output 5" in value for value in html_values)


def test_retry_replaces_answer_without_duplicate_widget_keys() -> None:
    script = """
from rag_chat.domain.models import RagAnswer, TokenUsage
from rag_chat.ui.streamlit_app import run_app

class FakeOrchestrator:
    def answer(self, *, question, model, history=(), on_progress=None):
        return RagAnswer(
            content="Grounded answer.",
            model=model,
            sources=(),
            usage=TokenUsage(),
            latency_ms=1,
        )

run_app(
    orchestrator_factory=FakeOrchestrator,
    models=("test-model",),
    configuration_error=None,
)
"""
    app = AppTest.from_string(script, default_timeout=10).run()
    app.chat_input(key="chat_prompt").set_value("Question").run()
    assert not app.exception

    next(button for button in app.button if button.label == "Retry").click().run()

    assert not app.exception
    assert sum(item.value == "Grounded answer." for item in app.markdown) == 1
    assert len(app.feedback) == 1


def test_timeout_keeps_the_active_generation_stage_visible() -> None:
    script = """
from rag_chat.domain.errors import RagTimeoutError
from rag_chat.domain.models import OrchestrationStep, ProgressEvent, ProgressState
from rag_chat.ui.streamlit_app import run_app

class FakeOrchestrator:
    def answer(self, *, question, model, history=(), on_progress=None):
        for step in (
            OrchestrationStep.VALIDATE_INPUT,
            OrchestrationStep.RETRIEVE_CONTEXT,
        ):
            on_progress(ProgressEvent(step, ProgressState.STARTED))
            on_progress(ProgressEvent(step, ProgressState.COMPLETED))
        on_progress(ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED))
        raise RagTimeoutError("timed out")

run_app(
    orchestrator_factory=FakeOrchestrator,
    models=("test-model",),
    configuration_error=None,
)
"""
    app = AppTest.from_string(script, default_timeout=10).run()
    app.chat_input(key="chat_prompt").set_value("Question").run()

    statuses = app.get("status")
    assert statuses[-1].label == "Generate grounded answer interrupted"
    assert statuses[-1].state == "error"
    assert app.error[0].title == "Request timed out"


def test_retry_shows_real_replacement_completion() -> None:
    script = """
import streamlit as st
from rag_chat.domain.models import (
    OrchestrationStep,
    ProgressEvent,
    ProgressState,
    RagAnswer,
    TokenUsage,
)
from rag_chat.ui.state import UiMessage
from rag_chat.ui.streamlit_app import _generate_answer

class FakeOrchestrator:
    def answer(self, *, question, model, history=(), on_progress=None):
        for step in OrchestrationStep:
            on_progress(ProgressEvent(step, ProgressState.STARTED))
            on_progress(ProgressEvent(step, ProgressState.COMPLETED))
        return RagAnswer("Replacement answer.", model, (), TokenUsage(), 1)

st.session_state.messages = [
    UiMessage(message_id="user-1", role="user", content="Question"),
    UiMessage(
        message_id="assistant-1",
        role="assistant",
        content="Original answer.",
        prompt="Question",
        model="test-model",
    ),
]
_generate_answer(
    question="Question",
    model="test-model",
    history=(),
    orchestrator_factory=FakeOrchestrator,
    replace_message_id="assistant-1",
    refresh_sidebar_sources=lambda: None,
    refresh_model_status=lambda: None,
)
"""
    app = AppTest.from_string(script, default_timeout=10).run()

    statuses = app.get("status")
    assert statuses[-1].label == "Previous answer replaced"
    assert statuses[-1].state == "complete"
    assert app.session_state["messages"][-1].content == "Replacement answer."
