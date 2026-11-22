# Operate TruLens observability safely

TruLens recording is opt-in, and batch evaluation is a separate operator action. Enabling
recording can register a Snowflake External Agent; starting a run can create tasks and invoke
paid AI functions. Never enable either capability from an unreviewed developer environment.

## Quick path

1. Review prompts, retrieved chunks, and responses as potentially sensitive data.
2. Apply **Phase 1** of the least-privilege template in
   [`sql/trulens_observability_grants.sql`](../sql/trulens_observability_grants.sql).
3. Register `SOFIA_RAG` once in a controlled environment, then apply **Phase 2** to grant
   object usage and revoke the provisioner's `CREATE EXTERNAL AGENT` grant.
4. Apply [`sql/evaluation_foundation.sql`](../sql/evaluation_foundation.sql) in the approved
   account, populate its named evaluation table, apply **Phase 3** to the evaluator role, and
   configure a unique run name.
5. Start the run from an operator process, wait for invocation ingestion, then explicitly
   request the allow-listed server-side metrics.
6. Review traces and evaluation results in Snowsight under **AI & ML → Evaluations**.

The web application must remain functional when TruLens is disabled or unavailable.

## Responsibilities

| Role | Responsibility | Required privileges |
|---|---|---|
| Runtime | Export approved traces for the existing custom RAG app | `SNOWFLAKE.CORTEX_USER`, parent object access, External Agent `USAGE` |
| Provisioner | Perform the one-time External Agent registration | `SNOWFLAKE.CORTEX_USER`, `CREATE EXTERNAL AGENT` on the target schema |
| Evaluator | Invoke named-table runs and compute metrics | External Agent `USAGE`, `CREATE TASK`, `EXECUTE TASK`, `USE AI FUNCTIONS` |

Do not grant `READ UNREDACTED AI OBSERVABILITY EVENTS TABLE` in the baseline. Without that
account privilege, operators can inspect metadata such as token usage and latency while
sensitive tool inputs, outputs, and conversation text remain redacted. Grant it only to a
dedicated role after a separate privacy review.

## Configure a named evaluation run

Use a fully qualified dataset name and a run name that has never been used under the TruApp.
Environment variables and Streamlit secrets use the same field names shown in the example
configuration files. The named table must exist before applying Phase 3 of the grant template.

```bash
export TRULENS_EVAL_DATASET="DATALAB.TEST.SOFIA_EVALUATION_CASES"
export TRULENS_EVAL_RUN="release-2026-11-17"
export TRULENS_EVAL_JUDGE_MODEL="replace-with-enabled-cortex-model"
export TRULENS_EVAL_INPUT_COLUMN="QUESTION"
export TRULENS_EVAL_METRICS="groundedness,context_relevance,answer_relevance,coherence"
```

Add `correctness` only when the table contains reviewed reference answers:

```bash
export TRULENS_EVAL_GROUND_TRUTH_COLUMN="EXPECTED_ANSWER"
export TRULENS_EVAL_METRICS="groundedness,context_relevance,answer_relevance,coherence,correctness"
```

| Metric | Required evidence |
|---|---|
| `groundedness` | Generated answer and retrieved contexts |
| `context_relevance` | User question and retrieved contexts |
| `answer_relevance` | User question and generated answer |
| `coherence` | Generated answer |
| `correctness` | Generated answer and `RECORD_ROOT.GROUND_TRUTH_OUTPUT` |

## Start an evaluation explicitly

Run this only inside a controlled operator entry point that already owns the application's
existing `orchestrator` and `snowpark_session`. Reuse that session; do not introduce a second
credential path.

```python
from rag_chat.infrastructure.trulens.evaluation import (
    BatchEvaluationSettings,
    create_batch_run,
    execute_batch_run,
)
from rag_chat.infrastructure.trulens.instrumentation import create_trulens_runtime
from rag_chat.infrastructure.trulens.settings import ObservabilitySettings

evaluation = BatchEvaluationSettings.from_sources(secrets={}, environ=None)
runtime = create_trulens_runtime(
    delegate=orchestrator,
    snowpark_session=snowpark_session,
    settings=ObservabilitySettings(
        enabled=True,
        app_name="SOFIA_RAG",
        app_version="v1",
    ),
)
run = create_batch_run(tru_app=runtime.tru_app, settings=evaluation)
execute_batch_run(run=run, metrics=evaluation.metrics)
```

`execute_batch_run` waits for `INVOCATION_COMPLETED` or
`INVOCATION_PARTIALLY_COMPLETED` before starting metrics. It refuses to compute metrics after
failed, cancelled, unknown, or already-terminal runs. Metric computation is asynchronous;
confirm completion in Snowsight or through the TruLens run status API.

## Data-governance checklist

- [ ] The evaluation table contains only approved test questions and reference answers.
- [ ] Retrieved production documents are permitted to appear in observability traces.
- [ ] The evaluator role is separate from the application runtime role.
- [ ] The judge model is available in the deployment region and approved for the data class.
- [ ] The operator understands that model invocation, tasks, and metric computation can cost money.
- [ ] Unredacted event access remains ungranted unless separately approved.
- [ ] Credentials remain in Streamlit secrets or environment variables and never enter traces.

## Rollback

1. Set `TRULENS_ENABLED=false` to stop new application trace recording.
2. Stop or suspend evaluation tasks from the Snowflake operator role.
3. Revoke evaluator privileges using the matching statements in the SQL template.
4. Preserve existing events according to the organization's retention policy; do not delete
   evidence as an automatic rollback step.

## Official references

- [AI Observability access control](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability/reference)
- [Trace applications with TruLens](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability/trace-applications-trulens)
- [Evaluate applications with TruLens](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability/evaluate-applications-trulens)
