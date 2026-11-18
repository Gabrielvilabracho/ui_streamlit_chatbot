# Prepare role-isolated document access

**Status: local security foundation, not a deployed policy or completed agent migration.**
The existing app and its Search service are unchanged and must not be treated as
role-isolated. No account resources or permissions have been inspected or changed.

## Approved distribution

| Exact role | Policy label | Allowed documents | Source view in `DATALAB.SPAIN` |
| --- | --- | --- | --- |
| `GG_APP_SOYOU_DATALAB_USER` | `GENERAL` | Approved general Datalab documentation | `SOFIA_GENERAL_CHUNKS` |
| `GG_APP_SOYOU_DATALAB_DPO` | `PRIVACY` | Classified privacy, data-protection and compliance documentation | `SOFIA_PRIVACY_CHUNKS` |
| `GG_APP_SP_DATALAB_CREDIT_AFTERSALES` | `CREDIT_AFTERSALES` | Classified credit and aftersales documentation | `SOFIA_CREDIT_AFTERSALES_CHUNKS` |

There is no automatic cross-policy inheritance, including access to `GENERAL`.
Each document needs exactly one approved classification. Missing, unknown,
duplicate or conflicting assignments expose no chunks from that document.
Matching is exact and case-sensitive. The policy-setup script contains no assignments.

The user has now approved **GENERAL for the current parsed documents**. The
separate [initial assignment script](../sql/classify_existing_documents_general.sql)
prepares this explicit action without overwriting restrictive/ambiguous existing
classifications. It has not been run in Snowflake and is not a future-upload
default. Follow the [document lifecycle guide](document-lifecycle.md) for initial
assignment, new uploads, categorization, content updates and revocation.

## Before running any SQL in Snowsight

An authorized administrator must confirm all of the following:

1. The proposed `SOFIA_` object names are unused. The setup deliberately stops on
   collisions instead of replacing objects or trusting an existing definition.
   Snowflake DDL is not an atomic transaction: inspect partial creation before retrying.
2. The selected governance owner has database/schema usage, `CREATE TABLE`,
   `CREATE VIEW`, and `SELECT` on `RAG_DOCUMENTS` and `RAG_CHUNKS`. The owner
   remains trusted and must not be granted to consumers or the app's viewer role.
3. Existing/future grants, `PUBLIC`, database roles, ownership, role inheritance
   and secondary roles do not give consumers access to other policies, raw
   source tables, classification writes or an unrestricted Search service.
   These scripts do not remove or override existing privileges.
4. For optional SQL-view validation, each consumer already has approved database,
   schema and query-warehouse usage. A grantor with the required grant authority
   must run the separate view-grants script. Managed-access schemas can require
   the schema owner or a role with `MANAGE GRANTS`.

Do not run the older `sql/bootstrap.sql` for this migration: it provisions a
different sample database and shared-corpus runtime.

## Prepare the policy sources

After administrator review, run [`document_access_policies.sql`](../sql/document_access_policies.sql).
It creates an empty classification table and three policy-specific secure views.
It does not modify source records, create roles, grant permissions or create indexes.
With the empty classification table, all three views return zero documents.

Identify candidate documents without retrieving their contents:

```sql
SELECT DOC_ID, FILE_NAME
FROM DATALAB.SPAIN.RAG_DOCUMENTS
ORDER BY DOC_ID;
```

A document owner must approve the classification from its actual contents and
governance requirements, not infer it from the filename. Record the approved
numeric `RAG_DOCUMENTS.DOC_ID` and one exact policy label in
`DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS`. Do not copy UUIDs from
`RAG_DOCUEMNT_REGISTRY`, join that registry by filename, or assign every document
to `GENERAL` as a fallback. Classification writes are a separate governed action;
none are performed by the supplied setup.

After classifications and grants have been reviewed, the optional
[`document_access_grants.sql`](../sql/document_access_grants.sql) grants `SELECT`
only on each consumer's matching view. It is for SQL-view validation; it is not
the permission set for a deployed agent. No consumer gets the classification table.

## Requirements before enabling Cortex Agent

- Create a separate Search corpus from each policy view. Never index all policies
  and rely on `CURRENT_ROLE()`, a UI selector, a prompt or an optional Search filter:
  Cortex Search uses owner's rights. Separate agents over the same unrestricted
  Search service do not establish isolation.
- Grant each execution identity access only to its permitted service/agent.
  Review users with multiple roles: Snowflake grants are additive. The approved
  matrix does not revoke privileges a user already has through another role.
- Prove per-viewer invocation in Streamlit container runtime before sharing the
  app. Restricted-caller SQL connections and `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`
  are documented separately; their complete combined grant/runtime behavior
  remains unverified here. A shared owner OAuth token is not viewer identity.
- Test positive access for every role and negative access to both other policies,
  the source/classification tables and any shared Search service. Test real
  effective roles, not just a label displayed in Streamlit. Fail closed if the
  identity or required tool access is unavailable; do not silently fall back to
  the existing owner-connected RAG implementation.
- For policy revocation or reclassification, block access to affected Search
  services/agents and terminate affected app sessions first. Refresh/rebuild the
  affected indexes, verify the removed content is absent, and clear cached
  retrievals/conversation history before restoring access. View changes do not
  synchronously remove content from an existing Search index.

## Verification boundary

`tests/unit/test_document_access_sql.py` executes the actual portable view SELECTs
against synthetic SQLite records, checks all three classifications and denied
cases, and checks the exact explicit view grants. It does **not** validate
Snowflake DDL, effective grants, secure-view semantics, Search indexing or agent
execution. Those require administrator-run Snowflake verification before rollout.
No paid agent calls are necessary for the local tests.

Sources: [view privileges](https://docs.snowflake.com/en/user-guide/security-access-control-privileges#view-privileges),
[secure views](https://docs.snowflake.com/en/user-guide/views-secure),
[Search access control](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service#label-cortex-search-query-syntax-access-controls),
[Streamlit restricted caller rights](https://docs.snowflake.com/en/developer-guide/streamlit/features/restricted-callers-rights),
[DATA_AGENT_RUN](https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex).
