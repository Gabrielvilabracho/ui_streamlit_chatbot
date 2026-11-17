"""Small, sanitized visual elements without business behavior."""

from __future__ import annotations

import base64
import hashlib
import html


def theme_css(theme_type: str | None = "light") -> str:
    """Return Sof~IA tokens with theme-safe custom element styling."""

    shared_tokens = """
  --brand-primary: #17ABB5;
  --brand-accent: #1AAEB7;
  --brand-soft: #CFEFF0;
  --brand-surface: #EAF5F7;
  --on-brand-text: #222222;
  --brand-muted-text: #566467;
  --brand-accent-text: #0A6067;
  --brand-control-border: #566467;
  --on-state-text: #FFFFFF;
  --state-error-surface: #B42318;
  --state-success-surface: #166534;
  --state-warning-surface: #8A4B08;
  --font-display: "Manrope", "Helvetica Neue", Arial, sans-serif;
  --font-interface: "Helvetica Neue", "Suisse International", "Neue Montreal", Arial, sans-serif;
  --font-mono: "IBM Plex Mono", Consolas, monospace;
  --size-display: clamp(2.75rem, 6vw, 5rem);
  --size-h1: clamp(2.25rem, 4vw, 3.5rem);
  --size-h2: clamp(1.75rem, 3vw, 2.5rem);
  --size-h3: 1.375rem;
  --size-body: 1rem;
  --size-small: 0.875rem;
  --size-label: 0.75rem;
""".strip()

    if theme_type == "dark":
        theme_tokens = """
  --page: #222222;
  --surface: #2B2B2B;
  --surface-neutral: #333333;
  --text-primary: #FFFFFF;
  --text-secondary: #EAF5F7;
  --text-accent: #CFEFF0;
  --border: #4B4F55;
  --information-surface: #2B2B2B;
  --badge-surface: #333333;
  --control-surface: #2B2B2B;
  --control-border: #EAF5F7;
  --control-hover: #333333;
  --control-active: #4B4F55;
  --focus-ring: #17ABB5;
  --state-error: #FFB4AB;
  --state-success: #A7F3D0;
  --state-warning: #FDE68A;
""".strip()
    else:
        theme_tokens = """
  --page: #F3F0EA;
  --surface: #FFFFFF;
  --surface-neutral: #F2F2F2;
  --text-primary: #222222;
  --text-secondary: #566467;
  --text-accent: #0A6067;
  --border: #D7D2C8;
  --information-surface: #EAF5F7;
  --badge-surface: #CFEFF0;
  --control-surface: #FFFFFF;
  --control-border: #566467;
  --control-hover: #F2F2F2;
  --control-active: #CFEFF0;
  --focus-ring: #0A6067;
  --state-error: #B42318;
  --state-success: #166534;
  --state-warning: #8A4B08;
""".strip()

    styles = """
html, body, button, input, textarea, select {
  font-family: var(--font-interface);
}

body {
  font-size: var(--size-body);
  line-height: 1.6;
}

h1, h2, h3 {
  font-family: var(--font-display);
  color: inherit;
  text-wrap: balance;
}

h1 {
  font-size: var(--size-h1);
  font-weight: 500;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

h1:first-of-type {
  font-size: var(--size-display);
}

h2 {
  font-size: var(--size-h2);
  font-weight: 500;
  line-height: 1.15;
  letter-spacing: -0.025em;
}

h3 {
  font-size: var(--size-h3);
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: -0.015em;
}

p {
  max-width: 70ch;
  color: inherit;
  font-size: var(--size-body);
  line-height: 1.6;
  text-wrap: pretty;
}

small {
  font-size: var(--size-small);
}

label, code, pre, kbd, samp {
  font-family: var(--font-mono);
}

label {
  font-size: var(--size-label);
  font-weight: 500;
  line-height: 1.4;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

button, input, textarea, select {
  min-height: 2.75rem;
}

a:focus-visible,
button:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible {
  outline: 3px solid currentColor;
  outline-offset: 3px;
}

.sofia-onboarding {
  margin: 0.5rem 0 2rem;
  padding: clamp(1.25rem, 3vw, 2.25rem);
  border: 1px solid var(--brand-control-border);
  border-left: 0.25rem solid var(--brand-primary);
  border-radius: 0.75rem;
  background: var(--brand-surface);
  color: var(--on-brand-text);
}

.sofia-onboarding__eyebrow {
  margin: 0 0 0.75rem;
  color: var(--brand-accent-text);
  font: 500 var(--size-label)/1.4 var(--font-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.sofia-onboarding__copy {
  max-width: 70ch;
  margin: 0;
  color: var(--brand-muted-text);
  font: 400 var(--size-body)/1.6 var(--font-interface);
}

.sofia-copy-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.75rem;
  padding: 0.625rem 1rem;
  border: 1px solid currentColor;
  border-radius: 0.75rem;
  background: transparent;
  color: inherit;
  font: 600 var(--size-small)/1.25 var(--font-interface);
  cursor: pointer;
}

.sofia-copy-button:hover {
  border-color: var(--brand-primary);
  background: var(--brand-soft);
  color: var(--on-brand-text);
}

.sofia-copy-button:active {
  background: var(--brand-surface);
  color: var(--on-brand-text);
}

.sofia-copy-button:focus-visible {
  border-color: var(--brand-primary);
  outline: 3px solid currentColor;
  outline-offset: 3px;
}

.sofia-copy-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.sofia-copy-button[aria-pressed="true"] {
  border-color: var(--brand-primary);
  background: var(--brand-soft);
  color: var(--on-brand-text);
}

.sofia-copy-button[data-state="loading"] {
  cursor: wait;
}

.sofia-copy-button[data-state="success"] {
  border-color: var(--state-success-surface);
  background: var(--state-success-surface);
  color: var(--on-state-text);
}

.sofia-copy-button[data-state="warning"] {
  border-color: var(--state-warning-surface);
  background: var(--state-warning-surface);
  color: var(--on-state-text);
}

.sofia-copy-button[data-state="error"] {
  border-color: var(--state-error-surface);
  background: var(--state-error-surface);
  color: var(--on-state-text);
}

.sofia-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
  min-height: 2.75rem;
  align-items: center;
}

.sofia-metrics__item {
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--brand-control-border);
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--on-brand-text);
  font: 500 var(--size-label)/1.4 var(--font-mono);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

@media (max-width: 40rem) {
  .sofia-onboarding {
    margin-bottom: 1.5rem;
    padding: 1.25rem;
  }

  .sofia-metrics {
    justify-content: flex-start;
  }
}
""".strip()
    return (
        f"<style>\n:root {{\n{shared_tokens}\n{theme_tokens}\n}}"
        f"\n\n{styles}\n</style>"
    )


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
    button.disabled = true;
    button.dataset.state = "loading";
    button.setAttribute("aria-busy", "true");
    button.textContent = "Copying…";
    try {{
      await navigator.clipboard.writeText(text);
      button.dataset.state = "success";
      button.textContent = "Copied";
    }} catch {{
      button.dataset.state = "error";
      button.textContent = "Copy failed";
    }} finally {{
      button.removeAttribute("aria-busy");
      window.setTimeout(() => {{
        button.disabled = false;
        button.dataset.state = "idle";
        button.textContent = "Copy";
      }}, 1400);
    }}
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
