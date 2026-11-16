from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_explains_the_local_run_path_and_architecture_boundaries() -> None:
    readme = read("README.md")

    assert "uv sync --extra dev" in readme
    assert "uv run streamlit run app.py" in readme
    assert "Clean Architecture" in readme
    assert "domain" in readme
    assert "application" in readme
    assert "infrastructure" in readme
    assert "ui" in readme


def test_snowflake_bootstrap_uses_cortex_search_ai_complete_and_least_privilege() -> None:
    bootstrap = read("sql/bootstrap.sql")

    assert "CREATE CORTEX SEARCH SERVICE" in bootstrap
    assert "TARGET_LAG = '1 hour'" in bootstrap
    assert "CHANGE_TRACKING = TRUE" in bootstrap
    assert "SNOWFLAKE.CORTEX_USER" in bootstrap
    assert "GRANT USAGE ON CORTEX SEARCH SERVICE" in bootstrap
    assert "CONTAVIA_RAG_APP" in bootstrap


def test_configuration_examples_name_every_required_setting_without_real_secrets() -> None:
    secrets_example = read("config/snowflake-settings.example.toml")
    environment_example = read("config/environment-variables.example.txt")

    for name in (
        "account",
        "user",
        "password",
        "warehouse",
        "database",
        "schema",
        "search_service",
    ):
        assert name in secrets_example
        assert f"SNOWFLAKE_{name.upper()}" in environment_example

    assert "replace-me" in secrets_example
    assert "very-secret" not in secrets_example
    assert "very-secret" not in environment_example


def test_operations_runbook_documents_timeout_feedback_and_safe_telemetry() -> None:
    runbook = read("docs/operations.md")

    assert "timeout" in runbook.lower()
    assert "st.error" in runbook
    assert "feedback" in runbook.lower()
    assert "prompt content" in runbook.lower()
    assert "credentials" in runbook.lower()
