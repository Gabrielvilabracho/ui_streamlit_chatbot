# Agent platform configuration
Objective: prepare a version-controlled Snowflake configuration package for the existing Cortex Agent application.
Delivery: local feature branch; no Snowflake authentication, account execution, upload, push, or deployment. Runner: `uv run pytest tests -q`.

## Specs

- S1 — User: «lo que quiero que preparaemos el codigo para dejarlo listo para yo implementarlo al subirlo a la cuenta.»
- S2 — User: «confirmo base de datos DATALAB schema TEST. warehouse DATALAB_TEST_WH si existe».
- S3 — User: «DATALAB_TEST_ADMIN».
- S4 — User: «dejalo todo en - Database: DATALAB\n- Schema: TEST».

## Tasks

- T1 [S1-S4] — inline; status: in progress; route: inline because agent manifests, prompt composition, evaluation references and their validation form one dependent behavior.
- T2 [S1-S4] — inline; status: pending; prepare idempotent deployment templates and project documentation without account mutations.
- T3 [S1-S4] — inline; status: pending; validate generated artifacts, environment boundaries and regression coverage.

## Log

- L1 — User request verbatim: «lo que quiero que preparaemos el codigo para dejarlo listo para yo implementarlo al subirlo a la cuenta. y los permisos del rol son de SYSADMIN , confirmo base de datos DATALAB schema TEST. warehouse DATALAB_TEST_WH si existe».
- L2 — User confirmation verbatim: «DATALAB_TEST_ADMIN».
- L3 — Existing local adapter already targets `DATALAB.TEST`, uses caller-bound access, and now maps exactly `DATALAB_TEST_ADMIN` to the isolated GENERAL agent. Native RBAC and runtime compatibility remain deployment evidence, not local-test claims.
- L4 — User decision verbatim: «dejalo todo en - Database: DATALAB\n- Schema: TEST». Evaluation datasets, results and platform metadata belong in `DATALAB.TEST`; no separate `AGENT_PLATFORM` database is part of this deployment package.
