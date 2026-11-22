# Snowflake agent platform architecture

This document defines the recommended target architecture for a reusable Snowflake agent platform. It is a design reference, not evidence that the described Snowflake objects, grants, or deployment automation already exist.

## Decision

Manage agent definitions, prompts, skills, evaluation datasets, and deployment scripts from a central, version-controlled platform repository. Keep domain data, search indexes, knowledge graphs, and access policies inside their owning domains.

```text
Git configuration repository
        │
        ▼
Snowflake agent platform
        │
        ├── versioned Cortex Agents
        ├── configuration and skill sources
        ├── evaluation datasets and results
        └── native observability
        │
        ▼
Streamlit applications, APIs, and other consumers
```

## Responsibility boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| Platform configuration | Reusable prompts, skills, templates, evaluations, deployment definitions | Business-domain source data |
| Domain | Documents, chunks, graph entities and edges, Search services, data-policy views | Shared platform prompts or agent lifecycle policy |
| Cortex Agent | Tool orchestration and grounded responses within granted access | Authorization decisions outside Snowflake grants |
| Consumer application | User experience, caller identity verification, request guardrails, safe response rendering | Hidden agent tool orchestration |

## Source of truth and deployment artifacts

The editable source of truth is a dedicated Git repository, such as `agent-platform-config`:

```text
agent-platform-config/
├── prompts/
│   ├── global/
│   ├── domains/
│   └── agent-types/
├── skills/
├── templates/
├── agents/
├── evaluations/
└── deploy/
```

Prompts are composed from small Markdown files and policy-specific configuration. A generator produces one complete `agent_spec.yaml` per agent. The generated specification is uploaded to a Snowflake stage or imported from a Git repository by Snowflake; it is the deployment artifact, not the editable source.

```text
Shared prompts + domain prompts + agent policy + tool configuration
                              │
                              ▼
                       agent_spec.yaml
                              │
                              ▼
                   Snowflake stage or Git integration
                               │
                               ▼
                         Cortex Agent version
```

## Executable repository blueprint

The next repository must be named and structured as an executable platform project, not as a
collection of manually copied prompts. The following layout is the source-of-truth contract for
`agent-platform-config`:

```text
agent-platform-config/
├── README.md                         # Quick start, environments, and delivery policy
├── pyproject.toml                    # Generator, validation, and test dependencies
├── prompts/
│   ├── global/                       # Safety, privacy, evidence, and refusal rules
│   ├── agent-types/                  # Knowledge-assistant behavior shared by agents
│   ├── domains/                      # Domain vocabulary and response rules
│   └── policies/                     # Policy-specific constraints and escalation rules
├── skills/
│   └── <skill-name>/SKILL.md         # One independently versioned reusable skill
├── agents/
│   └── <agent-name>/agent.yaml       # Editable agent source manifest
├── evaluations/
│   ├── datasets/                     # Approved case definitions, never raw conversations
│   ├── thresholds/                   # Versioned promotion thresholds by environment
│   └── acceptance/                   # Deterministic acceptance-case definitions
├── deploy/
│   ├── 00-bootstrap.sql              # Platform schemas, stages, and non-production setup
│   ├── 10-grants.sql                 # Least-privilege roles and grants
│   ├── 20-upload.sql                 # Generated-artifact upload or Git-integration actions
│   ├── 30-agents.sql                 # Candidate agent version creation
│   ├── 40-promote.sql                # Alias promotion after evidence review
│   └── 50-rollback.sql               # Alias rollback to the approved immutable version
├── scripts/
│   ├── build_agent_specs.py          # Compose editable sources into generated artifacts
│   ├── validate_platform.py          # Validate manifests, references, and policy boundaries
│   └── package_evaluations.py        # Validate approved evaluation-data shape
├── generated/                        # Git-ignored, reproducible deployment artifacts
│   └── <environment>/<agent-name>/agent_spec.yaml
├── tests/
│   ├── unit/                         # Generator and manifest validation
│   └── acceptance/                   # Offline contract and policy-isolation checks
└── .github/workflows/validate.yml    # Build and validation only; no automatic promotion
```

`generated/` is not edited by people. A build must regenerate it from a clean checkout, so every
deployed `agent_spec.yaml` can be traced to a source commit, a source manifest, and a prompt set.

### Editable contracts

Each agent has one source manifest. The exact Snowflake deployment schema belongs to the generated
artifact; this repository-level manifest deliberately stays stable across deployment mechanisms:

