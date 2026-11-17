"""Small, sanitized visual elements without business behavior."""

from __future__ import annotations

import base64
import hashlib
import html


def theme_css() -> str:
    """Return the explicitly requested Sof~IA semantic token layer."""

    return """
<style>
:root {
  --sofia-primary: #17ABB5;
  --sofia-accent: #1AAEB7;
  --sofia-primary-soft: #CFEFF0;
  --sofia-accent-surface: #EAF5F7;
  --sofia-ink: #222222;
  --sofia-neutral: #F2F2F2;
  --sofia-base: #FFFFFF;
  --sofia-cloud: #DDD8CC;
  --sofia-ivory: #E8E8DE;
  --sofia-wave: #F3F0EA;
  --sofia-fog: #F4F4F4;
  --sofia-font: "Helvetica Neue", "Suisse International", "Neue Montreal", Arial, sans-serif;
}

html, body, button, input, textarea, select {
  font-family: var(--sofia-font);
}

.sofia-onboarding {
  position: relative;
  overflow: hidden;
  margin: 0.5rem 0 2rem;
  padding: clamp(1.25rem, 3vw, 2.25rem);
  border: 1px solid var(--sofia-primary-soft);
  border-radius: 1.25rem;
  background:
    radial-gradient(circle at 92% 0%, rgba(23, 171, 181, 0.18), transparent 34%),
    linear-gradient(135deg, var(--sofia-base), var(--sofia-accent-surface));
  color: var(--sofia-ink);
}

.sofia-onboarding__eyebrow {
  margin: 0 0 0.75rem;
  color: #0B747B;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.sofia-onboarding__copy {
  max-width: 62ch;
  margin: 0;
  color: #35575A;
  line-height: 1.65;
}

.sofia-copy-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.25rem;
  padding: 0.35rem 0.8rem;
  border: 1px solid var(--sofia-primary-soft);
  border-radius: 999px;
  background: var(--sofia-base);
  color: var(--sofia-ink);
  font: 600 0.78rem/1 var(--sofia-font);
  cursor: pointer;
}

.sofia-copy-button:hover,
.sofia-copy-button:focus-visible {
  border-color: var(--sofia-primary);
  color: #0B747B;
  outline: none;
}

.sofia-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem;
  min-height: 2.25rem;
  align-items: center;
}

.sofia-metrics__item {
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--sofia-primary-soft);
  border-radius: 999px;
  background: var(--sofia-accent-surface);
  color: #35575A;
  font: 600 0.68rem/1 var(--sofia-font);
  white-space: nowrap;
}
</style>
""".strip()


def onboarding_html() -> str:
    return """
<section class="sofia-onboarding" aria-label="Getting started">
  <p class="sofia-onboarding__eyebrow">Grounded finance knowledge</p>
  <p class="sofia-onboarding__copy">
    Ask a policy or process question. Sof~IA searches approved Snowflake knowledge,
    builds a grounded answer, and keeps every source visible for review.
  </p>
</section>
""".strip()


def copy_button_html(message_id: str, content: str) -> str:
    """Build a clipboard control without interpolating answer text into JavaScript."""

    element_id = "copy-" + hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:16]
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return f"""
<button id="{element_id}" class="sofia-copy-button" type="button" aria-label="Copy answer">
  Copy
</button>
<script>
(() => {{
  const button = document.getElementById("{element_id}");
  if (!button || button.dataset.ready === "true") return;
  button.dataset.ready = "true";
  button.addEventListener("click", async () => {{
    const bytes = Uint8Array.from(atob("{encoded_content}"), character => character.charCodeAt(0));
    const text = new TextDecoder().decode(bytes);
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
    window.setTimeout(() => {{ button.textContent = "Copy"; }}, 1400);
  }});
}})();
</script>
""".strip()


def metric_plugin_html(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
) -> str:
    """Render passive usage metadata; no client event or provider call is involved."""

    input_label = html.escape(f"Input {prompt_tokens:,}")
    output_label = html.escape(f"Output {completion_tokens:,}")
    latency_label = html.escape(f"{latency_ms:,.0f} ms")
    return f"""
<div class="sofia-metrics" aria-label="Model usage">
  <span class="sofia-metrics__item">{input_label}</span>
  <span class="sofia-metrics__item">{output_label}</span>
  <span class="sofia-metrics__item">{latency_label}</span>
</div>
""".strip()
