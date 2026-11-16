"""Central, versioned business prompt for grounded answers."""

from __future__ import annotations

from collections.abc import Sequence

from rag_chat.domain.models import ChatMessage, SourceDocument

SYSTEM_PROMPT = """You are CONTAVIA Knowledge Assistant.
Answer the user's question using only the supplied trusted context.
When the context supports a statement, cite its source with [n], matching the source number.
If the context is insufficient, say that the available sources do not contain the answer.
Do not invent policies, figures, links, or citations. Keep the response concise and actionable.
""".strip()


def build_rag_prompt(
    *,
    question: str,
    sources: Sequence[SourceDocument],
    history: Sequence[ChatMessage],
) -> str:
    """Build the provider prompt without leaking presentation concerns into the domain."""

    history_text = "\n".join(
        f"{message.role.upper()}: {message.content}" for message in history
    ) or "No previous conversation."
    context_text = "\n\n".join(
        f"[{index}] {source.title}\n{source.content}\nURI: {source.uri or 'not provided'}"
        for index, source in enumerate(sources, start=1)
    ) or "No relevant context was retrieved."

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"CONVERSATION\n{history_text}\n\n"
        f"TRUSTED CONTEXT\n{context_text}\n\n"
        f"USER QUESTION\n{question}\n\n"
        "ANSWER"
    )
