# Sof~IA Snowflake Cortex RAG

A grounded knowledge assistant built with Clean Architecture, Snowflake Cortex Search, Snowflake `AI_COMPLETE`, and Streamlit. The UI keeps retrieval sources, execution status, feedback, token usage, and latency visible without coupling presentation code to Snowflake.

## Quick path

1. Create the Snowflake objects and roles with [`sql/bootstrap.sql`](sql/bootstrap.sql).
2. Copy `config/snowflake-settings.example.toml` to `.streamlit/secrets.toml` and replace every placeholder.
3. Install and run the app:

```bash
uv sync --extra dev
uv run streamlit run app.py
```

Open the local URL shown by Streamlit. The input remains disabled until every required Snowflake setting is present.

Use **Settings → Theme** in the Streamlit toolbar to switch between the branded Light and Dark appearances.

> Never commit `.streamlit/secrets.toml` or `.env`. Both are ignored by Git.

## What the app does

1. Validates the question through an injected guardrail.
2. Retrieves trusted chunks from a Cortex Search Service.
3. Builds the standardized domain prompt with conversation history and numbered sources.
4. Calls `AI_COMPLETE(..., show_details => TRUE)` to receive the answer and token usage.
5. Validates the response and records metadata-only telemetry.
6. Renders citations, copy/retry controls, `st.feedback`, input/output tokens, and latency.

Timeouts are translated to a user-facing `st.error` alert; they do not terminate the Streamlit session.

## Clean Architecture

Dependencies point inward. The domain and application layers import neither Streamlit nor Snowflake.

| Layer | Responsibility | Main paths |
| --- | --- | --- |
| `domain` | Entities, errors, orchestration steps, and the central system prompt | `src/rag_chat/domain/` |
| `application` | RAG use case and provider-neutral ports for retrieval, generation, guardrails, and telemetry | `src/rag_chat/application/` |
| `infrastructure` | Snowflake settings, Snowpark session, Cortex Search, and `AI_COMPLETE` adapters | `src/rag_chat/infrastructure/` |
| `ui` | Streamlit state, semantic markup, chat controls, sources, and error presentation | `src/rag_chat/ui/` |
| Composition root | Concrete dependency wiring and resource caching | `app.py`, `src/rag_chat/composition.py` |

The system prompt lives in `src/rag_chat/domain/prompts.py`. Change it as a business rule, not inside the UI or provider adapter.

See [`docs/architecture.md`](docs/architecture.md) for the request flow and extension points.

## Configuration

Streamlit secrets take precedence over environment variables. The complete secret shape is in [`config/snowflake-settings.example.toml`](config/snowflake-settings.example.toml).

For environment-based configuration, copy `config/environment-variables.example.txt` to a local `.env`, replace placeholders, and export it in your shell before starting Streamlit. The application intentionally does not load `.env` files automatically.

```bash
set -a
source .env
set +a
uv run streamlit run app.py
```

To override the account-specific model selector:

```bash
export RAG_MODELS="llama3.3-70b,mistral-large2"
```

Model availability varies by Snowflake region and account. Keep only models enabled for the deployment.

To show context utilization near the chat input, configure only context limits you have
verified for the exact deployed model versions:

```bash
export RAG_MODEL_CONTEXT_LIMITS="llama3.3-70b=replace-with-verified-limit"
```

Use comma-separated `model=limit` entries for multiple models. Unknown limits remain labeled
as unavailable; the application does not infer them.

## Verification

```bash
uv run pytest tests -q
uv run ruff check app.py src tests
uv run mypy app.py src
```

The test suite uses fakes and Streamlit `AppTest`; it performs no live Snowflake operation.

## Operations and security

- Read [`docs/operations.md`](docs/operations.md) before deployment.
- The application role receives only warehouse/database/schema usage, Cortex Search service usage, and `SNOWFLAKE.CORTEX_USER`.
- Parameterized Snowpark SQL binds the model and prompt passed to `AI_COMPLETE`.
- Logs contain model, source count, token counts, latency, and character count—not credentials, question text, prompt content, or answer content.
- The clipboard control embeds answer text as base64 data and executes only static, local JavaScript on an explicit click.

## Documentation evidence

The implementation follows current official guidance:

- [Streamlit chat interfaces](https://docs.streamlit.io/develop/api-reference/chat)
- [Streamlit `st.status`](https://docs.streamlit.io/develop/api-reference/status/st.status)
- [Streamlit `st.feedback`](https://docs.streamlit.io/develop/api-reference/widgets/st.feedback)
- [Snowflake Cortex Search Python API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service)
- [Snowflake `AI_COMPLETE`](https://docs.snowflake.com/en/sql-reference/functions/ai_complete-single-string)
