"""Snowflake AI_COMPLETE implementation of the generation port."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import SpanAttributes

from rag_chat.domain.errors import ProviderResponseError
from rag_chat.domain.models import GenerationResult, TokenUsage
from rag_chat.infrastructure.snowflake._errors import translate_timeout
from rag_chat.infrastructure.trulens.instrumentation import generation_span_attributes

_AI_COMPLETE_SQL = """
SELECT TO_JSON(
    AI_COMPLETE(
        model => ?,
        prompt => ?,
        model_parameters => OBJECT_CONSTRUCT(
            'temperature', ?,
            'max_tokens', ?,
            'guardrails', TRUE
        ),
        show_details => TRUE
    )
) AS RESPONSE
""".strip()


class CortexCompleteGenerator:
    def __init__(
        self,
        *,
        session: Any,
        temperature: float = 0.1,
        max_tokens: int = 1_024,
    ) -> None:
        self._session = session
        self._temperature = temperature
        self._max_tokens = max_tokens

    @instrument(
        name="sofia.generate",
        span_type=SpanAttributes.SpanType.GENERATION,
        attributes=generation_span_attributes,
    )
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout_seconds: float,
    ) -> GenerationResult:
        try:
            frame = self._session.sql(
                _AI_COMPLETE_SQL,
                params=[model, prompt, self._temperature, self._max_tokens],
            )
            rows = _collect_with_timeout(frame, timeout_seconds)
        except Exception as error:
            translate_timeout(error, operation="AI_COMPLETE request")
            raise

        if not rows:
            raise ProviderResponseError("Snowflake AI_COMPLETE returned no rows.")
        raw_response = _row_value(rows[0], "RESPONSE")
        payload = _parse_payload(raw_response)
        content = _extract_content(payload)
        usage = payload.get("usage", {})
        if not isinstance(usage, Mapping):
            usage = {}
        return GenerationResult(
            content=content,
            model=str(payload.get("model") or model),
            usage=TokenUsage(
                prompt_tokens=_integer(usage.get("prompt_tokens")),
                completion_tokens=_integer(usage.get("completion_tokens")),
            ),
            usage_reported=all(
                type(usage.get(key)) is int and usage[key] >= 0
                for key in ("prompt_tokens", "completion_tokens")
            ),
        )


def _collect_with_timeout(frame: Any, timeout_seconds: float) -> list[Any]:
    statement_params = {"STATEMENT_TIMEOUT_IN_SECONDS": str(max(1, math.ceil(timeout_seconds)))}
    try:
        return list(frame.collect(statement_params=statement_params))
    except TypeError:
        return list(frame.collect())


def _row_value(row: Any, name: str) -> object:
    if isinstance(row, Mapping):
        return row.get(name) or row.get(name.lower())
    try:
        return row[name]
    except (KeyError, TypeError):
        return getattr(row, name, None)


def _parse_payload(raw: object) -> Mapping[str, object]:
    if isinstance(raw, Mapping):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise ProviderResponseError("Snowflake AI_COMPLETE returned an empty response.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProviderResponseError("Snowflake AI_COMPLETE returned invalid JSON.") from error
    if not isinstance(payload, Mapping):
        raise ProviderResponseError("Snowflake AI_COMPLETE returned an unexpected JSON shape.")
    return payload


def _extract_content(payload: Mapping[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderResponseError("Snowflake AI_COMPLETE response has no choices.")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ProviderResponseError("Snowflake AI_COMPLETE returned an invalid choice.")
    message = first.get("messages") or first.get("message") or first.get("content")
    if isinstance(message, Mapping):
        message = message.get("content")
    if isinstance(message, list):
        message = "".join(
            str(part.get("text", "")) if isinstance(part, Mapping) else str(part)
            for part in message
        )
    content = str(message or "").strip()
    if not content:
        raise ProviderResponseError("Snowflake AI_COMPLETE returned empty content.")
    return content


def _integer(value: object) -> int:
    if not isinstance(value, (int, float, str)):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
