# Add, categorize and update documents

Use this guide for the planned `DATALAB.SPAIN` deployment. **The app migration is
not deployed, and this repository does not implement the existing PDF ingestion
pipeline.** Uploading a file does not parse, categorize, index or publish it.

## Current decision: existing documents are GENERAL

The approved initial category is `GENERAL` for documents currently in
`DATALAB.SPAIN.RAG_DOCUMENTS`. This applies to parsed documents, not every file
registered in the stage, and is not automatic approval of future uploads.
Under the approved role matrix, `GENERAL` is available to
`GG_APP_SOYOU_DATALAB_USER`; it is not inherited by the DPO or credit/aftersales
roles. Their policy sources remain empty until documents are explicitly assigned
to them. Existing restrictive classifications are never silently downgraded.

### Initial rollout in Snowsight

An authorized administrator performs these steps; the app does not run them:

1. Complete the owner/grant/name-collision review in the
   [policy guide](document-access-policies.md#before-running-any-sql-in-snowsight).
2. Run [`document_access_policies.sql`](../sql/document_access_policies.sql) once
   to create the classification table and three secure views. Do not rerun this
   setup on existing objects or use the old `SOFIA.KNOWLEDGE` sample bootstrap.
3. Review the current parsed-document inventory:

   ```sql
   SELECT DOC_ID, FILE_NAME
   FROM DATALAB.SPAIN.RAG_DOCUMENTS
   ORDER BY DOC_ID;
   ```

4. With ingestion and classification writers paused, run
   [`classify_existing_documents_general.sql`](../sql/classify_existing_documents_general.sql)
   in a standalone worksheet execution, outside any existing transaction. It
   assigns `GENERAL` to currently unclassified numeric document IDs. Repeating
   it with the same documents makes no duplicate assignments. A restrictive,
   invalid or duplicate existing assignment aborts the entire operation; inspect
   it instead of deleting it to make the script pass.
5. Verify classifications and visible chunks using the checks below. The separate
   view-grants script is optional for administrator-approved SQL validation.
   Agent/Search publication remains gated on the policy guide's isolation tests.

Do not schedule or automatically rerun the initial GENERAL script after uploads:
its current-document selection would also include new, unclassified documents.
The script changes classifications only, not documents, chunks, roles or indexes.
Its Snowflake scripting/transaction behavior still requires account verification;
local tests exercise the query bodies, not the Snowflake runtime.

## The document lifecycle

| Step | Location | Completion evidence |
| --- | --- | --- |
| Upload | `DATALAB.SPAIN.gabriel_test_pdf_docs_stage` | Reviewed file exists at its exact stage path |
| Register | `RAG_DOCUEMNT_REGISTRY` | Approved loader recorded the file; this alone does not mean parsed |
| Parse | `RAG_DOCUMENTS` | Numeric `DOC_ID`, expected file/version and usable `RAW_TEXT` |
| Chunk/embed | `RAG_CHUNKS` | Complete chunks refer to that same numeric `DOC_ID` |
| Categorize | `SOFIA_DOCUMENT_CLASSIFICATIONS` | Exactly one approved policy row for that numeric `DOC_ID` |
| Publish | Policy-specific Search service and agent | Refreshed, isolated corpus; positive and negative access checks pass |

The registry uses VARCHAR IDs; the parsed/chunk tables use numeric IDs. Never
cast registry UUIDs to numeric IDs, invent `MAX(DOC_ID) + 1`, or join by filename.
The existing loader must supply the authoritative mapping and ID allocation.
Earlier reported counts were 13 registry entries versus 3 parsed documents;
registration must not be mistaken for completed processing.

## Add a new document

1. **Approve the content.** The document owner checks source, version, privacy,
   allowed audience and retention requirements. Choose a category from the table
   below; a filename is not evidence of sensitivity. Do not upload credentials.
2. **Upload through Snowsight.** Open the database/schema, select the configured
   stage and use its file-upload action. Use a reviewed, versioned relative path;
   do not overwrite a published file in place before the update procedure below.
3. **Run the approved ingestion pipeline.** Its operator registers the stage path,
   parses the file, and produces chunks/embeddings in the tables above. That
   task/procedure is not included or identified in this repository: obtain its
   actual name and invocation from the pipeline owner before this step. Do not
   substitute SQL targeting the unverified staging tables or guess an embedding
   model from the vector's dimension. Stop here if the pipeline is unavailable.
4. **Verify processing.** Inspect metadata/counts for the loader-assigned numeric
   `DOC_ID`; validate extraction and chunk quality in the governed environment.
   Never paste raw text, personal data or embeddings into logs or support chat.
5. **Assign one approved category.** Use the classification procedure below. Until
   then the policy views deny the document. Keep source tables, classification
   writes and ingestion privileges out of consumer roles.
6. **Publish only to the matching policy corpus.** Refresh/index that policy's
   Search source, verify the intended version is present, and test the authorized
   role plus both unauthorized roles before making it available in the app.
   Stage upload or a committed classification alone is not publication proof.

## Categorize a new document

| Exact category | Audience | Intended content |
| --- | --- | --- |
| `GENERAL` | `GG_APP_SOYOU_DATALAB_USER` | Approved general Datalab documentation |
| `PRIVACY` | `GG_APP_SOYOU_DATALAB_DPO` | Privacy, data protection and compliance |
| `CREDIT_AFTERSALES` | `GG_APP_SP_DATALAB_CREDIT_AFTERSALES` | Credit and aftersales |

These are separate audiences, not increasing access levels. A mixed-audience
document requires governance review or separate redacted documents; do not add
multiple classification rows. Missing/unknown labels and duplicate/conflicting
assignments are denied by the policy views.

After approval, a governance writer can use this **template for a new assignment**.
Replace `<numeric_DOC_ID>` with the ID returned by the loader; choose one exact
policy label. Run with a single classification writer, after confirming no
assignment exists. Record the approval in the organization's governed audit
process; do not treat query history as a complete approval record.

```sql
SET document_id = <numeric_DOC_ID>;
SET access_policy = 'GENERAL'; -- Or PRIVACY / CREDIT_AFTERSALES after approval.

INSERT INTO DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS (DOC_ID, ACCESS_POLICY)
SELECT DISTINCT d.DOC_ID, $access_policy
FROM DATALAB.SPAIN.RAG_DOCUMENTS d
WHERE d.DOC_ID = $document_id
  AND $access_policy IN ('GENERAL', 'PRIVACY', 'CREDIT_AFTERSALES')
  AND NOT EXISTS (
    SELECT 1 FROM DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS p
    WHERE p.DOC_ID = d.DOC_ID
  );
```

Expect **one inserted row**. Zero means the ID/category is invalid, the document
is not parsed or an assignment already exists: stop and inspect, not success.
This template intentionally cannot overwrite an existing category.

## Update document content

1. Identify the exact existing numeric `DOC_ID`, current category, stage path,
   version and affected services/agents. Preserve the current version and its
   classification in an approved backup/audit location before modifying records.
2. Block access to the affected Search service/agent and end affected app sessions.
   This is mandatory for sensitive corrections, deletions and audience changes;
   the conservative default is to keep access blocked throughout any replacement.
3. Upload a new version and have the approved loader validate parsing/chunking
   before publication. Preserve `DOC_ID` if the loader supports version replacement;
   otherwise obtain the new ID and explicitly migrate its reviewed classification.
4. The loader must replace the complete old chunk set atomically, including changed
   embeddings/metadata, rather than append new chunks beside stale ones. If its
   replacement/rollback behavior is unknown, stop before changing source records.
   Keep the previous category unless a separate audience change is approved.
5. Refresh/rebuild every affected policy index. Verify old chunks are absent and
   the new version is present; clear affected retrieval caches and conversation
   history, which may still contain the old text or citations.
6. Repeat positive/negative access and answer-quality checks, then restore access.
   If verification fails, keep access blocked and restore the approved source and
   classification snapshot; rebuild/verify indexes again before reopening.

## Change category or remove a document

Treat recategorization as an authorization change, not a metadata-only edit:

1. Approve the destination category, or removal, and retain the previous mapping
   in the governed audit record. Identify both source and destination indexes.
2. Block affected service/agent access and terminate affected sessions **before**
   changing the classification or deleting/replacing source records.
3. With a single governance writer, replace the old assignment with exactly one
   approved row in a transaction; on error roll back. For removal, revoke the
   classification and follow the approved retention/deletion workflow. No consumer
   or app session may perform these writes. The initial GENERAL script is not a
   recategorization tool and must not be used to bypass an existing assignment.
4. Refresh/rebuild affected indexes, verify no removed content remains, and clear
   cached retrievals and chat history before testing and restoring access.

Removing a category row denies new SQL-view reads, but does **not** immediately
erase indexed content, existing answers, traces or evaluation datasets. Apply the
organization's retention/deletion policy to those copies too. Do not restore
access merely because a view count changed or a refresh interval elapsed.

## Verify without exposing document text

```sql
SELECT d.DOC_ID, d.FILE_NAME, p.ACCESS_POLICY
FROM DATALAB.SPAIN.RAG_DOCUMENTS d
LEFT JOIN DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS p ON p.DOC_ID = d.DOC_ID
ORDER BY d.DOC_ID;

SELECT DOC_ID, COUNT(*) AS CHUNK_COUNT
FROM DATALAB.SPAIN.RAG_CHUNKS
GROUP BY DOC_ID ORDER BY DOC_ID;

SELECT ACCESS_POLICY, COUNT(*) AS ASSIGNMENT_COUNT
FROM DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS
GROUP BY ACCESS_POLICY;
```

Before publication, require exactly one known classification per published ID,
nonempty complete chunks, the intended index version, and positive/negative role
tests. Effective grants, role inheritance, restricted-caller invocation and actual
Search resource names remain deployment checks, not local test results.

References: [stage uploads in Snowsight](https://docs.snowflake.com/en/user-guide/data-load-local-file-system-stage-ui),
[Snowflake scripting exceptions](https://docs.snowflake.com/en/developer-guide/snowflake-scripting/exceptions),
[transaction behavior](https://docs.snowflake.com/en/sql-reference/transactions),
[Search access control](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service#label-cortex-search-query-syntax-access-controls).
