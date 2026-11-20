from __future__ import annotations

import re
import tomllib
from pathlib import Path

from rag_chat.ui.markup import copy_button_html, metric_plugin_html, theme_css


def _theme_tokens(mode: str) -> dict[str, str]:
    matches = re.findall(
        r"(--[\w-]+):\s*(?:light-dark\((#[0-9A-Fa-f]{6}),\s*(#[0-9A-Fa-f]{6})\)"
        r"|(#[0-9A-Fa-f]{6}))",
        theme_css(mode),
    )
    return {
        name: fixed or (dark if mode == "dark" else light) for name, light, dark, fixed in matches
    }


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_copy_button_encodes_untrusted_answer_text_before_javascript_insertion() -> None:
    markup = copy_button_html("answer-1", "</script><script>alert('xss')</script>")

    assert "</script><script>alert" not in markup
    assert "navigator.clipboard.writeText" in markup
    assert "copy-answer-1" not in markup
    assert 'button.setAttribute("aria-busy", "true")' in markup
    assert 'button.dataset.state = "loading"' in markup
    assert "Copying…" in markup
    assert "Copy failed" in markup


def test_metric_plugin_renders_passive_token_and_latency_values() -> None:
    markup = metric_plugin_html(
        prompt_tokens=123,
        completion_tokens=45,
        latency_ms=678.9,
    )

    assert "Input 123" in markup
    assert "Output 45" in markup
    assert "679 ms" in markup
    assert "<script" not in markup


def test_theme_css_carries_the_sofia_semantic_palette_and_typography() -> None:
    css = theme_css("dark")

    for color in ("#17ABB5", "#1AAEB7", "#CFEFF0", "#EAF5F7", "#222222"):
        assert color in css
    assert "Helvetica Neue" in css
    assert "Suisse International" in css
    assert "Neue Montreal" in css
    assert "--brand-primary" in css
    assert ".sofia-onboarding" in css


def test_theme_css_follows_native_color_scheme_without_a_python_rerun() -> None:
    light_css = theme_css("light")
    dark_css = theme_css("dark")

    assert "#FFFFFF" in light_css
    assert "#222222" in dark_css
    assert "#FFFFFF" in dark_css
    assert light_css == dark_css == theme_css(None)
    assert "light-dark(#FFFFFF, #222222)" in light_css
    assert "light-dark(#222222, #17ABB5)" in light_css
    assert "color-scheme:" not in light_css


def test_dark_custom_palette_preserves_existing_colors() -> None:
    assert _theme_tokens("dark") == {
        "--brand-primary": "#17ABB5",
        "--brand-accent": "#1AAEB7",
        "--brand-soft": "#CFEFF0",
        "--brand-surface": "#EAF5F7",
        "--on-brand-text": "#222222",
        "--brand-muted-text": "#566467",
        "--brand-accent-text": "#0A6067",
        "--brand-control-border": "#566467",
        "--on-state-text": "#FFFFFF",
        "--state-error-surface": "#B42318",
        "--state-success-surface": "#166534",
        "--state-warning-surface": "#8A4B08",
        "--page": "#222222",
        "--surface": "#2B2B2B",
        "--surface-neutral": "#333333",
        "--text-primary": "#FFFFFF",
        "--text-secondary": "#EAF5F7",
        "--text-accent": "#CFEFF0",
        "--border": "#4B4F55",
        "--information-surface": "#2B2B2B",
        "--badge-surface": "#333333",
        "--control-surface": "#2B2B2B",
        "--control-border": "#EAF5F7",
        "--control-hover": "#333333",
        "--control-active": "#4B4F55",
        "--focus-ring": "#17ABB5",
        "--state-error": "#FFB4AB",
        "--state-success": "#A7F3D0",
        "--state-warning": "#FDE68A",
    }


