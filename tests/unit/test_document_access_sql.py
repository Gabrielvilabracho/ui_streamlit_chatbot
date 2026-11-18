"""Exercise the policy SELECTs locally, without claiming Snowflake grant proof."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY_SQL = ROOT / "sql" / "document_access_policies.sql"
GRANTS_SQL = ROOT / "sql" / "document_access_grants.sql"
INITIAL_GENERAL_SQL = ROOT / "sql" / "classify_existing_documents_general.sql"
LIFECYCLE_GUIDE = ROOT / "docs" / "document-lifecycle.md"
POLICIES = (
    ("GENERAL", "SOFIA_GENERAL_CHUNKS", "GG_APP_SOYOU_DATALAB_USER", 101),
    ("PRIVACY", "SOFIA_PRIVACY_CHUNKS", "GG_APP_SOYOU_DATALAB_DPO", 202),
    (
        "CREDIT_AFTERSALES",
        "SOFIA_CREDIT_AFTERSALES_CHUNKS",
        "GG_APP_SP_DATALAB_CREDIT_AFTERSALES",
        303,
    ),
)


@pytest.fixture
def corpus() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE RAG_DOCUMENTS (DOC_ID INTEGER, FILE_NAME TEXT);
        CREATE TABLE RAG_CHUNKS (CHUNK_ID INTEGER, DOC_ID INTEGER, CHUNK_TEXT TEXT);
        CREATE TABLE SOFIA_DOCUMENT_CLASSIFICATIONS (DOC_ID INTEGER, ACCESS_POLICY TEXT);
        INSERT INTO RAG_DOCUMENTS VALUES
            (101, 'same.pdf'), (202, 'same.pdf'), (303, 'credit.pdf'),
            (404, 'unclassified.pdf'), (505, 'invalid.pdf'),
            (606, 'conflicting.pdf'), (707, 'duplicate.pdf');
        INSERT INTO RAG_CHUNKS VALUES
            (1, 101, 'General content'), (2, 202, 'Privacy content'),
            (3, 303, 'Credit content'), (4, 404, 'Unclassified content'),
            (5, 505, 'Invalid content'), (6, 606, 'Conflicting content'),
            (7, 707, 'Duplicate classification'), (8, 808, 'Orphan chunk');
        INSERT INTO SOFIA_DOCUMENT_CLASSIFICATIONS VALUES
            (101, 'GENERAL'), (202, 'PRIVACY'), (303, 'CREDIT_AFTERSALES'),
            (505, 'UNKNOWN'), (606, 'GENERAL'), (606, 'PRIVACY'),
            (707, 'GENERAL'), (707, 'GENERAL'), (808, 'GENERAL');
        """
    )
    try:
        yield connection
    finally:
        connection.close()


def install_views(connection: sqlite3.Connection) -> None:
    """Run the actual portable view bodies; SQLite cannot test Snowflake RBAC."""
    definitions = re.findall(
        r"CREATE SECURE VIEW DATALAB\.SPAIN\.(\w+)\s+AS\s+(.*?);",
        POLICY_SQL.read_text(),
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert len(definitions) == 3
    for name, query in definitions:
        local_query = query.replace("DATALAB.SPAIN.", "")
        connection.execute(f"CREATE VIEW {name} AS {local_query}")


@pytest.mark.parametrize("policy,view,role,expected_doc", POLICIES)
def test_only_explicitly_classified_policy_documents_are_visible(
    corpus: sqlite3.Connection, policy: str, view: str, role: str, expected_doc: int
) -> None:
    del role
    before = tuple(corpus.iterdump())
    install_views(corpus)
    rows = corpus.execute(f"SELECT DOC_ID, ACCESS_POLICY, CHUNK_TEXT, TITLE FROM {view}").fetchall()
    assert rows == [
        (
            expected_doc,
            policy,
            {101: "General content", 202: "Privacy content", 303: "Credit content"}[expected_doc],
            "credit.pdf" if expected_doc == 303 else "same.pdf",
        )
    ]
    # Rendering a policy must not classify or mutate any source records.
    after = tuple(line for line in corpus.iterdump() if not line.startswith("CREATE VIEW"))
    assert after == before


def test_empty_classification_exposes_no_documents(corpus: sqlite3.Connection) -> None:
    corpus.execute("DELETE FROM SOFIA_DOCUMENT_CLASSIFICATIONS")
    install_views(corpus)
    for _, view, _, _ in POLICIES:
        assert corpus.execute(f"SELECT * FROM {view}").fetchall() == []


def test_grants_are_limited_to_the_matching_consumer_view() -> None:
    sql = GRANTS_SQL.read_text()
    statements = re.sub(r"--[^\n]*", "", sql)
    grants = {
        " ".join(statement.split()) for statement in statements.split(";") if statement.strip()
    }
    assert grants == {
        f"GRANT SELECT ON VIEW DATALAB.SPAIN.{view} TO ROLE {role}" for _, view, role, _ in POLICIES
    }


def test_policy_setup_neither_replaces_objects_nor_assigns_real_documents() -> None:
    sql = re.sub(r"--[^\n]*", "", POLICY_SQL.read_text()).upper()
    assert "CREATE TABLE DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS" in sql
    assert not re.search(r"\b(REPLACE|INSERT|UPDATE|DELETE|DROP|TRUNCATE|MERGE)\b", sql)
    assert "CURRENT_ROLE" not in sql
    assert "RAG_DOCUEMNT_REGISTRY" not in sql
