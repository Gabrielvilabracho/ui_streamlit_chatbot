-- Explicit initial rollout action, not a default for future documents.
-- Read docs/document-lifecycle.md and review effective grants before execution.
-- Prerequisite: sql/document_access_policies.sql has created the empty policy table.
-- Run as the approved governance owner, outside another transaction, with no
-- concurrent ingestion/classification writes. No account operation runs from the app.
-- Existing restrictive, invalid or duplicate classifications require manual review;
-- this script must not downgrade them to GENERAL or partially seed other documents.

EXECUTE IMMEDIATE $$
DECLARE
  conflict_count INTEGER;
  assignment_conflict EXCEPTION (
    -20001,
    'Existing classifications require review. No GENERAL assignments were applied.'
  );
BEGIN
  BEGIN TRANSACTION;

  SELECT COUNT(*)
  INTO :conflict_count
  FROM (
    SELECT p.DOC_ID
    FROM DATALAB.TEST.SOFIA_DOCUMENT_CLASSIFICATIONS p
    INNER JOIN (
      SELECT DISTINCT DOC_ID
      FROM DATALAB.TEST.RAG_DOCUMENTS
      WHERE DOC_ID IS NOT NULL
    ) d ON d.DOC_ID = p.DOC_ID
    GROUP BY p.DOC_ID
    HAVING COUNT(*) <> 1 OR MIN(p.ACCESS_POLICY) <> 'GENERAL'
  );

  IF (conflict_count > 0) THEN
    RAISE assignment_conflict;
  END IF;

  INSERT INTO DATALAB.TEST.SOFIA_DOCUMENT_CLASSIFICATIONS (DOC_ID, ACCESS_POLICY)
  SELECT DISTINCT d.DOC_ID, 'GENERAL'
  FROM DATALAB.TEST.RAG_DOCUMENTS d
  WHERE d.DOC_ID IS NOT NULL
    AND NOT EXISTS (
      SELECT 1
      FROM DATALAB.TEST.SOFIA_DOCUMENT_CLASSIFICATIONS p
      WHERE p.DOC_ID = d.DOC_ID
    );

  COMMIT;
EXCEPTION
  WHEN OTHER THEN
    ROLLBACK;
    RAISE;
END;
$$;
