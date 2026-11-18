# Operations runbook

Use this runbook to configure, observe, and troubleshoot the application without exposing credentials or prompt content.

For the planned `DATALAB.SPAIN` container deployment, use the
[document lifecycle guide](document-lifecycle.md) to add, categorize and update
documents, and the [policy guide](document-access-policies.md) for role isolation.
The [container integration guide](snowflake-container.md) covers `snowflake_app.py`,
caller identity, named-agent routing and the pending native acceptance checks.
The checklist below describes the existing local/sample runtime, not that migration.

> The bootstrap now targets the `SOFIA` database, roles, and warehouse. It does not rename or remove objects created with earlier identifiers; existing deployments require an explicit migration plan before rollout.

## Deployment checklist

- [ ] Run `sql/bootstrap.sql` with reviewed object names and role assignments.
- [ ] Load approved document chunks into `SOFIA.KNOWLEDGE.DOCUMENT_CHUNKS`.
- [ ] Verify the Cortex Search Service is active and current.
- [ ] Store credentials in Streamlit secrets or the deployment secret manager.
- [ ] Set `RAG_MODELS` to models available in the target Snowflake account.
- [ ] Run the full local checks before deployment.

## Expected telemetry

`LoggingTelemetry` emits metadata for completed and failed requests:

- model name;
- number of retrieved sources;
- input and output token counts;
- end-to-end latency;
- question character count;
- exception type for failures.

It does **not** log credentials, question text, prompt content, source content, answer content, or Streamlit secrets. Preserve that rule when replacing the default adapter.

The passive UI metric plugin displays input tokens, output tokens, and latency for each answer. It does not send data or trigger reruns.

## Timeout behavior

The generator applies `STATEMENT_TIMEOUT_IN_SECONDS` to the Snowflake collection call. Cortex Search and `AI_COMPLETE` timeout-shaped provider exceptions become `RagTimeoutError`.

The UI catches both `RagTimeoutError` and native `TimeoutError`, marks `st.status` as failed, and renders a titled `st.error` alert. The Streamlit process and existing chat history remain available so the user can retry.

If timeouts recur:

1. Check warehouse state and queueing.
2. Check Cortex Search Service refresh status.
3. Reduce retrieved chunk count or source chunk size.
4. Review the selected model's account availability and latency.
5. Increase the application timeout only after measuring the bottleneck.

## Feedback

`st.feedback("thumbs")` is keyed by assistant message ID and preserved for the Streamlit session. The current implementation deliberately does not persist feedback to Snowflake. Add a dedicated feedback port before storing it so consent, retention, identity, and PII rules remain explicit.

## Guardrails

`BaselineGuardrail` rejects empty and oversized inputs/outputs. Replace or compose it at the application port for production policy checks. Do not place provider-specific guardrail logic in Streamlit.

Recommended production additions:

- prompt-injection classification before retrieval;
- policy-isolated Search corpora and audited grants for document access; optional filters alone are not an authorization boundary (see the policy guide);
- PII classification/redaction before generation and telemetry;
- output policy validation before rendering;
- trace correlation IDs that do not encode user content.

## Common failures

| Symptom | Check |
| --- | --- |
| Input is disabled | One or more required Snowflake settings is missing. Read the titled configuration alert. |
| Cortex Search returns no sources | Confirm data load, change tracking, service refresh, search column, and application role `USAGE`. |
| `AI_COMPLETE` is denied | Grant `SNOWFLAKE.CORTEX_USER` to the application role and verify model availability. |
| Query times out | Check the timeout procedure above and warehouse queueing. |
| Copy control does nothing | Clipboard access requires a secure browser context or localhost and an explicit user click. |