```yaml
# agents/sofia-general/agent.yaml
name: SOFIA_GENERAL_AGENT
environment: test
description: Policy-isolated general knowledge assistant
prompt_layers:
  - prompts/global/safety.md
  - prompts/global/evidence.md
  - prompts/agent-types/knowledge-assistant.md
  - prompts/domains/sofia.md
  - prompts/policies/general.md
skills:
  - procedure-explanation
  - policy-comparison
tools:
  cortex_search:
    allowed_services:
      - DATALAB.TEST.SOFIA_GENERAL_SEARCH
    inaccessible_tool_behavior: reject
  evaluation:
    dataset: DATALAB.TEST.SOFIA_EVALUATION_CASES
  policy: GENERAL
  threshold_set: sofia-knowledge-assistant-v1
release:
  stable_alias: PRODUCTION
  candidate_alias: STAGING
```

The generator must reject manifests that reference a missing prompt, skill, threshold set, or
evaluation policy. It must also reject an agent with more than its explicitly allowed Search
services. A prompt or skill reference never grants access; the matching SQL grants remain the
enforcement boundary.

Every skill folder contains a `SKILL.md` with a short name, purpose, allowed inputs, expected
output, prohibited actions, and evaluation cases. Skills must not contain credentials, role
assumptions, hidden cross-policy behavior, or deployment commands.

### Generator contract

`scripts/build_agent_specs.py` must perform these deterministic steps:

1. Load one `agents/<agent-name>/agent.yaml` manifest.
2. Resolve prompt layers in the declared order, rejecting path traversal and duplicate layers.
3. Validate the named skills and their required metadata.
4. Render one complete `generated/<environment>/<agent-name>/agent_spec.yaml` artifact.
5. Write a companion build manifest containing the source commit, source file hashes, generator
   version, target environment, and generated-artifact hash.
6. Exit non-zero without producing a deployable artifact if validation fails.

The generator must not contact Snowflake, invoke models, or promote aliases. Generation is local
and reproducible; deployment is a separate, explicitly authorized operation.

### Deployment contract

Deployment is ordered and reviewable. The scripts in `deploy/` must be idempotent where Snowflake
supports it and must never silently switch a production alias.

| Stage | Input | Required evidence | Output |
| --- | --- | --- | --- |
| Bootstrap | Reviewed `00-bootstrap.sql` | Schema and stage names match the selected environment | Platform objects exist |
| Grant | Reviewed `10-grants.sql` | Role matrix shows least privilege and no cross-policy Search access | Roles can use only intended objects |
| Build | Source manifests and prompt layers | Generator and unit tests pass | Hashed `agent_spec.yaml` artifacts |
| Upload | Generated artifact | Artifact hash matches the build manifest | Candidate artifact is available to Snowflake |
| Create version | `30-agents.sql` | Agent uses only approved tools and environment objects | Immutable candidate version |
| Evaluate | Candidate version and approved dataset | Quality, safety, latency, and cost evidence | Promotion decision |
| Promote | Approved candidate and `40-promote.sql` | Named approver and rollback target | Stable alias moves to the candidate |
| Roll back | `50-rollback.sql` | Incident or failed evidence review | Stable alias returns to prior version |

The CI workflow validates source manifests, generated-artifact reproducibility, prompt composition,
skill references, policy isolation, and evaluation-data shape. It may create a build artifact, but
it must not upload, create agents, call paid AI functions, or promote an alias automatically.

### Environment and promotion rules

Maintain separate `dev`, `test`, and `production` configuration values. Source manifests may be
shared, but tool names, roles, warehouse names, stages, aliases, and dataset references are
environment-specific. A promotion record must name:

- source commit and generated-artifact hash;
- agent and immutable candidate version;
- prompt, skill, model, and retrieval-configuration versions;
- baseline run and evaluation-result references;
- quality and safety threshold results;
- approving owner; and
- exact prior alias target for rollback.

No deployment may use a mutable `LIVE` target as the consumer contract. Consumers invoke the
stable alias; promotion and rollback move that alias only after recorded evidence review.

### First implementation sequence

Build the new repository in this order:

1. Add the directory layout, `agent.yaml` schema, one General-agent manifest, and one minimal
   `SKILL.md`.
2. Implement the local generator and its validation tests; prove that two clean builds produce the
   same artifact hash.
3. Add `dev` and `test` deployment templates with placeholder identifiers, not production grants.
4. Connect the repository to the `DATALAB.TEST` evaluation foundation and add approved test
   cases for the General policy.
5. Deploy one `STAGING` candidate manually, evaluate it, and record its rollback target.
6. Add the Privacy and Credit Aftersales manifests only after their isolated Search services,
   grants, and evaluation cases exist.

GraphRAG, custom tools, MCP connectors, automatic scheduling, and automatic production promotion
remain explicitly out of scope for this first repository version.

## Snowflake platform layout

The selected test deployment keeps all Sof~IA configuration, evaluation and domain
objects in one existing namespace:

