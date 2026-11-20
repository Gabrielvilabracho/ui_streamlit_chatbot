# Architecture and extension points

The design keeps the Streamlit rerun model and Snowflake provider details at the edges. Domain and application code can be tested without credentials, a browser, or a Snowflake account.

## Request flow

```text
Streamlit chat input
        │
        ▼
RagOrchestrator ──► Guardrail.validate_input
        │
        ├──────────► Retriever.retrieve
        │                │
        │                └── Cortex Search Service
        │
        ├──────────► Domain prompt template
        │
        ├──────────► Generator.generate
        │                │
        │                └── AI_COMPLETE(show_details => TRUE)
        │
        ├──────────► Guardrail.validate_output
        │
        └──────────► Telemetry.record_success / record_failure
                         │
                         ▼
              RagAnswer + sources + usage + latency
```

Each orchestration step emits its existing start/completion events through the shared hook dispatcher. The Streamlit adapter consumes the request's `on_progress` callback to present progress.

## Dependency rule

| Source layer | May depend on | Must not depend on |
| --- | --- | --- |
| Domain | Python standard library | Application, infrastructure, Streamlit, Snowflake |
| Application | Domain and application ports | Streamlit, concrete Snowflake SDK types |
| Infrastructure | Domain/application contracts and Snowflake SDKs | Streamlit UI state |
| UI | Domain/application contracts and Streamlit | Snowflake SDK implementation details |
| Composition | Every outer adapter needed to assemble the runtime | Business decisions that belong in domain/application |

`tests/architecture/test_clean_architecture_boundaries.py` enforces the critical domain/application import boundary.

## Central prompt policy

`src/rag_chat/domain/prompts.py` owns `SYSTEM_PROMPT` and the grounded prompt format. It requires numbered citations and an explicit insufficient-context response. Provider adapters receive the completed prompt; they do not define business behavior.

## Extension points

The ports in `src/rag_chat/application/ports.py` are the stable injection seams:

- `Retriever`: replace Cortex Search or add metadata filters.
- `Generator`: change model providers without changing the use case.
- `Guardrail`: compose PII, prompt-injection, policy, or output validators.
- `Telemetry`: emit OpenTelemetry spans, Snowflake event records, or vendor metrics.

New adapters should translate provider exceptions into domain-safe errors at the infrastructure boundary.

### Shared hooks

`src/rag_chat/application/hooks/` owns the progress callback contract (`progress.py`) and ordered dispatch (`dispatcher.py`). Register reusable callbacks with `hooks=(callback, ...)` when constructing `RagOrchestrator` or `CortexAgentService`; `build_orchestrator` forwards the same option. Both services use this dispatcher at their existing event points, reusing the domain's `ProgressEvent`.

Configured hooks run in registration order, followed by the optional per-request `on_progress` callback. Request callbacks are never registered permanently, including when a service is cached. Hook exceptions propagate; hooks do not silently swallow failures. Register only callbacks safe for the service's lifetime, not user-specific UI state. The agent path still reports only its actual generation stage, not local retrieval steps it cannot observe.

### Shared guardrails

`src/rag_chat/application/guardrails/` groups reusable validation:

- `input.py`: reject empty questions or questions exceeding 8,000 trimmed characters.
- `output.py`: reject empty responses or responses exceeding 32,000 trimmed characters.
- `pipeline.py`: run configured input/output rules in order, stopping at the first rejection; `BaselineGuardrail` composes the existing default checks.

Both service paths keep the baseline enabled by default. The old `application.defaults.BaselineGuardrail` import remains available. Supply a custom `Guardrail` through `guardrail=` to either service or `build_orchestrator`; `GuardrailPipeline` accepts separate tuples of input/output validator callables. A custom pipeline replaces the baseline, so include its validators explicitly when extending it:

```python
from rag_chat.application.guardrails import GuardrailPipeline, InputGuardrail, OutputGuardrail

guardrail = GuardrailPipeline(
    input_rules=(InputGuardrail().validate,),
    output_rules=(OutputGuardrail().validate,),
)
```

These are structural checks, not PII or prompt-injection detection. Snowflake identity, approved-role, provider-payload, and citation checks stay in `infrastructure/snowflake/cortex_agent.py`; general guardrails never replace those controls.

## Streamlit state

`UiMessage` stores only the data required to replay a conversation: role, content, original question, citations, model, token counts, and latency. Retry replaces the selected assistant message while preserving the earlier conversation. Every repeated widget key is derived from a stable message ID.

## Visual system

`.streamlit/config.toml` carries native Streamlit theme tokens. `src/rag_chat/ui/markup.py` adds only the requested Sof~IA-specific typography, onboarding, copy control, and passive metric badges.

Complete `[theme.light]` and `[theme.dark]` sections keep Streamlit's native appearance selector available in **Settings → Theme**. Custom markup reads `st.context.theme.type` and selects matching semantic tokens without private Streamlit selectors or theme-changing JavaScript.

Semantic values retain the approved Sof~IA palette reference:

| Role | Value |
| --- | --- |
| Primary action | `#17ABB5` |
| Secondary accent | `#1AAEB7` |
| Primary soft | `#CFEFF0` |
| Accent surface | `#EAF5F7` |
| Primary text | `#222222` |
| Neutral/base surfaces | `#F2F2F2`, `#FFFFFF` |
| Typography | Helvetica Neue, Suisse International, Neue Montreal, Arial, sans-serif |
