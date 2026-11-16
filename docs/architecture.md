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

Every completed orchestration step is emitted through a callback. The Streamlit adapter renders those events as disabled `st.checkbox` items inside `st.status`.

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

## Streamlit state

`UiMessage` stores only the data required to replay a conversation: role, content, original question, citations, model, token counts, and latency. Retry replaces the selected assistant message while preserving the earlier conversation. Every repeated widget key is derived from a stable message ID.

## Visual system

`.streamlit/config.toml` carries native Streamlit theme tokens. `src/rag_chat/ui/markup.py` adds only the requested CONTAVIA-specific typography, onboarding, copy control, and passive metric badges.

Semantic values are sourced from the provided CONTAVIA reference:

| Role | Value |
| --- | --- |
| Primary action | `#17ABB5` |
| Secondary accent | `#1AAEB7` |
| Primary soft | `#CFEFF0` |
| Accent surface | `#EAF5F7` |
| Primary text | `#222222` |
| Neutral/base surfaces | `#F2F2F2`, `#FFFFFF` |
| Typography | Helvetica Neue, Suisse International, Neue Montreal, Arial, sans-serif |
