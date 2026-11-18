-- Local deployment preparation only. Read docs/document-access-policies.md first.
-- Run as the approved governance owner, never as a consumer/app execution role.
-- Audit existing/future grants and role inheritance BEFORE creating these objects.
-- Deliberately no REPLACE/IF NOT EXISTS: a name collision requires inspection.
-- No document is automatically classified and no source table is modified.

CREATE TABLE DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS (
  DOC_ID NUMBER(38,0) NOT NULL,
  ACCESS_POLICY VARCHAR NOT NULL
);

-- A document must have exactly one classification row. Snowflake standard-table
-- uniqueness constraints are not an authorization boundary. Duplicate/conflicting
-- rows, unknown labels and absent assignments therefore fail closed in the views.
CREATE SECURE VIEW DATALAB.SPAIN.SOFIA_GENERAL_CHUNKS AS
WITH classified AS (
  SELECT DOC_ID
  FROM DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS
  GROUP BY DOC_ID
  HAVING COUNT(*) = 1 AND MIN(ACCESS_POLICY) = 'GENERAL'
)
SELECT
  c.CHUNK_ID,
  c.DOC_ID,
  c.CHUNK_TEXT,
  d.FILE_NAME AS TITLE,
  'GENERAL' AS ACCESS_POLICY
FROM DATALAB.SPAIN.RAG_CHUNKS c
INNER JOIN DATALAB.SPAIN.RAG_DOCUMENTS d ON d.DOC_ID = c.DOC_ID
INNER JOIN classified p ON p.DOC_ID = c.DOC_ID;

CREATE SECURE VIEW DATALAB.SPAIN.SOFIA_PRIVACY_CHUNKS AS
WITH classified AS (
  SELECT DOC_ID
  FROM DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS
  GROUP BY DOC_ID
  HAVING COUNT(*) = 1 AND MIN(ACCESS_POLICY) = 'PRIVACY'
)
SELECT
  c.CHUNK_ID,
  c.DOC_ID,
  c.CHUNK_TEXT,
  d.FILE_NAME AS TITLE,
  'PRIVACY' AS ACCESS_POLICY
FROM DATALAB.SPAIN.RAG_CHUNKS c
INNER JOIN DATALAB.SPAIN.RAG_DOCUMENTS d ON d.DOC_ID = c.DOC_ID
INNER JOIN classified p ON p.DOC_ID = c.DOC_ID;

CREATE SECURE VIEW DATALAB.SPAIN.SOFIA_CREDIT_AFTERSALES_CHUNKS AS
WITH classified AS (
  SELECT DOC_ID
  FROM DATALAB.SPAIN.SOFIA_DOCUMENT_CLASSIFICATIONS
  GROUP BY DOC_ID
  HAVING COUNT(*) = 1 AND MIN(ACCESS_POLICY) = 'CREDIT_AFTERSALES'
)
SELECT
  c.CHUNK_ID,
  c.DOC_ID,
  c.CHUNK_TEXT,
  d.FILE_NAME AS TITLE,
  'CREDIT_AFTERSALES' AS ACCESS_POLICY
FROM DATALAB.SPAIN.RAG_CHUNKS c
INNER JOIN DATALAB.SPAIN.RAG_DOCUMENTS d ON d.DOC_ID = c.DOC_ID
INNER JOIN classified p ON p.DOC_ID = c.DOC_ID;
