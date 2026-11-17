from __future__ import annotations

from rag_chat.ui.markup import copy_button_html, metric_plugin_html, theme_css


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
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
    css = theme_css()

    for color in ("#17ABB5", "#1AAEB7", "#CFEFF0", "#EAF5F7", "#222222"):
        assert color in css
    assert "Helvetica Neue" in css
    assert "Suisse International" in css
    assert "Neue Montreal" in css
    assert "--brand-primary" in css
    assert ".sofia-onboarding" in css


def test_theme_css_adapts_custom_markup_to_the_active_dark_theme() -> None:
    light_css = theme_css("light")
    dark_css = theme_css("dark")

    assert "#FFFFFF" in light_css
    assert "#222222" in dark_css
    assert "#FFFFFF" in dark_css
    assert light_css != dark_css


def test_theme_css_defines_requested_semantic_typography_and_interaction_tokens() -> None:
    css = theme_css("light")

    for token in (
        "--brand-primary: #17ABB5",
        "--brand-accent: #1AAEB7",
        "--brand-soft: #CFEFF0",
        "--brand-surface: #EAF5F7",
        "--page: #F3F0EA",
        "--surface: #FFFFFF",
        "--surface-neutral: #F2F2F2",
        "--text-primary: #222222",
        "--text-secondary: #566467",
        "--text-accent: #0A6067",
        "--border: #D7D2C8",
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
    normal_text_pairs = (
        ("#222222", "#F3F0EA"),
        ("#566467", "#F3F0EA"),
        ("#0A6067", "#F3F0EA"),
        ("#FFFFFF", "#222222"),
        ("#EAF5F7", "#222222"),
        ("#CFEFF0", "#222222"),
        ("#222222", "#17ABB5"),
    )
    control_boundary_pairs = (
        ("#566467", "#F3F0EA"),
        ("#EAF5F7", "#222222"),
        ("#0A6067", "#F3F0EA"),
        ("#17ABB5", "#222222"),
    )

    assert all(_contrast_ratio(*pair) >= 4.5 for pair in normal_text_pairs)
    assert all(_contrast_ratio(*pair) >= 3 for pair in control_boundary_pairs)
