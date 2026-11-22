# Sof~IA agent platform configuration

This directory is the editable, version-controlled source of truth for the
Sof~IA GENERAL Cortex Agent candidate. It prepares artifacts for a later,
manual Snowsight deployment; it never authenticates to Snowflake, uploads
files, executes SQL, or promotes an agent.

## Target environment

- Database and schema: `DATALAB.TEST`
- Query warehouse: `DATALAB_TEST_WH`
- Approved caller role: `DATALAB_TEST_ADMIN`
- Policy: `GENERAL`

## Layout

- `prompts/` — ordered behavioral prompt layers.
- `agents/` — one editable agent manifest per candidate.
- `projects/` — shared project ownership and environment metadata.
- `evaluations/` — dataset and threshold references for reproducible evaluation.
- `scripts/` — local validation and deterministic artifact generation.

## Local commands

```bash
python agent_platform/scripts/validate_platform.py
python agent_platform/scripts/build_agent_specs.py --output /tmp/sofia-agent-artifacts
```

The generated JSON artifact is deployment-neutral. Before deployment, translate
it to the Snowflake-supported agent definition for the target account and run
the administrator acceptance checks in `docs/snowflake-container.md`.
