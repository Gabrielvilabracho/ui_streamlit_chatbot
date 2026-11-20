from __future__ import annotations

import pytest

from rag_chat.application.hooks import HookDispatcher
from rag_chat.domain.models import OrchestrationStep, ProgressEvent, ProgressState


def test_dispatcher_calls_registered_hooks_then_request_callback_without_retaining_it() -> None:
    calls = []
    dispatcher = HookDispatcher(hooks=(lambda event: calls.append(("registered", event)),))
    event = ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED)

    dispatcher.emit(event, on_progress=lambda value: calls.append(("request", value)))
    dispatcher.emit(event)

    assert calls == [("registered", event), ("request", event), ("registered", event)]
    HookDispatcher().emit(event)


def test_dispatcher_preserves_registration_order() -> None:
    calls = []
    dispatcher = HookDispatcher(
        hooks=(lambda event: calls.append("first"), lambda event: calls.append("second"))
    )
    dispatcher.emit(
        ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED),
        on_progress=lambda event: calls.append("request"),
    )
    assert calls == ["first", "second", "request"]


def test_dispatcher_preserves_callback_exception() -> None:
    def fail(event: ProgressEvent) -> None:
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match="^callback failed$"):
        HookDispatcher().emit(
            ProgressEvent(OrchestrationStep.GENERATE_ANSWER, ProgressState.STARTED),
            on_progress=fail,
        )
