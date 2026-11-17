from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parents[2]


def test_root_app_renders_onboarding_and_safe_configuration_error() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10).run()

    assert not app.exception
    assert app.title[0].value == "Ask Sof~IA"
    assert app.selectbox(key="model_selector").value
    assert "Snowflake configuration" in app.error[0].value
    assert app.chat_input[0].disabled is True


def test_fake_chat_flow_renders_checklist_sources_controls_and_metrics() -> None:
    def fake_app() -> None:
        from rag_chat.domain.models import (
            OrchestrationStep,
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
                        on_progress(step)
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
        )

    app = AppTest.from_function(fake_app, default_timeout=10).run()
    app.chat_input[0].set_value("What does the source say?").run(timeout=10)

    assert not app.exception
    assert any(item.value == "Grounded answer [1]." for item in app.markdown)
    assert any("Source title" in item.value for item in app.markdown)
    assert any("Source title" in item.value for item in app.sidebar.markdown)
    assert len(app.checkbox) == 5
    assert all(item.value is True and item.disabled for item in app.checkbox)
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
