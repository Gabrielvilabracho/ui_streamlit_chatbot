from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = REPOSITORY_ROOT / "agent_platform"
BUILDER = PLATFORM_ROOT / "scripts" / "build_agent_specs.py"


def _build(platform_root: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(platform_root / "scripts" / "build_agent_specs.py"),
            "--output",
            str(output),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_builder_creates_deterministic_general_agent_artifacts_in_datalab_test(
    tmp_path: Path,
) -> None:
    first = _build(PLATFORM_ROOT, tmp_path / "first")
    second = _build(PLATFORM_ROOT, tmp_path / "second")

    assert first.returncode == second.returncode == 0, first.stderr
    first_spec = (tmp_path / "first" / "sofia-general" / "agent-spec.json").read_text()
    second_spec = (tmp_path / "second" / "sofia-general" / "agent-spec.json").read_text()
    artifact = json.loads(first_spec)

    assert first_spec == second_spec
    assert artifact["agent"]["name"] == "SOFIA_GENERAL_AGENT"
    assert artifact["access"] == {
        "database": "DATALAB",
        "schema": "TEST",
        "warehouse": "DATALAB_TEST_WH",
        "caller_role": "DATALAB_TEST_ADMIN",
        "policy": "GENERAL",
        "search_service": "DATALAB.TEST.SOFIA_GENERAL_SEARCH",
    }
    assert artifact["evaluation"]["dataset"] == "DATALAB.TEST.SOFIA_EVALUATION_CASES"
    assert artifact["project"]["name"] == "sofia-knowledge"
    assert len(artifact["prompts"]["layers"]) == 4


def test_builder_rejects_prompt_path_traversal_without_writing_an_artifact(tmp_path: Path) -> None:
    platform_root = tmp_path / "agent_platform"
    shutil.copytree(PLATFORM_ROOT, platform_root)
    manifest = platform_root / "agents" / "sofia-general" / "agent.toml"
    manifest.write_text(
        manifest.read_text().replace("prompts/global/safety-and-evidence.md", "../secret.md")
    )
    output = tmp_path / "generated"

    result = _build(platform_root, output)

    assert result.returncode != 0
    assert "repository-relative prompt path" in result.stderr
    assert not output.exists()
