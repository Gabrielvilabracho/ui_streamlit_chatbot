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
        r"CREATE SECURE VIEW DATALAB\.TEST\.(\w+)\s+AS\s+(.*?);",
        POLICY_SQL.read_text(),
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert len(definitions) == 3
    for name, query in definitions:
        local_query = query.replace("DATALAB.TEST.", "")
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
        f"GRANT SELECT ON VIEW DATALAB.TEST.{view} TO ROLE {role}" for _, view, role, _ in POLICIES
    }


def test_policy_setup_neither_replaces_objects_nor_assigns_real_documents() -> None:
    sql = re.sub(r"--[^\n]*", "", POLICY_SQL.read_text()).upper()
    assert "CREATE TABLE DATALAB.TEST.SOFIA_DOCUMENT_CLASSIFICATIONS" in sql
    assert not re.search(r"\b(REPLACE|INSERT|UPDATE|DELETE|DROP|TRUNCATE|MERGE)\b", sql)
    assert "CURRENT_ROLE" not in sql
    assert "RAG_DOCUEMNT_REGISTRY" not in sql


def run_initial_general_queries(connection: sqlite3.Connection) -> None:
    """Probe actual query bodies; Snowflake scripting/RBAC needs live validation."""
    sql = re.sub(r"--[^\n]*", "", INITIAL_GENERAL_SQL.read_text())
    guard = re.search(r"SELECT COUNT\(\*\)\s+INTO :conflict_count\s+(FROM.*?);", sql, re.S)
    insert = re.search(r"INSERT INTO .*?;", sql, re.S)
    assert guard is not None and insert is not None
    assert "IF (conflict_count > 0) THEN\n    RAISE assignment_conflict;\n  END IF;" in sql
    assert sql.index("RAISE assignment_conflict;") < sql.index("INSERT INTO")
    assert "BEGIN TRANSACTION;" in sql and "COMMIT;" in sql
    assert re.search(r"WHEN OTHER THEN\s+ROLLBACK;\s+RAISE;", sql)
    conflict_count = connection.execute(
        ("SELECT COUNT(*) " + guard.group(1)).replace("DATALAB.TEST.", "")
    ).fetchone()[0]
    if conflict_count:
        raise ValueError("Existing classifications require review")
    connection.execute(insert.group().replace("DATALAB.TEST.", ""))


def test_initial_general_assignment_is_complete_and_rerunnable(
    corpus: sqlite3.Connection,
) -> None:
    corpus.execute("DELETE FROM SOFIA_DOCUMENT_CLASSIFICATIONS")
    corpus.execute("INSERT INTO RAG_DOCUMENTS VALUES (101, 'duplicate source row.pdf')")
    source_rows = corpus.execute("SELECT * FROM RAG_DOCUMENTS").fetchall()
    chunks = corpus.execute("SELECT * FROM RAG_CHUNKS").fetchall()
    run_initial_general_queries(corpus)
    assignments = corpus.execute(
        "SELECT DOC_ID, ACCESS_POLICY FROM SOFIA_DOCUMENT_CLASSIFICATIONS ORDER BY DOC_ID"
    ).fetchall()
    assert assignments == [(doc_id, "GENERAL") for doc_id in (101, 202, 303, 404, 505, 606, 707)]
    run_initial_general_queries(corpus)
    assert (
        corpus.execute(
            "SELECT DOC_ID, ACCESS_POLICY FROM SOFIA_DOCUMENT_CLASSIFICATIONS ORDER BY DOC_ID"
        ).fetchall()
        == assignments
    )
    assert corpus.execute("SELECT * FROM RAG_DOCUMENTS").fetchall() == source_rows
    assert corpus.execute("SELECT * FROM RAG_CHUNKS").fetchall() == chunks


@pytest.mark.parametrize(
    "labels", [("PRIVACY",), ("CREDIT_AFTERSALES",), ("UNKNOWN",), ("GENERAL", "GENERAL")]
)
def test_initial_general_rejects_conflicts_without_partial_assignment(
    corpus: sqlite3.Connection, labels: tuple[str, ...]
) -> None:
    corpus.execute("DELETE FROM SOFIA_DOCUMENT_CLASSIFICATIONS")
    corpus.executemany(
        "INSERT INTO SOFIA_DOCUMENT_CLASSIFICATIONS VALUES (202, ?)",
        [(label,) for label in labels],
    )
    before = tuple(corpus.iterdump())
    with pytest.raises(ValueError, match="Existing classifications require review"):
        run_initial_general_queries(corpus)
    assert tuple(corpus.iterdump()) == before


def new_document_assignment_query() -> str:
    """Keep the runbook's operator-facing SQL example under regression coverage."""
    match = re.search(
        r"INSERT INTO DATALAB\.TEST\.SOFIA_DOCUMENT_CLASSIFICATIONS .*?;",
        LIFECYCLE_GUIDE.read_text(),
        re.S,
    )
    assert match is not None
    return (
        match.group()
        .replace("DATALAB.TEST.", "")
        .replace("$document_id", ":document_id")
        .replace("$access_policy", ":access_policy")
    )


@pytest.mark.parametrize("policy", [entry[0] for entry in POLICIES])
def test_guide_assigns_a_new_document_once(corpus: sqlite3.Connection, policy: str) -> None:
    query = new_document_assignment_query()
    parameters = {"document_id": 404, "access_policy": policy}
    assert corpus.execute(query, parameters).rowcount == 1
    assert corpus.execute(query, parameters).rowcount == 0
    assert corpus.execute(
        "SELECT ACCESS_POLICY FROM SOFIA_DOCUMENT_CLASSIFICATIONS WHERE DOC_ID = 404"
    ).fetchall() == [(policy,)]


@pytest.mark.parametrize("doc_id,policy", [(999, "GENERAL"), (404, "UNKNOWN"), (202, "GENERAL")])
def test_guide_rejects_missing_invalid_or_existing_assignments_without_mutation(
    corpus: sqlite3.Connection, doc_id: int, policy: str
) -> None:
    before = tuple(corpus.iterdump())
    result = corpus.execute(
        new_document_assignment_query(), {"document_id": doc_id, "access_policy": policy}
    )
    assert result.rowcount == 0
    assert tuple(corpus.iterdump()) == before


@pytest.mark.parametrize("resource", ["DATALAB_TEST_WH", "DATALAB_TEST_ADMIN"])
def test_container_resource_contract_uses_test_environment(resource: str) -> None:
    guide = (ROOT / "docs" / "snowflake-container.md").read_text()
    assert f"`{resource}`" in guide
