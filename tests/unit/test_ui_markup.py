from __future__ import annotations

from rag_chat.ui.markup import copy_button_html, metric_plugin_html, theme_css


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
    assert "--sofia-primary" in css
    assert ".sofia-onboarding" in css
