from __future__ import annotations

import importlib
from types import SimpleNamespace

from rag_chat.infrastructure.trulens import connector as connector_module


def test_installed_snowflake_connector_imports() -> None:
    module = importlib.import_module("trulens.connectors.snowflake")

    assert callable(module.SnowflakeConnector)


def test_connector_reuses_existing_snowpark_session(monkeypatch) -> None:
    snowpark_session = object()

    class FakeSnowflakeConnector:
        def __init__(self, *, snowpark_session) -> None:
            self.snowpark_session = snowpark_session

    def fake_import_module(name: str) -> SimpleNamespace:
        assert name == "trulens.connectors.snowflake"
        return SimpleNamespace(SnowflakeConnector=FakeSnowflakeConnector)

    monkeypatch.setattr(connector_module.importlib, "import_module", fake_import_module)

    connector = connector_module.create_snowflake_connector(snowpark_session)

    assert connector.snowpark_session is snowpark_session
