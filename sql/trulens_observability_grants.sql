-- Review and replace every example role or object name before execution.
-- This file is documentation only; the application never executes these grants.

-- Phase 1: before External Agent registration.
-- Grant the provisioner only the authority needed for controlled registration.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER
    TO ROLE SOFIA_RAG_OBSERVABILITY_PROVISIONER;
GRANT CREATE EXTERNAL AGENT ON SCHEMA DATALAB.TEST
    TO ROLE SOFIA_RAG_OBSERVABILITY_PROVISIONER;

-- Stop here. Run the first controlled TruApp initialization with the provisioner role.

-- Phase 2: after External Agent registration.
-- Runtime access uses the governed object but cannot create or own it.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE SOFIA_RAG_APP;
GRANT USAGE ON DATABASE DATALAB TO ROLE SOFIA_RAG_APP;
GRANT USAGE ON SCHEMA DATALAB.TEST TO ROLE SOFIA_RAG_APP;
GRANT USAGE ON EXTERNAL AGENT DATALAB.TEST.SOFIA_RAG
    TO ROLE SOFIA_RAG_APP;

REVOKE CREATE EXTERNAL AGENT ON SCHEMA DATALAB.TEST
    FROM ROLE SOFIA_RAG_OBSERVABILITY_PROVISIONER;

-- Phase 3: after the named evaluation table exists.
-- Evaluator access can read approved test data and run paid evaluation explicitly.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE SOFIA_RAG_EVALUATOR;
GRANT USAGE ON DATABASE DATALAB TO ROLE SOFIA_RAG_EVALUATOR;
GRANT USAGE ON SCHEMA DATALAB.TEST TO ROLE SOFIA_RAG_EVALUATOR;
GRANT USAGE ON EXTERNAL AGENT DATALAB.TEST.SOFIA_RAG
    TO ROLE SOFIA_RAG_EVALUATOR;
GRANT SELECT ON TABLE DATALAB.TEST.SOFIA_EVALUATION_CASES
    TO ROLE SOFIA_RAG_EVALUATOR;

-- Batch runs create Snowflake tasks; server-side metrics invoke paid AI functions.
GRANT CREATE TASK ON SCHEMA DATALAB.TEST
    TO ROLE SOFIA_RAG_EVALUATOR;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE SOFIA_RAG_EVALUATOR;
GRANT USE AI FUNCTIONS ON ACCOUNT TO ROLE SOFIA_RAG_EVALUATOR;

-- Intentionally omitted from the baseline because it reveals prompt, context, and response
-- content. Grant only after separate privacy approval:
-- GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE ON ACCOUNT
--     TO ROLE SOFIA_RAG_UNREDACTED_READER;

-- Rollback evaluator execution authority without deleting recorded evidence.
-- REVOKE USE AI FUNCTIONS ON ACCOUNT FROM ROLE SOFIA_RAG_EVALUATOR;
-- REVOKE EXECUTE TASK ON ACCOUNT FROM ROLE SOFIA_RAG_EVALUATOR;
-- REVOKE CREATE TASK ON SCHEMA DATALAB.TEST
--     FROM ROLE SOFIA_RAG_EVALUATOR;
