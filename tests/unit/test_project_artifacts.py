from __future__ import annotations

from pathlib import Path

from PIL import Image

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


def test_sofinco_brand_assets_are_wired_into_the_app_shell() -> None:
    mark_path = PROJECT_ROOT / "static/brand/sofinco-mark.png"
    wordmark_path = PROJECT_ROOT / "static/brand/sofinco_logo.png"

    assert mark_path.is_file()
    assert wordmark_path.is_file()

    with Image.open(mark_path).convert("RGBA") as mark:
        assert 0.8 <= mark.width / mark.height <= 1.2
        assert mark.getchannel("A").getextrema()[0] == 0
        assert mark.getpixel((0, 0))[3] == 0
    with Image.open(wordmark_path).convert("RGBA") as wordmark:
        assert wordmark.width > wordmark.height * 3
        alpha_bounds = wordmark.getchannel("A").getbbox()
        assert alpha_bounds is not None
        left, _top, right, bottom = alpha_bounds
        assert left >= 32
        assert wordmark.width - right >= 32
        assert wordmark.height - bottom >= 48
        colors = {
            color
            for _count, color in (
                wordmark.getcolors(maxcolors=wordmark.width * wordmark.height) or ()
            )
        }
        assert (24, 172, 185, 255) in colors
        assert not any(
            alpha > 0 and red >= 245 and green >= 245 and blue >= 245
            for red, green, blue, alpha in colors
        )

    entrypoint = read("app.py")
    streamlit_app = read("src/rag_chat/ui/streamlit_app.py")

    assert "page_icon=str(BRAND_MARK)" in entrypoint
    assert 'st.logo(str(BRAND_MARK), size="small", icon_image=str(BRAND_MARK))' in streamlit_app
    assert 'BRAND_WORDMARK = BRAND_ASSET_DIR / "sofinco_logo.png"' in streamlit_app
    assert 'alt="Sofinco wordmark"' in streamlit_app
    assert "width=180" in streamlit_app
    assert 'st.space("stretch")' in streamlit_app
    assert 'with st.container(horizontal=True, vertical_alignment="center")' in streamlit_app
    assert 'alt="Sofinco mark"' in streamlit_app
    assert "width=64" in streamlit_app
    assert "avatar=str(BRAND_MARK)" in streamlit_app


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


def test_trulens_grants_are_phased_and_allow_named_dataset_reads() -> None:
    grants = read("sql/trulens_observability_grants.sql")

    assert "Phase 1: before External Agent registration" in grants
    assert "Phase 2: after External Agent registration" in grants
    assert "Phase 3: after the named evaluation table exists" in grants
    assert (
        "GRANT SELECT ON TABLE SOFIA.OBSERVABILITY.SOFIA_EVAL_QUESTIONS\n"
        "    TO ROLE SOFIA_RAG_EVALUATOR;"
    ) in grants
    assert "GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE" not in "\n".join(
        line for line in grants.splitlines() if not line.lstrip().startswith("--")
    )


def test_streamlit_theme_exposes_complete_native_light_and_dark_modes() -> None:
    theme = read(".streamlit/config.toml")

    assert "[theme.light]" in theme
    assert "[theme.dark]" in theme
    assert "[theme.light.sidebar]" in theme
    assert "[theme.dark.sidebar]" in theme
    assert 'backgroundColor = "#FFFFFF"' in theme
    assert 'backgroundColor = "#222222"' in theme
    assert theme.count('paddingTop = "0.5rem"') == 2


def test_streamlit_theme_uses_requested_semantic_palette_and_local_fonts() -> None:
    theme = read(".streamlit/config.toml")

    for expected in (
        'backgroundColor = "#FFFFFF"',
        'secondaryBackgroundColor = "#F2F2F2"',
        'textColor = "#222222"',
        'linkColor = "#222222"',
        'borderColor = "#222222"',
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
        'redColor = "#222222"',
        'orangeColor = "#222222"',
        'greenColor = "#222222"',
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
