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
    assert "SOFIA_RAG_APP" in bootstrap


def test_operational_artifacts_use_the_sofia_brand_and_identifiers() -> None:
    operational_paths = (
        "README.md",
        "app.py",
        "config/environment-variables.example.txt",
        "config/snowflake-settings.example.toml",
        "docs/architecture.md",
        "docs/operations.md",
        "pyproject.toml",
        "sql/bootstrap.sql",
        "src/rag_chat/__init__.py",
        "src/rag_chat/domain/prompts.py",
        "src/rag_chat/ui/markup.py",
        "src/rag_chat/ui/streamlit_app.py",
    )
    content = "\n".join(read(path) for path in operational_paths)

    assert "CONTAVIA" not in content.upper()
    assert "Sof~IA" in content
    assert "SOFIA_RAG_APP" in content
    assert 'name = "sofia-cortex-rag"' in content


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


def test_streamlit_theme_exposes_complete_native_light_and_dark_modes() -> None:
    theme = read(".streamlit/config.toml")

    assert "[theme.light]" in theme
    assert "[theme.dark]" in theme
    assert "[theme.light.sidebar]" in theme
    assert "[theme.dark.sidebar]" in theme
    assert 'backgroundColor = "#F3F0EA"' in theme
    assert 'backgroundColor = "#222222"' in theme


def test_streamlit_theme_uses_requested_semantic_palette_and_local_fonts() -> None:
    theme = read(".streamlit/config.toml")

    for expected in (
        'backgroundColor = "#F3F0EA"',
        'secondaryBackgroundColor = "#F2F2F2"',
        'textColor = "#222222"',
        'linkColor = "#0A6067"',
        'borderColor = "#566467"',
        'backgroundColor = "#222222"',
        'secondaryBackgroundColor = "#2B2B2B"',
        'textColor = "#FFFFFF"',
        'linkColor = "#CFEFF0"',
        'borderColor = "#EAF5F7"',
        'font = "Helvetica Neue, Suisse International, Neue Montreal, Manrope, sans-serif"',
        'headingFont = "Manrope, Helvetica Neue, sans-serif"',
        'codeFont = "IBM Plex Mono, monospace"',
        "[[theme.fontFaces]]",
        "enableStaticServing = true",
        'redColor = "#B42318"',
        'orangeColor = "#8A4B08"',
        'greenColor = "#166534"',
    ):
        assert expected in theme

    for relative_path in (
        "static/fonts/Manrope-Variable.ttf",
        "static/fonts/IBMPlexMono-Regular.ttf",
        "static/fonts/IBMPlexMono-Medium.ttf",
        "static/fonts/OFL-Manrope.txt",
        "static/fonts/OFL-IBMPlexMono.txt",
        "static/fonts/PROVENANCE.md",
    ):
        assert (PROJECT_ROOT / relative_path).is_file()

    provenance = read("static/fonts/PROVENANCE.md")
    assert "https://github.com/googlefonts/manrope" in provenance
    assert "https://github.com/IBM/plex" in provenance
