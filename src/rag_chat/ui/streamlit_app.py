"""Streamlit view for the framework-independent RAG use case."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

import streamlit as st

from rag_chat.application.orchestrator import RagOrchestrator
from rag_chat.domain.errors import RagError, RagTimeoutError
from rag_chat.domain.models import ChatMessage, OrchestrationStep
from rag_chat.ui.markup import (
    copy_button_html,
    metric_plugin_html,
    onboarding_html,
    theme_css,
)
from rag_chat.ui.state import (
    UiMessage,
    assistant_message,
    conversation_history,
    replace_message,
    user_message,
)

OrchestratorFactory = Callable[[], RagOrchestrator]


def run_app(
    *,
    orchestrator_factory: OrchestratorFactory | None,
    models: tuple[str, ...],
    configuration_error: str | None,
) -> None:
    """Render the application and execute work only after user input."""

    _initialize_state()
    st.html(theme_css())
    selected_model = _render_sidebar(models, configuration_error)
    st.title("Ask CONTAVIA")
    st.caption("Grounded answers from approved Snowflake knowledge")
    st.html(onboarding_html())

    if configuration_error:
        st.error(
            configuration_error,
            title="Snowflake configuration required",
            icon=":material/key:",
        )

    retry_request = _render_history()
    prompt = st.chat_input(
        "Ask about a policy, process, or document",
        key="chat_prompt",
        disabled=orchestrator_factory is None,
        submit_mode="disable",
    )

    if prompt and orchestrator_factory:
        message = user_message(prompt, message_id=_message_id("user"))
        messages = _messages()
        history = conversation_history(messages)
        st.session_state.messages = [*messages, message]
        with st.chat_message("user"):
            st.markdown(prompt)
        _generate_answer(
            question=prompt,
            model=selected_model,
            history=history,
            orchestrator_factory=orchestrator_factory,
        )
    elif retry_request and orchestrator_factory:
        history = conversation_history(
            _messages(), before_message_id=retry_request.message_id
        )
        _generate_answer(
            question=cast(str, retry_request.prompt),
            model=selected_model,
            history=history,
            orchestrator_factory=orchestrator_factory,
            replace_message_id=retry_request.message_id,
        )
        st.rerun()


def _initialize_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []


def _messages() -> tuple[UiMessage, ...]:
    return tuple(cast(list[UiMessage], st.session_state.messages))


def _render_sidebar(models: tuple[str, ...], configuration_error: str | None) -> str:
    with st.sidebar:
        st.caption("CONTAVIA · KNOWLEDGE WORKSPACE")
        st.header("Answer settings")
        selected_model = st.selectbox(
            "Cortex model",
            models,
            key="model_selector",
            help="Availability depends on your Snowflake account and region.",
        )
        st.caption("Retrieval: Cortex Search · Generation: AI_COMPLETE")
        if configuration_error:
            st.badge("Configuration needed", color="orange", icon=":material/key:")
        else:
            st.badge("Ready", color="green", icon=":material/check_circle:")
        if st.button(
            "Clear conversation",
            key="clear_conversation",
            icon=":material/delete_sweep:",
            width="stretch",
        ):
            st.session_state.messages = []
            st.rerun()
    return selected_model


def _render_history() -> UiMessage | None:
    retry_request: UiMessage | None = None
    for message in _messages():
        with st.chat_message(message.role):
            st.markdown(message.content)
            if message.role == "assistant":
                _render_sources(message)
                if _render_controls(message):
                    retry_request = message
    return retry_request


def _generate_answer(
    *,
    question: str,
    model: str,
    history: tuple[ChatMessage, ...],
    orchestrator_factory: OrchestratorFactory,
    replace_message_id: str | None = None,
) -> None:
    request_id = replace_message_id or _message_id("assistant")
    with st.chat_message("assistant"):
        status = st.status(
            ":shimmer[Running grounded answer workflow]",
            expanded=True,
            type="compact",
        )

        def mark_progress(step: OrchestrationStep) -> None:
            status.checkbox(
                step.value,
                value=True,
                disabled=True,
                key=f"step_{request_id}_{step.name.lower()}",
            )

        try:
            orchestrator = orchestrator_factory()
            answer = orchestrator.answer(
                question=question,
                model=model,
                history=history,
                on_progress=mark_progress,
            )
        except (RagTimeoutError, TimeoutError):
            status.update(label="Workflow timed out", state="error", expanded=True)
            st.error(
                "Snowflake did not respond before the request deadline. Retry the answer.",
                title="Request timed out",
                icon=":material/schedule:",
            )
            return
        except RagError as error:
            status.update(label="Workflow stopped safely", state="error", expanded=True)
            st.error(str(error), title="Unable to generate an answer", icon=":material/error:")
            return
        except Exception:
            status.update(label="Workflow failed", state="error", expanded=True)
            st.error(
                "An unexpected provider error occurred. "
                "No credentials or prompt content were logged.",
                title="Unable to generate an answer",
                icon=":material/error:",
            )
            return

        status.update(
            label=f"Workflow complete · {answer.latency_ms:,.0f} ms",
            state="complete",
            expanded=False,
        )
        message = assistant_message(
            question=question,
            answer=answer,
            message_id=request_id,
        )
        messages = _messages()
        if replace_message_id:
            st.session_state.messages = list(replace_message(messages, message))
            return

        st.session_state.messages = [*messages, message]
        st.markdown(answer.content)
        _render_sources(message)
        _render_controls(message)


def _render_sources(message: UiMessage) -> None:
    if not message.sources:
        return
    with st.expander(
        f"Sources · {len(message.sources)}",
        icon=":material/library_books:",
    ):
        for index, source in enumerate(message.sources, start=1):
            st.markdown(f"**[{index}] {_escape_markdown(source.title)}**")
            st.caption(source.content[:280])
            if source.uri and _is_safe_link(source.uri):
                st.link_button(
                    "Open source",
                    source.uri,
                    icon=":material/open_in_new:",
                    width="content",
                )


def _render_controls(message: UiMessage) -> bool:
    copy_column, retry_column, feedback_column, metrics_column = st.columns(
        (1, 1, 2, 5),
        gap="xsmall",
        vertical_alignment="center",
    )
    with copy_column:
        st.html(
            copy_button_html(message.message_id, message.content),
            width="content",
            unsafe_allow_javascript=True,
        )
    with retry_column:
        retry = st.button(
            "Retry",
            key=f"retry_{message.message_id}",
            icon=":material/refresh:",
            width="content",
        )
    with feedback_column:
        st.feedback(
            "thumbs",
            key=f"feedback_{message.message_id}",
            on_change="ignore",
            persist_state="session",
        )
    with metrics_column:
        st.html(
            metric_plugin_html(
                prompt_tokens=message.prompt_tokens,
                completion_tokens=message.completion_tokens,
                latency_ms=message.latency_ms,
            )
        )
    return retry


def _message_id(role: str) -> str:
    return f"{role}-{uuid4().hex}"


def _is_safe_link(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"http", "https"}


def _escape_markdown(value: str) -> str:
    escaped = value
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped
