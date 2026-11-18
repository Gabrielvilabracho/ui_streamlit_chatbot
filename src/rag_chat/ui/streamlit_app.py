"""Streamlit view for the framework-independent RAG use case."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse
from uuid import uuid4

import streamlit as st

from rag_chat.application.ports import AnswerService
from rag_chat.domain.errors import RagError, RagTimeoutError
from rag_chat.domain.models import (
    ChatMessage,
    OrchestrationStep,
    ProgressEvent,
    ProgressState,
)
from rag_chat.ui.markup import (
    copy_button_html,
    metric_plugin_html,
    onboarding_html,
    theme_css,
)
from rag_chat.ui.model_status import build_model_status
from rag_chat.ui.state import (
    UiMessage,
    assistant_message,
    conversation_history,
    replace_message,
    user_message,
)

OrchestratorFactory = Callable[[], AnswerService]
BRAND_ASSET_DIR = Path(__file__).resolve().parents[3] / "static" / "brand"
BRAND_MARK = BRAND_ASSET_DIR / "sofinco-mark.png"
BRAND_WORDMARK = BRAND_ASSET_DIR / "sofinco_logo.png"


def run_app(
    *,
    orchestrator_factory: OrchestratorFactory | None,
    models: tuple[str, ...],
    configuration_error: str | None,
    user_identifier: str | None = None,
    access_role: str | None = None,
    model_context_limits: Mapping[str, int] | None = None,
) -> None:
    """Render the application and execute work only after user input."""

    _initialize_state()
    st.html(theme_css(st.context.theme.type))
    st.logo(str(BRAND_MARK), size="small", icon_image=str(BRAND_MARK))
    selected_model, refresh_sidebar_sources = _render_sidebar(
        models,
        configuration_error,
        user_identifier=user_identifier,
        access_role=access_role,
    )

    refresh_sidebar_sources()
    _render_brand_title()
    st.caption("Grounded answers from approved Snowflake knowledge")
    st.html(onboarding_html())

    if configuration_error:
        st.error(
            configuration_error,
            title="Snowflake configuration required",
            icon=":material/key:",
        )

    retry_request = _render_history()
    model_status_placeholder = st.empty()

    def refresh_model_status() -> None:
        with model_status_placeholder.container():
            _render_model_status(
                selected_model=selected_model,
                context_limits=model_context_limits or {},
            )

    refresh_model_status()
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
            refresh_sidebar_sources=refresh_sidebar_sources,
            refresh_model_status=refresh_model_status,
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
            refresh_sidebar_sources=refresh_sidebar_sources,
            refresh_model_status=refresh_model_status,
        )
        st.rerun()


def _initialize_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []


def _render_brand_title() -> None:
    with st.container(horizontal=True, vertical_alignment="center"):
        st.image(
            str(BRAND_MARK),
            alt="Sofinco mark",
            width=64,
        )
        st.title("Ask Sof~IA")


def _messages() -> tuple[UiMessage, ...]:
    return tuple(cast(list[UiMessage], st.session_state.messages))


def _latest_assistant_message() -> UiMessage | None:
    return next(
        (message for message in reversed(_messages()) if message.role == "assistant"),
        None,
    )


def _render_sidebar(
    models: tuple[str, ...],
    configuration_error: str | None,
    *,
    user_identifier: str | None,
    access_role: str | None,
) -> tuple[str, Callable[[], None]]:
    with st.sidebar, st.container(height="stretch", gap="small"):
        _render_sidebar_identity(user_identifier, access_role)
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

        sidebar_sources = st.empty()
        st.space("stretch")
        st.divider()
        with st.container(horizontal_alignment="center"):
            st.image(
                str(BRAND_WORDMARK),
                alt="Sofinco wordmark",
                width=180,
            )

    def refresh_sidebar_sources() -> None:
        with sidebar_sources.container():
            _render_sidebar_sources(_latest_assistant_message())

    return selected_model, refresh_sidebar_sources


def _render_sidebar_identity(user_identifier: str | None, access_role: str | None) -> None:
    st.caption("Signed in as")
    st.markdown(
        f":material/account_circle: **{_escape_markdown(user_identifier or 'Unavailable')}**"
    )
    st.caption("Access role")
    role_label = access_role or (
        "Default Snowflake role" if user_identifier else "Role unavailable"
    )
    st.badge(role_label, color="gray", icon=":material/admin_panel_settings:")
    st.divider()


def _render_sidebar_sources(message: UiMessage | None) -> None:
    st.divider()
    st.subheader("Sources consulted")
    if message is None or not message.sources:
        st.caption("Sources from the latest answer will appear here.")
        return

    with st.expander(
        f"Latest answer · {len(message.sources)}",
        icon=":material/library_books:",
    ):
        _render_source_items(
            message,
            preview_length=140,
            link_label="Open document",
            key_prefix="sidebar_source",
            link_width="stretch",
        )


def _render_history() -> UiMessage | None:
    retry_request: UiMessage | None = None
    for message in _messages():
        avatar = str(BRAND_MARK) if message.role == "assistant" else None
        with st.chat_message(message.role, avatar=avatar):
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
    refresh_sidebar_sources: Callable[[], None],
    refresh_model_status: Callable[[], None],
    replace_message_id: str | None = None,
) -> None:
    request_id = replace_message_id or _message_id("assistant")
    with st.chat_message("assistant", avatar=str(BRAND_MARK)):
        stage_statuses: dict[OrchestrationStep, Any] = {}
        active_stage: OrchestrationStep | None = None

        def mark_progress(event: ProgressEvent) -> None:
            nonlocal active_stage
            if event.state is ProgressState.STARTED:
                active_stage = event.step
                stage_statuses[event.step] = st.status(
                    f":shimmer[{event.step.value}]",
                    state="running",
                    type="step",
                )
                return
            stage_statuses[event.step].update(
                label=event.step.value,
                state="complete",
            )
            if active_stage is event.step:
                active_stage = None

        def mark_active_stage_failed() -> None:
            if active_stage is None:
                return
            stage_statuses[active_stage].update(
                label=f"{active_stage.value} interrupted",
                state="error",
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
            mark_active_stage_failed()
            st.error(
                "Snowflake did not respond before the request deadline. Retry the answer.",
                title="Request timed out",
                icon=":material/schedule:",
            )
            return
        except RagError as error:
            mark_active_stage_failed()
            st.error(str(error), title="Unable to generate an answer", icon=":material/error:")
            return
        except Exception:
            mark_active_stage_failed()
            st.error(
                "An unexpected provider error occurred. "
                "No credentials or prompt content were logged.",
                title="Unable to generate an answer",
                icon=":material/error:",
            )
            return

        message = assistant_message(
            question=question,
            answer=answer,
            message_id=request_id,
        )
        messages = _messages()
        if replace_message_id:
            replacement_status = st.status(
                ":shimmer[Replacing previous answer]",
                state="running",
                type="step",
            )
            st.session_state.messages = list(replace_message(messages, message))
            replacement_status.update(
                label="Previous answer replaced",
                state="complete",
            )
            refresh_sidebar_sources()
            refresh_model_status()
            return

        st.session_state.messages = [*messages, message]
        refresh_sidebar_sources()
        refresh_model_status()
        st.markdown(answer.content)
        _render_sources(message)
        _render_controls(message)


def _render_model_status(
    *,
    selected_model: str,
    context_limits: Mapping[str, int],
) -> None:
    status = build_model_status(
        selected_model=selected_model,
        messages=_messages(),
        context_limits=context_limits,
    )
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.badge(status.model, icon=":material/smart_toy:", color="primary")
        st.badge(
            status.intensity,
            icon=":material/tune:",
            color="gray",
            help="The selected Snowflake model does not expose a verified intensity setting.",
        )
        st.badge(status.tokens, icon=":material/data_usage:", color="gray")
        st.badge(
            status.context,
            icon=":material/donut_large:",
            color="gray",
            help="Shown only when a verified context limit is configured for the response model.",
        )


def _render_sources(message: UiMessage) -> None:
    if not message.sources:
        return
    with st.expander(
        f"Sources · {len(message.sources)}",
        icon=":material/library_books:",
    ):
        _render_source_items(
            message,
            preview_length=280,
            link_label="Open source",
            key_prefix="message_source",
            link_width="content",
        )


def _render_source_items(
    message: UiMessage,
    *,
    preview_length: int,
    link_label: str,
    key_prefix: str,
    link_width: Literal["content", "stretch"],
) -> None:
    for index, source in enumerate(message.sources, start=1):
        st.markdown(f"**[{index}] {_escape_markdown(source.title)}**")
        st.caption(source.content[:preview_length])
        if source.uri and _is_safe_link(source.uri):
            st.link_button(
                link_label,
                source.uri,
                key=f"{key_prefix}_{message.message_id}_{source.document_id}_{index}",
                icon=":material/open_in_new:",
                width=link_width,
            )
        if index < len(message.sources):
            st.divider()


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
