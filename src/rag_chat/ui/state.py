"""Serializable presentation state and domain conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rag_chat.domain.models import ChatMessage, RagAnswer, SourceDocument


@dataclass(frozen=True, slots=True)
class UiMessage:
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    prompt: str | None = None
    model: str | None = None
    sources: tuple[SourceDocument, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    usage_reported: bool = True


def user_message(content: str, *, message_id: str) -> UiMessage:
    return UiMessage(message_id=message_id, role="user", content=content)


def assistant_message(*, question: str, answer: RagAnswer, message_id: str) -> UiMessage:
    return UiMessage(
        message_id=message_id,
        role="assistant",
        content=answer.content,
        prompt=question,
        model=answer.model,
        sources=answer.sources,
        prompt_tokens=answer.usage.prompt_tokens,
        completion_tokens=answer.usage.completion_tokens,
        latency_ms=answer.latency_ms,
        usage_reported=answer.usage_reported,
    )


def conversation_history(
    messages: tuple[UiMessage, ...],
    *,
    before_message_id: str | None = None,
) -> tuple[ChatMessage, ...]:
    history: list[ChatMessage] = []
    for message in messages:
        if message.message_id == before_message_id:
            break
        history.append(ChatMessage(role=message.role, content=message.content))
    return tuple(history)


def replace_message(
    messages: tuple[UiMessage, ...],
    replacement: UiMessage,
) -> tuple[UiMessage, ...]:
    return tuple(
        replacement if message.message_id == replacement.message_id else message
        for message in messages
    )
