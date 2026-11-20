# Runtime guardrails

Both application entrypoints enable context-aware guardrails in addition to the existing
input/output validators. Detected personal data is masked; detected credentials are rejected.
The diagnostic hooks report stable rejection IDs without recording the rejected content.

## Behavior

| Boundary | Action |
| --- | --- |
| New UI question | Validate length, reject detected secrets/instruction overrides, then mask before adding it to application conversation state or rendering it. |
| Existing conversation / retry | Mask historical content and source metadata before display; withhold messages containing detected secrets and disable their retry prompt. |
| Service input | Recheck question and all history, reject unsupported message roles, and enforce the context budget. No silent history truncation. |
| Direct retrieval | Mask identifiers, titles and content; reject detected secrets and override instructions before generation. Remove modified or non-HTTP(S) source URLs. |
| Generation | Check the complete serialized prompt/request size, not just the latest question. |
| Output | Mask text and sources; reject numeric references without a corresponding source. Return a fixed abstention instead of an uncited substantive answer. |
| No direct evidence | Abstain without calling the model. Exact standalone greetings/thanks return a fixed response without sources. Agent identity checks still run for greetings. |
| Explicit trace attributes | Mask personal data and replace detected secrets with a fixed withheld marker. Unknown token usage is absent, not zero. |

Recognized personal-data patterns include email addresses, international/labelled phone
numbers and Spanish mobile/fixed numbers, Spanish DNI/NIE and labelled identity documents,
IBAN-shaped values and labelled bank accounts. Names are not masked. Secret signals include
private-key headers, common API-key shapes, labelled passwords/tokens, bearer credentials,
credential-bearing URLs and signed-URL parameter names. Detection is heuristic: this is **not
comprehensive DLP**, a compliance certification, or a guarantee against obfuscated identifiers.

## Configurable defaults

Set these environment variables in the application runtime. Invalid settings fail closed
without echoing their values. Restart the runtime when changing quota policy.

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `RAG_GUARDRAIL_MAX_CONTEXT_BYTES` | 48000 | Maximum UTF-8 bytes in the serialized visible prompt/request. Not an exact tokenizer count. |
| `RAG_GUARDRAIL_REQUESTS_PER_WINDOW` | 10 | Admitted requests per user in the rolling rate window, including retries and greetings. |
| `RAG_GUARDRAIL_RATE_WINDOW_SECONDS` | 60 | Rolling request-rate window. |
| `RAG_GUARDRAIL_TOKEN_QUOTA` | 524288 | Accounted tokens available in the quota window. |
| `RAG_GUARDRAIL_QUOTA_WINDOW_SECONDS` | 3600 | Quota-window lifetime; active requests cannot be evicted. Rate-window retention can postpone cleanup. |
| `RAG_GUARDRAIL_TOKEN_RESERVATION` | 65536 | Reserved per admitted request; retained for unknown usage or failed calls. Must not exceed the quota. |
| `RAG_GUARDRAIL_DEADLINE_SECONDS` | 30 | Total service deadline, including retrieval and Agent identity rechecks. |

The ledger is lock-protected, bounded to 4096 subjects, and shared across service recreation
in **one Python process**. Clear conversation does not reset it. Direct mode keys the quota
by connection account/user; a shared Snowflake connection has a shared quota, not verified
per-visitor quotas. Agent mode keys it by the verified viewer, across that viewer's roles.
Subject keys are hashed in memory. No chat content is stored in the ledger.

Reported token usage settles the reservation, including valid zero. A response rejected
after generation still consumes its reported usage. Failed or unreported calls keep their
reservation. Reservations prevent simultaneous requests from spending the same allowance;
if actual provider usage exceeds a reservation, the actual usage is charged and later
requests are blocked when the quota is exhausted. This is not a hard provider billing cap.
An exact per-model tokenizer budget, distributed/persistent quotas, and hidden Agent tool
usage limits require provider-side controls. Process restarts reset this local ledger.

## Trust and deadline boundaries

The direct prompt serializes question, history and sources as untrusted JSON data under
fixed instructions. Explicit instruction-override signals are rejected as defense in depth.
Existing approved-role checks, caller rights, fixed Agent selection and parameterized SQL
remain independent; a custom text validator cannot grant permissions or select another Agent.

Citation checks establish **reference integrity, not semantic entailment**. A real citation
can still accompany an unsupported assertion. No universal relevance threshold or automatic
claim-verification model is introduced. Missing/invalid evidence does not trigger a paid retry.

The application cannot inspect or sanitize the named Agent's hidden retrieved chunks, alter
its tool permissions, or enforce its hidden prompt budget. Apply the planning and response
instructions in [the Agent setup guide](sofia-agent-instructions.md), plus appropriate
Snowflake access/masking controls, separately. Editing local Markdown does not deploy them.

Remaining time is passed to COMPLETE and Agent SQL statements. Production COMPLETE does not
retry without its timeout if the client rejects statement parameters. SQL timeouts round up
to whole seconds, and late results are withheld. The current synchronous Search port has no
verified cancellation contract: it is checked when retrieval returns, but **cannot be forcibly
interrupted here**. No background thread is used to pretend that provider work was cancelled.

Explicit TruLens attributes are protected, but independent SDK auto-capture, external
exporters, provider logs and deployment-level tracing settings require separate review.
Do not enable raw argument/return-value recording as a substitute for these safe attributes.

## Programmatic use and verification

`build_orchestrator()` and `snowflake_app.py` enable `RuntimeGuardrails` automatically.
Low-level `RagOrchestrator` / `CortexAgentService` constructors retain their dependency-
injection API: callers assembling their own service must pass `safety=RuntimeGuardrails(...)`.
For direct services also supply a trusted `subject`; never derive it from question text.
The old `Guardrail` port remains text-only; context, quota and deadline rules do not belong
inside an arbitrary `str -> None` validator or an observational hook.

Run `.venv/bin/python -m pytest` for faked service, UI, quota and regression checks. No live
Snowflake calls are required. A deployment test must separately establish grants, Agent
instructions, provider cancellation behavior and multi-process quota requirements.
