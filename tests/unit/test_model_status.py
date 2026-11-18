from __future__ import annotations

from rag_chat.ui.model_status import build_model_status, parse_model_context_limits
from rag_chat.ui.state import UiMessage


def test_parse_model_context_limits_accepts_only_explicit_positive_values() -> None:
    limits = parse_model_context_limits(
        "llama3.3-70b=131072,mistral-large2=32768,invalid,nope=zero,empty=0"
    )

    assert limits == {
        "llama3.3-70b": 131_072,
        "mistral-large2": 32_768,
    }


def test_model_status_labels_unknown_usage_and_unsupported_intensity() -> None:
    status = build_model_status(
        selected_model="llama3.3-70b",
        messages=(),
        context_limits={},
    )

    assert status.model == "Model · llama3.3-70b"
    assert status.intensity == "Intensity · unavailable"
    assert status.tokens == "Last response · unavailable"
    assert status.context == "Context · unavailable"


def test_model_status_calculates_last_response_context_utilization() -> None:
    last_response = UiMessage(
        message_id="assistant-1",
        role="assistant",
        content="Answer",
        model="llama3.3-70b",
        prompt_tokens=20,
        completion_tokens=5,
    )

    status = build_model_status(
        selected_model="mistral-large2",
        messages=(last_response,),
        context_limits={"llama3.3-70b": 100},
    )

    assert status.model == "Model · mistral-large2"
    assert status.tokens == "Last response · Input 20 / Output 5"
    assert status.context == "Context · 25 / 100 (25.0%)"
