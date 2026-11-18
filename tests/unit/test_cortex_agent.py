from __future__ import annotations

import json
from typing import Any

import pytest

from rag_chat.domain.errors import ConfigurationError
from rag_chat.infrastructure.snowflake.cortex_agent import (
    identify_viewer,
)

ROLE = "GG_APP_SOYOU_DATALAB_USER"


class FakeSession:
    def __init__(self, payload: object = None, role: str = ROLE) -> None:
        self.payload = payload or {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Grounded answer [7].",
                    "annotations": [
                        {
                            "type": "cortex_search_citation",
                            "index": 7,
                            "doc_id": "d1",
                            "doc_title": "Policy",
                            "text": "Approved evidence",
                        }
                    ],
                }
            ],
        }
        self.role = role
        self.calls: list[tuple[str, Any]] = []
        self.statement_params: list[Any] = []

    def sql(self, query: str, params: object = None) -> Any:
        self.calls.append((query, params))
        return self

    def collect(self, *, statement_params: object) -> list[dict[str, object]]:
        self.statement_params.append(statement_params)
        query = self.calls[-1][0]
        if "CURRENT_USER" in query:
            return [{"VIEWER": "viewer", "ACCESS_ROLE": self.role}]
        if "DATA_AGENT_RUN" in query:
            return [{"RESPONSE": json.dumps(self.payload)}]
        return []


@pytest.mark.parametrize(
    "role,policy",
    [
        (ROLE, "GENERAL"),
        ("GG_APP_SOYOU_DATALAB_DPO", "PRIVACY"),
        ("GG_APP_SP_DATALAB_CREDIT_AFTERSALES", "CREDIT_AFTERSALES"),
    ],
)
def test_viewer_uses_exact_approved_policy(role: str, policy: str) -> None:
    session = FakeSession(role=role)
    viewer = identify_viewer(session)
    assert (viewer.user, viewer.role, viewer.policy) == ("viewer", role, policy)
    assert viewer.agent == f"DATALAB.SPAIN.SOFIA_{policy}_AGENT"
    assert session.calls[0][0] == "USE SECONDARY ROLES NONE"


@pytest.mark.parametrize("role", ["ACCOUNTADMIN", "AGENT_STUDIO_USER", "", "general"])
def test_unknown_role_is_denied_without_agent_call(role: str) -> None:
    session = FakeSession(role=role)
    with pytest.raises(ConfigurationError, match="approved document policy"):
        identify_viewer(session)
    assert all("DATA_AGENT_RUN" not in sql for sql, _ in session.calls)
