from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "rag_chat"


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_domain_and_application_do_not_import_outer_frameworks() -> None:
    protected_files = [
        *sorted((SRC_ROOT / "domain").glob("*.py")),
        *sorted((SRC_ROOT / "application").glob("*.py")),
    ]

    assert protected_files, "Expected domain and application modules to exist"
    for path in protected_files:
        forbidden = imported_roots(path) & {"streamlit", "snowflake", "trulens"}
        assert not forbidden, f"{path.relative_to(PROJECT_ROOT)} imports {sorted(forbidden)}"
