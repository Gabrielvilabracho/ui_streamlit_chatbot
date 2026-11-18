"""Pure model-usage labels for the compact chat-input status strip."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rag_chat.ui.state import UiMessage


@dataclass(frozen=True, slots=True)
class ModelStatus:
    model: str
    intensity: str
    tokens: str
    context: str


def parse_model_context_limits(value: str) -> dict[str, int]:
    """Parse explicit `model=limit` entries without inventing model capacities."""

    limits: dict[str, int] = {}
    for entry in value.split(","):
        model, separator, raw_limit = entry.partition("=")
        if not separator:
            continue
        model = model.strip()
        try:
            limit = int(raw_limit.strip())
        except ValueError:
            continue
        if model and limit > 0:
            limits[model] = limit
    return limits


def build_model_status(
    *,
    selected_model: str,
    messages: Sequence[UiMessage],
    context_limits: Mapping[str, int],
) -> ModelStatus:
    """Describe selected-model settings and the latest provider-reported usage."""

    latest = next(
        (
            message
            for message in reversed(messages)
            if message.role == "assistant" and message.model
        ),
        None,
    )
    if latest is None:
        return ModelStatus(
            model=f"Model · {selected_model}",
            intensity="Intensity · unavailable",
            tokens="Last response · unavailable",
            context="Context · unavailable",
        )

    prompt_tokens = latest.prompt_tokens
    completion_tokens = latest.completion_tokens
    total_tokens = prompt_tokens + completion_tokens
    context_limit = context_limits.get(latest.model or "")
    context = "Context · unavailable"
    if context_limit:
        percentage = total_tokens / context_limit * 100
        precision = 2 if percentage < 1 else 1
        context = (
            f"Context · {total_tokens:,} / {context_limit:,} "
            f"({percentage:.{precision}f}%)"
        )

    return ModelStatus(
        model=f"Model · {selected_model}",
        intensity="Intensity · unavailable",
        tokens=(
            f"Last response · Input {prompt_tokens:,} / Output {completion_tokens:,}"
        ),
        context=context,
    )
