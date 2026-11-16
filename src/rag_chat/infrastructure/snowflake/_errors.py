"""Translate provider-specific timeout shapes at the infrastructure boundary."""

from __future__ import annotations

from rag_chat.domain.errors import RagTimeoutError


def translate_timeout(error: Exception, *, operation: str) -> None:
    """Raise an application timeout when the provider reports a timeout-like error."""

    if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower():
        raise RagTimeoutError(f"Snowflake {operation} timed out. Please retry.") from error
