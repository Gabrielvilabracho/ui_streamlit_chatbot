# AI Functions evaluation plan

This plan evolves Sof~IA from its current RAG baseline into a measured Snowflake AI Functions workflow. It prioritizes quality, safety, cost, and latency before adding more infrastructure.

## Quick path

1. Create a representative evaluation dataset.
2. Run the existing batch evaluation for every candidate change.
3. Compare quality, latency, tokens, and cost with the approved baseline.
4. Promote only configurations that meet the agreed thresholds.

## Current baseline

The application already provides the starting point:

- Cortex Search retrieves document chunks.
- The application generates grounded answers through its configured Snowflake AI services.
- TruLens records traces and supports table-backed batch evaluation.
- Privacy and UI regressions have automated tests.

The current implementation is traditional RAG. It is not GraphRAG and does not include an explicit document-classification pipeline.

## Phase 1: build the evaluation foundation

The local setup script is [`sql/evaluation_foundation.sql`](../sql/evaluation_foundation.sql).
It creates the empty `DATALAB.TEST` tables only; it does not load questions,
grant execution access, or schedule a Task.

Create these Snowflake-owned datasets under `DATALAB.TEST`:

| Dataset | Purpose | Minimum fields |
| --- | --- | --- |
| Evaluation cases | Stable questions used to compare configurations | case ID, question, expected answer when available, domain, policy, difficulty |
| Evaluation runs | Metadata for one evaluated candidate | run ID, agent version, prompt version, model, retrieval configuration, started time |
| Evaluation results | Metric results for each case and run | run ID, case ID, metric, score, latency, tokens, cost, trace reference |
| Feedback samples | Reviewed production feedback, separated from the evaluation set | feedback ID, question, outcome, reviewer decision, approved-for-evaluation flag |

Use real, approved questions as the core of the dataset. Add synthetic cases only to cover missing scenarios and edge cases. Keep production conversations and evaluation data separate.

## Phase 2: evaluate every candidate

Evaluate a candidate whenever the model, prompt, Search configuration, document set, metadata filter, or agent tool changes.

| Area | What to measure |
| --- | --- |
| Answer quality | Groundedness, answer relevance, coherence, and correctness when a trusted expected answer exists |
| Retrieval quality | Context relevance, citation faithfulness, and retrieval accuracy |
| Safety | Rejection of sensitive input, cross-policy access denial, prompt-injection handling, and safe insufficient-evidence answers |
| Operations | Latency, token use, cost, failed tool calls, and timeout rate |

Run the existing TruLens batch flow against the evaluation cases. Correctness requires a ground-truth column; do not fabricate expected answers merely to enable the metric.

## Phase 3: optimize with controlled experiments

Change one variable per experiment:

- model;
- composed system prompt;
- number of retrieved chunks;
- search filters and metadata;
- ranking settings; or
- agent tool configuration.

Compare each run against the approved baseline. A candidate is eligible for promotion only when it meets quality and safety thresholds and its cost and latency remain acceptable.

## Automation decision

Start with one scheduled Snowflake Task that runs the evaluation and stores results.

| Add this | Only when this is true |
| --- | --- |
| Task Graph | Evaluation has dependent stages: classify, index, evaluate, compare, then alert |
| Streams and Tasks | Only changed or newly arrived documents and feedback must be processed |
| Dynamic Tables | Derived evaluation or document data must remain fresh automatically |
| dbt Project | Many source tables require transformations, tests, documentation, and lineage |

Do not add these components merely because they are available. Their value must be demonstrated by volume, freshness, or workflow complexity.

## Document classification

Add classification only if evaluation shows it improves retrieval. Start with metadata such as document type, department, product, policy, effective date, and sensitivity level. Evaluate filtered retrieval against the current unfiltered baseline before making it part of production.

## GraphRAG decision

GraphRAG is a later option, not the first implementation step. Consider it only when important questions require verified multi-hop relationships across departments, policies, products, and processes.

Before adopting it:

1. Demonstrate that current RAG plus metadata filters and multi-step retrieval misses these questions.
2. Start with one department and a small business core: policy, product, process, department, system, and regulation.
3. Store evidence for every graph relationship.
4. Test graph retrieval against the RAG baseline for quality, safety, cost, and latency.

## Promotion and review

Use versioned agents and stable aliases. Keep a record of the candidate configuration, evaluation evidence, approval, and rollback target. Review failed or low-scoring cases through their traces before changing a prompt or model.

## Next planning step

Load the first approved evaluation dataset, then define the candidate baseline, metric thresholds,
Task schedule, and promotion owner. Do not add Task Graph, dbt, Streams, Dynamic Tables,
classification, or GraphRAG until their stated trigger is observed.
