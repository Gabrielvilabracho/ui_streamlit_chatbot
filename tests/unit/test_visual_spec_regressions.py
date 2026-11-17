from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_s10_components_use_semantic_color_tokens() -> None:
    source = (ROOT / "src/rag_chat/ui/markup.py").read_text()
    styles = source.split('styles = """', 1)[1].split('""".strip()', 1)[0]
    direct_color = r"(?:color|background|border-color|outline):\s*#[0-9A-Fa-f]{6}"

    assert not re.search(direct_color, styles)


def test_s11_display_scale_is_consumed() -> None:
    source = (ROOT / "src/rag_chat/ui/markup.py").read_text()

    assert "--size-display:" in source
    assert "var(--size-display)" in source


def test_s13_fonts_record_authoritative_provenance() -> None:
    provenance = (ROOT / "static/fonts/PROVENANCE.md").read_text()

    assert "https://github.com/googlefonts/manrope" in provenance
    assert "https://github.com/IBM/plex" in provenance
    assert len(re.findall(r"\b[0-9a-f]{64}\b", provenance.lower())) >= 3