def test_theme_css_defines_requested_semantic_typography_and_interaction_tokens() -> None:
    css = theme_css("light")

    tokens = _theme_tokens("light")
    for token, color in {
        "--brand-primary": "#222222",
        "--brand-accent": "#222222",
        "--brand-soft": "#F2F2F2",
        "--brand-surface": "#FFFFFF",
        "--page": "#FFFFFF",
        "--surface": "#FFFFFF",
        "--surface-neutral": "#F2F2F2",
        "--text-primary": "#222222",
        "--text-secondary": "#222222",
        "--text-accent": "#222222",
        "--border": "#222222",
    }.items():
        assert tokens[token] == color

    for token in (
        '--font-display: "Manrope", "Helvetica Neue", Arial, sans-serif',
        '--font-interface: "Helvetica Neue", "Suisse International"',
        '--font-mono: "IBM Plex Mono", Consolas, monospace',
        "font-variant-numeric: tabular-nums",
        "clamp(2.25rem, 4vw, 3.5rem)",
        "max-width: 70ch",
        "min-height: 2.75rem",
        ":focus-visible",
        ":active",
        ":disabled",
    ):
        assert token in css

    assert "linear-gradient" not in css
    assert "radial-gradient" not in css


def test_requested_text_and_control_colors_meet_wcag_contrast_thresholds() -> None:
    light = _theme_tokens("light")
    dark = _theme_tokens("dark")
    normal_text_pairs = (
        (light["--text-primary"], light["--page"]),
        (light["--text-secondary"], light["--page"]),
        (light["--text-accent"], light["--page"]),
        (light["--brand-muted-text"], light["--brand-surface"]),
        (light["--on-brand-text"], light["--brand-soft"]),
        (dark["--text-primary"], dark["--page"]),
        (dark["--text-secondary"], dark["--page"]),
        (dark["--text-accent"], dark["--page"]),
        (dark["--on-brand-text"], dark["--brand-primary"]),
    )
    control_boundary_pairs = (
        (light["--control-border"], light["--control-surface"]),
        (light["--focus-ring"], light["--page"]),
        (dark["--control-border"], dark["--control-surface"]),
        (dark["--focus-ring"], dark["--page"]),
    )

    assert all(_contrast_ratio(*pair) >= 4.5 for pair in normal_text_pairs)
    assert all(_contrast_ratio(*pair) >= 3 for pair in control_boundary_pairs)


def test_light_custom_markup_uses_only_monochrome_colors() -> None:
    tokens = _theme_tokens("light")

    assert tokens["--page"] == "#FFFFFF"
    assert tokens["--text-primary"] == _theme_tokens("dark")["--page"] == "#222222"
    assert all(color[1:3] == color[3:5] == color[5:7] for color in tokens.values())
    assert theme_css() == theme_css("light")


def test_native_light_theme_has_white_main_and_dark_sidebar_with_readable_controls() -> None:
    config_path = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"
    theme = tomllib.loads(config_path.read_text())["theme"]
    light = theme["light"]
    sidebar = light["sidebar"]

    assert light["backgroundColor"] == "#FFFFFF"
    assert light["textColor"] == sidebar["backgroundColor"] == theme["dark"]["backgroundColor"]
    assert sidebar["textColor"] == "#FFFFFF"
    for palette in (light, sidebar):
        colors = [value for key, value in palette.items() if key.endswith("Color")]
        assert all(color[1:3] == color[3:5] == color[5:7] for color in colors)
        assert _contrast_ratio(palette["textColor"], palette["backgroundColor"]) >= 4.5
        assert _contrast_ratio(palette["textColor"], palette["secondaryBackgroundColor"]) >= 4.5
        assert _contrast_ratio(palette["linkColor"], palette["backgroundColor"]) >= 4.5
        assert _contrast_ratio("#FFFFFF", palette["primaryColor"]) >= 4.5
        assert _contrast_ratio(palette["primaryColor"], palette["backgroundColor"]) >= 3
