# Agent platform configuration
Objective: prepare a version-controlled Snowflake configuration package for the existing Cortex Agent application.
Delivery: local feature branch; no Snowflake authentication, account execution, upload, push, or deployment. Runner: `uv run pytest tests -q`.

## Specs

- S1 — User: «lo que quiero que preparaemos el codigo para dejarlo listo para yo implementarlo al subirlo a la cuenta.»
- S2 — User: «confirmo base de datos DATALAB schema TEST. warehouse DATALAB_TEST_WH si existe».
- S3 — User: «DATALAB_TEST_ADMIN».
- S4 — User: «dejalo todo en - Database: DATALAB\n- Schema: TEST».
- S5 — User: «si. y quiero que lo guardemos fuera de la carpeta de /projects/ui_streamlit_chatbot».

## Tasks

- T1 [S1-S4] — inline; status: completed; commit: `2b45bfd`; route: inline because agent manifests, prompt composition, evaluation references and their validation form one dependent behavior.
- T2 [S1-S4] — inline; status: completed; commit: `2b45bfd`; retarget evaluation SQL, configuration examples, grants and documentation to `DATALAB.TEST` without account mutations.
- T3 [S1-S4] — inline; status: completed; commit: `2b45bfd`; deterministic build, focused/full regressions, static checks and independent security verification passed.
- T4 [S1-S5] — inline; status: completed; app commit: `807a302`; platform commit: `36216e9`; extract the shared platform into a sibling local Git repository and leave this application as a documented consumer. Route: inline because repository extraction and consumer contract must remain coherent.

## Log

- L1 — User request verbatim: «lo que quiero que preparaemos el codigo para dejarlo listo para yo implementarlo al subirlo a la cuenta. y los permisos del rol son de SYSADMIN , confirmo base de datos DATALAB schema TEST. warehouse DATALAB_TEST_WH si existe».
- L2 — User confirmation verbatim: «DATALAB_TEST_ADMIN».
- L3 — Existing local adapter already targets `DATALAB.TEST`, uses caller-bound access, and now maps exactly `DATALAB_TEST_ADMIN` to the isolated GENERAL agent. Native RBAC and runtime compatibility remain deployment evidence, not local-test claims.
- L4 — User decision verbatim: «dejalo todo en - Database: DATALAB\n- Schema: TEST». Evaluation datasets, results and platform metadata belong in `DATALAB.TEST`; no separate `AGENT_PLATFORM` database is part of this deployment package.
- L5 — Added the local `agent_platform/` source-of-truth package: prompt layers, GENERAL manifest, project/evaluation metadata, and a standard-library TOML validator/builder. It generates a deterministic, deployment-neutral JSON artifact and a source-hash manifest; it neither authenticates nor contacts Snowflake.
- L6 — RED: package and namespace assertions failed before the implementation. GREEN: focused platform/project/agent tests, full suite, Ruff, mypy and diff checks passed. Independent verification required staging the package and removing a stale `AGENT_PLATFORM` mention from the AI-functions plan; the targeted recheck passed. Native Snowflake grants, agent creation and runtime behavior remain deployment acceptance work.
- L7 — User decision verbatim: «si. y quiero que lo guardemos fuera de la carpeta de /projects/ui_streamlit_chatbot». Extract the shared source into sibling local repository `agent-platform-config`; do not create, publish or configure a remote repository without separate authorization.
- L8 — Created `/Users/gabrielvilabracho/projects/agent-platform-config` as a local Git repository with no remote. Its tracked `main` commit `36216e9` owns the prompt, agent, project, evaluation and builder source. The application commit `807a302` removes that duplicated source and adds a consumer contract. Focused and full application checks passed; platform builder tests passed with the existing local Python environment. Independent verification confirmed the extraction and no remote/Snowflake operation.
