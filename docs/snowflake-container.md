# Run the caller-bound Cortex Agent app in Snowsight

The local container integration is implemented in `snowflake_app.py`. It is **not a
validated deployment**: native caller-grant compatibility, agent/Search resources,
package installation and role isolation still require administrator-run checks.
Do not share the app with consumers until every acceptance check below passes.

## Entrypoints

| Environment | Entrypoint | Identity and orchestration |
| --- | --- | --- |
| Local development | `app.py` | Existing local credentials, Cortex Search + AI_COMPLETE; unchanged |
| Streamlit in Snowflake, container runtime | `snowflake_app.py` | Restricted caller's rights, named policy-specific Cortex Agent |

The container entrypoint does not read local passwords, mounted owner OAuth tokens,
`get_active_session()` or `_snowflake`. It creates
`st.connection("snowflake-callers-rights")` during script execution before rendering,
then obtains its Snowpark session. It never caches the session/service globally and
never falls back to owner execution. Connection failures disable chat.

## Resource contract

Use `DATALAB.SPAIN` and query warehouse `DEFAULT_WH_XS`. App owner:
`GG_APP_CC_REC_DATAWARE_DMO`. These proposed names are **not** resources created by
the application:

| Viewer default role | Agent | Isolated Search source view |
| --- | --- | --- |
| `GG_APP_SOYOU_DATALAB_USER` | `DATALAB.SPAIN.SOFIA_GENERAL_AGENT` | `DATALAB.SPAIN.SOFIA_GENERAL_CHUNKS` |
| `GG_APP_SOYOU_DATALAB_DPO` | `DATALAB.SPAIN.SOFIA_PRIVACY_AGENT` | `DATALAB.SPAIN.SOFIA_PRIVACY_CHUNKS` |
| `GG_APP_SP_DATALAB_CREDIT_AFTERSALES` | `DATALAB.SPAIN.SOFIA_CREDIT_AFTERSALES_AGENT` | `DATALAB.SPAIN.SOFIA_CREDIT_AFTERSALES_CHUNKS` |

1. Prepare the [classification and secure views](document-access-policies.md) and
   the approved [initial GENERAL assignment](document-lifecycle.md). Neither has
   been executed by this implementation.
2. Create a separate Search service over **each** policy view; configure each
   named agent with only its corresponding Search service. Reuse the approved
   ingestion/embedding configuration; this repository does not establish it.
3. Configure the model and grounding instructions on each agent, not in the app.
   Use the [prepared Sof~IA agent instructions](sofia-agent-instructions.md) for the
   planning/response fields and their pending native acceptance cases.
   Configure inaccessible-tool handling to reject incomplete tool access. The app
   also withholds any response containing warnings, incomplete status or errors.
4. Audit ordinary privileges and caller grants with an administrator. Viewers need
   access to Cortex Agents and the particular agent/tool resources they may use;
   the app owner needs the corresponding caller allowances. Ordinary grants alone
   are not caller grants. `AGENT_STUDIO_USER` is the supplied Cortex role name,
   not an assumed built-in privilege or a role this app activates.

The app disables secondary roles and matches only the exact default primary role
returned by Snowflake. A different role, including the app owner role, is denied.
There is no role picker and no implicit GENERAL inheritance. Account role inheritance
and existing broader grants must still be audited: application routing is not a
replacement for Snowflake authorization or corpus isolation.

## Snowsight upload preparation

Select a **container runtime**, not a warehouse runtime. Upload `snowflake_app.py`,
`src/rag_chat/`, `static/`, `.streamlit/config.toml` and the project packaging files.
The `rag_chat` package must be installed/importable from `src` in the container;
uploading the entrypoint alone is insufficient. Use the dependencies declared in
`pyproject.toml`; validate the container's package-repository access and installed
versions first. This change does not install packages or create a compute pool.
Select `snowflake_app.py` as the main file. Do not copy local credential files.

The documented minimum for restricted caller's rights is Streamlit 1.53.1. This
project already requires a newer version; its actual UI/package compatibility must
be checked in the selected Snowflake runtime. Exact Snowsight packaging and native
grant statements remain T3 deployment work, not a proven upload recipe.

## Response and observability behavior

- The adapter calls parameterized `SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?)` with full
  text history, `stream: false`, no background run or automatic thread creation.
  Retry history does not repeat the same current user question.
- A 60-second statement timeout is requested without a timeout-dropping fallback.
  Native timeout enforcement remains an acceptance check. There is no automatic
  paid-call retry.
- The UI shows agent-managed model selection, not a model override. It reports
  only actual generation start/completion, never fictional retrieval/tool steps.
- Search citation indices, document IDs, titles and excerpts are retained from
  response annotations. No filename joins, fabricated source links or sequential
  relabeling are performed. Answer text is retained verbatim. Verify actual native
  inline citation formatting against these source labels before rollout.
- Token totals are shown only when the response reports complete numeric usage;
  missing usage remains unavailable, not zero. Agent aggregate usage is not a
  model context-window utilization measurement.
- Identity, role or agent changes (or identity failure) clear the visible history
  and its sources before rendering. Reclassification/revocation still requires
  blocking access, refreshing/rebuilding indexes and clearing sessions as described
  in the lifecycle guide; it is not solved by a UI reset.
- Native Cortex Agent monitoring is the source for internal tool/model traces.
  The existing local TruLens wrapper is not attached to the caller session: this
  implementation does not claim native internal spans or a validated evaluation
  path. Evaluation and monitoring setup remain T3.

## Required native acceptance evidence

An administrator must run these checks in the actual Snowsight app; local fakes
and AppTest are insufficient:

- Verify CURRENT_USER/CURRENT_ROLE through the caller connection for each viewer,
  including a Snowsight-selected role different from their default role.
- Prove DATA_AGENT_RUN works through that same restricted caller session, with
  only the intended caller grants. If unsupported, stop: do not use owner REST.
- For each of the three roles, prove own-policy retrieval succeeds and other-policy
  agent/Search access fails. Also test an unauthorized default role and inspect
  inherited/public grants. Empty PRIVACY/CREDIT_AFTERSALES must not reveal GENERAL.
- Confirm history/retry and actual citation markers map to the native annotations;
  verify absent usage, tool warnings, timeout behavior and new-viewer isolation.
- Validate installed packages/assets, native monitoring, Search refresh and the
  revocation sequence before granting consumer app access.

## Official references

- [Restricted caller's rights in Streamlit](https://docs.snowflake.com/en/developer-guide/streamlit/features/restricted-callers-rights)
- [Streamlit SnowflakeConnection](https://docs.streamlit.io/develop/api-reference/connections/st.connections.snowflakeconnection)
- [DATA_AGENT_RUN](https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex)
- [Agent request/response schemas](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)
- [GRANT CALLER](https://docs.snowflake.com/en/sql-reference/sql/grant-caller)
