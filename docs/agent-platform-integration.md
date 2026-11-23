# Consume the shared agent platform

`ui_streamlit_chatbot` is a consumer application. It invokes approved Cortex
Agent aliases from `DATALAB.TEST`, but it does not build or deploy agent
artifacts, own prompt layers, or define evaluation datasets.

The shared source of truth lives in the sibling local repository
`../agent-platform-config` during development. That repository owns:

- agent manifests and policy-specific Search-service references;
- reusable prompt layers and skills;
- project metadata, evaluation contracts and promotion thresholds; and
- deterministic deployment artifacts for manual Snowsight deployment.

## Consumer contract

The application uses `DATALAB.TEST` and query warehouse `DATALAB_TEST_WH`.
`DATALAB_TEST_ADMIN` maps only to the GENERAL agent. The application accepts no
prompt, agent, role or evaluation configuration from its own source tree.

Before an agent version is promoted, validate and deploy it from the platform
repository, then prove caller rights, policy isolation and runtime behavior in
Snowsight. The application remains responsible for UI behavior, caller identity
verification and safe response rendering.
