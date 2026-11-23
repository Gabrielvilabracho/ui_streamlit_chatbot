from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_application_is_a_consumer_of_the_external_agent_platform() -> None:
    guide = (REPOSITORY_ROOT / "docs" / "agent-platform-integration.md").read_text()

    assert not (REPOSITORY_ROOT / "agent_platform").exists()
    assert "agent-platform-config" in guide
    assert "DATALAB.TEST" in guide
    assert "DATALAB_TEST_WH" in guide
    assert "does not build or deploy agent" in guide
    assert "artifacts" in guide
