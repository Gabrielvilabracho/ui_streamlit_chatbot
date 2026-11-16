"""Cortex Search implementation of the retrieval port."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from rag_chat.domain.models import SourceDocument
from rag_chat.infrastructure.snowflake._errors import translate_timeout


class CortexSearchRetriever:
    def __init__(
        self,
        *,
        service: Any,
        content_column: str,
        id_column: str,
        title_column: str,
        uri_column: str,
    ) -> None:
        self._service = service
        self._content_column = content_column
        self._id_column = id_column
        self._title_column = title_column
        self._uri_column = uri_column

    def retrieve(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        columns = list(
            dict.fromkeys(
                (
                    self._content_column,
                    self._id_column,
                    self._title_column,
                    self._uri_column,
                )
            )
        )
        try:
            response = self._service.search(query=query, columns=columns, limit=limit)
        except Exception as error:
            translate_timeout(error, operation="Cortex Search request")
            raise

        results = getattr(response, "results", ())
        return tuple(self._map_document(result, index) for index, result in enumerate(results))

    def _map_document(self, raw: Mapping[str, object], index: int) -> SourceDocument:
        content = str(raw.get(self._content_column, "")).strip()
        document_id = str(raw.get(self._id_column) or _stable_id(content, index))
        title = str(raw.get(self._title_column) or f"Source {index + 1}")
        uri_value = raw.get(self._uri_column)
        score_value = raw.get("@search.score")
        return SourceDocument(
            document_id=document_id,
            content=content,
            title=title,
            uri=str(uri_value) if uri_value else None,
            score=_optional_float(score_value),
        )


def _stable_id(content: str, index: int) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"chunk-{index + 1}-{digest}"


def _optional_float(value: object) -> float | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None
