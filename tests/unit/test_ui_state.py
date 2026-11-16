from __future__ import annotations

from rag_chat.domain.models import RagAnswer, SourceDocument, TokenUsage
from rag_chat.ui.state import (
    assistant_message,
    conversation_history,
    replace_message,
    user_message,
)


def test_ui_messages_preserve_question_sources_and_metrics_across_reruns() -> None:
    question = user_message("How do I post an invoice?", message_id="user-1")
    answer = RagAnswer(
        content="Validate it before posting [1].",
        model="llama3.3-70b",
        sources=(
            SourceDocument(
                document_id="invoice-1",
                content="Invoices must be validated before posting.",
                title="Invoice policy",
                uri="https://docs.example.test/invoices",
            ),
        ),
        usage=TokenUsage(prompt_tokens=42, completion_tokens=8),
        latency_ms=321.5,
    )

    message = assistant_message(
        question="How do I post an invoice?",
        answer=answer,
        message_id="assistant-1",
    )

    assert question.role == "user"
    assert message.prompt == "How do I post an invoice?"
    assert message.sources[0].title == "Invoice policy"
    assert message.prompt_tokens == 42
    assert message.completion_tokens == 8
    assert message.latency_ms == 321.5


def test_retry_history_stops_before_the_answer_being_replaced() -> None:
    first_user = user_message("First question", message_id="user-1")
    first_answer = assistant_message(
        question="First question",
        answer=RagAnswer(
            content="First answer",
            model="model-a",
            sources=(),
            usage=TokenUsage(),
            latency_ms=10.0,
        ),
        message_id="assistant-1",
    )
    second_user = user_message("Second question", message_id="user-2")

    history = conversation_history(
        (first_user, first_answer, second_user),
        before_message_id="assistant-1",
    )

    assert [(item.role, item.content) for item in history] == [
        ("user", "First question")
    ]


def test_replace_message_updates_only_the_selected_assistant_response() -> None:
    original = assistant_message(
        question="Question",
        answer=RagAnswer(
            content="Old answer",
            model="model-a",
            sources=(),
            usage=TokenUsage(),
            latency_ms=10.0,
        ),
        message_id="assistant-1",
    )
    replacement = assistant_message(
        question="Question",
        answer=RagAnswer(
            content="New answer",
            model="model-b",
            sources=(),
            usage=TokenUsage(),
            latency_ms=12.0,
        ),
        message_id="assistant-1",
    )

    updated = replace_message((original,), replacement)

    assert updated == (replacement,)