```text
DATALAB.TEST
├── SOFIA_*_AGENT                 # versioned Cortex Agent objects
├── SOFIA_*_SEARCH                # policy-isolated Search services
├── SOFIA_*_CHUNKS                # secure policy source views
├── SOFIA_EVALUATION_*            # approved cases, runs and results
└── SOFIA_*                       # lifecycle metadata and future configuration objects
```

This single-namespace decision is specific to the current test environment. An
agent may use a domain tool only through explicit Snowflake grants; placement
does not grant cross-policy access.

## Prompts and skills

### Prompts

Compose prompts in this order:

```text
Global safety and privacy rules
+ Agent-type behavior
+ Domain-specific rules
+ Policy-specific rules
+ Tool descriptions and constraints
= Agent orchestration and response instructions
```

Prompts define behavior; they are not access-control boundaries. Roles, grants, policy-isolated Search services, and restricted tool configuration enforce access.

### Skills

Store each reusable Snowflake skill in its own folder with `SKILL.md` at the folder root. Skills may be sourced from a Snowflake stage, a Git repository, or a Cortex Extension. An agent references only the skills it is allowed to use in its `agent_spec.yaml`.

```text
skills/
├── procedure-explanation/SKILL.md
├── policy-comparison/SKILL.md
└── graph-retrieval/SKILL.md
```

At runtime, Cortex evaluates each configured skill's name and description against the user request, loads the chosen `SKILL.md`, and follows its instructions. Agent orchestration instructions must also state when each skill is expected. Skill selection is model-mediated, so skills cannot be used as the sole control for sensitive access or actions.

Do not add a skill, MCP connector, custom tool, or code-execution capability without a concrete task, least-privilege grants, regression tests, evaluation cases, observability, and rollback path.

## Example: policy-isolated knowledge assistants

Sof~IA remains a multi-agent pattern because GraphRAG changes retrieval, not authorization:

```text
Verified caller role
        │
        ▼
Application policy router
        ├── GENERAL           → SOFIA_GENERAL_AGENT
        ├── PRIVACY           → SOFIA_PRIVACY_AGENT
        └── CREDIT_AFTERSALES → SOFIA_CREDIT_AFTERSALES_AGENT
                                      │
                                      ▼
                         policy-specific Search and graph projection
```

Agents may share prompt templates and skills, but each agent receives only its policy-specific tools and data projection. A central agent with unrestricted access is not an acceptable shortcut for policy-isolated domains.

## Lifecycle and promotion

Use Snowflake agent versions and aliases rather than editing production configuration in place:

```text
Git change
  → generated candidate specification
  → LIVE or DRAFT version
  → automated and human evaluation
  → immutable VERSION$N
  → STAGING alias
  → PRODUCTION alias
```

If a regression is observed, move the `PRODUCTION` alias back to the last approved immutable version. Consumer applications should invoke a stable alias, not `LIVE`.

## Evaluation and observability

Every agent change must be tested with policy-specific datasets covering supported answers, insufficient evidence, conflicts, historical documents, prompt injection, timeout/tool failure, citation correctness, and cross-policy access denial.

Promotion evidence should include:

- Groundedness, relevance, correctness, and citation faithfulness.
- Retrieval and graph-path accuracy when GraphRAG is enabled.
- Latency, token use, tool failures, and cost.
- Zero cross-policy leakage.

Use native Cortex Agent observability for planning, tool calls, model response, version, latency, token use, and feedback. The consumer application records its own safe operational telemetry. Do not assume that application-level tracing exposes all internal Cortex Agent spans.

## Adoption path

1. Establish the configuration repository, agent platform schemas, roles, and stages.
2. Deploy one minimal knowledge assistant with a single Cortex Search tool and no Skills, MCP, or custom tools.
3. Add an evaluation dataset, result history, quality thresholds, and a scheduled evaluation Task before adding more capabilities.
4. Run controlled experiments that change one variable at a time: model, prompt, retrieval settings, or metadata filters.
5. Add document classification when measured retrieval results show that document type, domain, product, policy, or date filters improve answers.
6. Add a Task Graph only when evaluation has dependent steps, such as classification, indexing, evaluation, comparison, and alerting.
7. Add dbt Projects, Streams, or Dynamic Tables only when the volume or freshness needs justify their operational cost.
8. Add reusable Skills only for measured, recurring tasks that improve results.
9. Add GraphRAG only where evaluations show that vector retrieval alone cannot answer required multi-hop questions.

The implementation details and adoption criteria are defined in [AI Functions evaluation plan](ai-functions-evaluation-plan.md).

## Related project documentation

- [Current application architecture](architecture.md)
- [Cortex Agent container deployment boundaries](snowflake-container.md)
- [Prepared Sof~IA agent instructions](sofia-agent-instructions.md)
- [Document access policies](document-access-policies.md)
