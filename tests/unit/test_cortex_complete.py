from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from rag_chat.domain.errors import RagTimeoutError
from rag_chat.infrastructure.snowflake.cortex_complete import CortexCompleteGenerator


@dataclass
class FakeDataFrame:
    rows: list[dict[str, object]]

    def collect(self) -> list[dict[str, object]]:
        return self.rows


class FakeSession:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.query = ""
        self.params: list[object] = []

    def sql(self, query: str, params: list[object]) -> FakeDataFrame:
        self.query = query
        self.params = params
        if isinstance(self.response, Exception):
            raise self.response
        return FakeDataFrame([{"RESPONSE": self.response}])


def test_generator_uses_ai_complete_details_and_maps_token_usage() -> None:
    session = FakeSession(
        json.dumps(
            {
                "choices": [{"messages": "A grounded answer [1]."}],
                "model": "llama3.3-70b",
                "usage": {
                    "prompt_tokens": 44,
                    "completion_tokens": 9,
                    "total_tokens": 53,
                },
            }
        )
    )
    generator = CortexCompleteGenerator(session=session, temperature=0.1, max_tokens=512)

    result = generator.generate(
        model="llama3.3-70b",
        prompt="Use only this context.",
        timeout_seconds=15.0,
    )

    assert "AI_COMPLETE" in session.query
    assert "show_details => TRUE" in session.query
    assert session.params[:2] == ["llama3.3-70b", "Use only this context."]
    assert result.content == "A grounded answer [1]."
    assert result.usage.prompt_tokens == 44
    assert result.usage.completion_tokens == 9
    assert result.usage.total_tokens == 53


def test_generator_translates_provider_timeout() -> None:
    generator = CortexCompleteGenerator(
        session=FakeSession(TimeoutError("socket timeout")),
        temperature=0.1,
        max_tokens=512,
    )

    with pytest.raises(RagTimeoutError, match="timed out"):
        generator.generate(model="llama3.3-70b", prompt="Question", timeout_seconds=1.0)


@pytest.mark.parametrize(
    "usage,reported",
    [
        ({}, False),
        ({"prompt_tokens": 2}, False),
        ({"prompt_tokens": "2", "completion_tokens": 1}, False),
        ({"prompt_tokens": True, "completion_tokens": 1}, False),
        ({"prompt_tokens": 0, "completion_tokens": 0}, True),
        ({"prompt_tokens": 2, "completion_tokens": 1}, True),
    ],
)
def test_generator_distinguishes_absent_usage_from_reported_zero(usage, reported) -> None:
    generator = CortexCompleteGenerator(
        session=FakeSession(
            json.dumps(
                {
                    "choices": [{"messages": "answer"}],
                    "usage": usage,
                }
            )
        )
    )
    result = generator.generate(model="model", prompt="question", timeout_seconds=1)
    assert result.usage_reported is reported
