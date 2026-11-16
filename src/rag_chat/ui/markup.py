"""Small, sanitized visual elements without business behavior."""

from __future__ import annotations

import base64
import hashlib
import html


def theme_css() -> str:
    """Return the explicitly requested CONTAVIA semantic token layer."""

    return """
<style>
:root {
  --contavia-primary: #17ABB5;
  --contavia-accent: #1AAEB7;
  --contavia-primary-soft: #CFEFF0;
  --contavia-accent-surface: #EAF5F7;
  --contavia-ink: #222222;
  --contavia-neutral: #F2F2F2;
  --contavia-base: #FFFFFF;
  --contavia-cloud: #DDD8CC;
  --contavia-ivory: #E8E8DE;
  --contavia-wave: #F3F0EA;
  --contavia-fog: #F4F4F4;
  --contavia-font: "Helvetica Neue", "Suisse International", "Neue Montreal", Arial, sans-serif;
}

html, body, button, input, textarea, select {
  font-family: var(--contavia-font);
}

.contavia-onboarding {
  position: relative;
  overflow: hidden;
  margin: 0.5rem 0 2rem;
  padding: clamp(1.25rem, 3vw, 2.25rem);
  border: 1px solid var(--contavia-primary-soft);
  border-radius: 1.25rem;
  background:
    radial-gradient(circle at 92% 0%, rgba(23, 171, 181, 0.18), transparent 34%),
    linear-gradient(135deg, var(--contavia-base), var(--contavia-accent-surface));
  color: var(--contavia-ink);
}

.contavia-onboarding__eyebrow {
  margin: 0 0 0.75rem;
  color: #0B747B;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.contavia-onboarding__copy {
  max-width: 62ch;
  margin: 0;
  color: #35575A;
  line-height: 1.65;
}

.contavia-copy-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.25rem;
  padding: 0.35rem 0.8rem;
  border: 1px solid var(--contavia-primary-soft);
  border-radius: 999px;
  background: var(--contavia-base);
  color: var(--contavia-ink);
  font: 600 0.78rem/1 var(--contavia-font);
  cursor: pointer;
}

.contavia-copy-button:hover,
.contavia-copy-button:focus-visible {
  border-color: var(--contavia-primary);
  color: #0B747B;
  outline: none;
}

.contavia-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem;
  min-height: 2.25rem;
  align-items: center;
}

.contavia-metrics__item {
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--contavia-primary-soft);
  border-radius: 999px;
  background: var(--contavia-accent-surface);
  color: #35575A;
  font: 600 0.68rem/1 var(--contavia-font);
  white-space: nowrap;
}
</style>
""".strip()


def onboarding_html() -> str:
    return """
<section class="contavia-onboarding" aria-label="Getting started">
  <p class="contavia-onboarding__eyebrow">Grounded finance knowledge</p>
  <p class="contavia-onboarding__copy">
    Ask a policy or process question. CONTAVIA searches approved Snowflake knowledge,
    builds a grounded answer, and keeps every source visible for review.
  </p>
</section>
""".strip()


def copy_button_html(message_id: str, content: str) -> str:
    """Build a clipboard control without interpolating answer text into JavaScript."""

    element_id = "copy-" + hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:16]
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return f"""
<button id="{element_id}" class="contavia-copy-button" type="button" aria-label="Copy answer">
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
<div class="contavia-metrics" aria-label="Model usage">
  <span class="contavia-metrics__item">{input_label}</span>
  <span class="contavia-metrics__item">{output_label}</span>
  <span class="contavia-metrics__item">{latency_label}</span>
</div>
""".strip()
