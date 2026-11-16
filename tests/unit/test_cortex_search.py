from __future__ import annotations

from dataclasses import dataclass

import pytest

from rag_chat.domain.errors import RagTimeoutError
from rag_chat.infrastructure.snowflake.cortex_search import CortexSearchRetriever


@dataclass
class FakeSearchResponse:
    results: list[dict[str, object]]


class FakeSearchService:
    def __init__(self, response: FakeSearchResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def search(self, **kwargs: object) -> FakeSearchResponse:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_retriever_maps_cortex_search_results_to_domain_documents() -> None:
    service = FakeSearchService(
        FakeSearchResponse(
            results=[
                {
                    "CHUNK_ID": "chunk-7",
                    "CHUNK": "Approved invoices are posted after validation.",
                    "TITLE": "Invoice posting",
                    "SOURCE_URL": "https://docs.example.test/invoices",
                    "@search.score": 0.97,
                }
            ]
        )
    )
    retriever = CortexSearchRetriever(
        service=service,
        content_column="CHUNK",
        id_column="CHUNK_ID",
        title_column="TITLE",
        uri_column="SOURCE_URL",
    )

    documents = retriever.retrieve("When are invoices posted?", limit=3)

    assert service.calls == [
        {
            "query": "When are invoices posted?",
            "columns": ["CHUNK", "CHUNK_ID", "TITLE", "SOURCE_URL"],
            "limit": 3,
        }
    ]
    assert documents[0].document_id == "chunk-7"
    assert documents[0].title == "Invoice posting"
    assert documents[0].score == pytest.approx(0.97)


def test_retriever_translates_provider_timeout() -> None:
    retriever = CortexSearchRetriever(
        service=FakeSearchService(TimeoutError("read timeout")),
        content_column="CHUNK",
        id_column="CHUNK_ID",
        title_column="TITLE",
        uri_column="SOURCE_URL",
    )

    with pytest.raises(RagTimeoutError, match="timed out"):
        retriever.retrieve("Question", limit=3)
