"""Caller-bound Snowflake identity and query foundation.

The caller session is injected by Streamlit, never constructed from owner credentials.
Deployment must separately prove caller grants and policy-isolated agent/Search objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_chat.domain.errors import ConfigurationError, ProviderResponseError
from rag_chat.infrastructure.snowflake._errors import translate_timeout

AGENT_MODEL = "Managed by Cortex Agent"
_POLICIES = {
    "GG_APP_SOYOU_DATALAB_USER": "GENERAL",
    "GG_APP_SOYOU_DATALAB_DPO": "PRIVACY",
    "GG_APP_SP_DATALAB_CREDIT_AFTERSALES": "CREDIT_AFTERSALES",
}
_TIMEOUT = {"STATEMENT_TIMEOUT_IN_SECONDS": "60"}


@dataclass(frozen=True, slots=True)
class Viewer:
    user: str
    role: str
    policy: str

    @property
    def agent(self) -> str:
        return f"DATALAB.SPAIN.SOFIA_{self.policy}_AGENT"


def _query(session: Any, sql: str, params: list[str] | None = None) -> list[Any]:
    try:
        return list(session.sql(sql, params=params).collect(statement_params=_TIMEOUT))
    except Exception as error:
        translate_timeout(error, operation="Cortex Agent caller connection")
        raise ProviderResponseError(
            "The Snowflake caller connection failed. Check the runtime and caller grants."
        ) from error


def identify_viewer(session: Any) -> Viewer:
    """Use the default primary role only; no secondary-role or owner escalation."""
    _query(session, "USE SECONDARY ROLES NONE")
    rows = _query(session, "SELECT CURRENT_USER() AS VIEWER, CURRENT_ROLE() AS ACCESS_ROLE")
    if len(rows) != 1:
        raise ConfigurationError("Snowflake did not return a verified viewer identity.")
    user, role = rows[0]["VIEWER"], rows[0]["ACCESS_ROLE"]
    if not isinstance(user, str) or not user.strip() or role not in _POLICIES:
        raise ConfigurationError("The viewer's default role has no approved document policy.")
    return Viewer(user=user, role=role, policy=_POLICIES[role])
