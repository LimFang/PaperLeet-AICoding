# AICB-9 Scoring Rules

**Status:** Scoring policy for the current pilot and future task additions. This document distinguishes implemented public scoring from planned or trusted-only components.

## 1. General rules

- Each task owns its rubric, maximum score, required outputs, and pass threshold.
- Scores must include a component breakdown and rubric version.
- Deterministic evaluators should be preferred where ground truth exists.
- A free-form explanation is not sufficient evidence of a correct answer when the task requires a verifiable artifact.
- Invalid outputs, missing fields, duplicate identifiers, timeouts, and execution errors must follow an explicit task policy.
- A task's unavailable component must remain unavailable. Do not silently redistribute its weight among other components.
- Do not compare raw scores across tasks as if they measured an identical construct.

## 2. Current pilot tasks

### A01 — Trace the Execution

The current deterministic rubric has a maximum of 100 points:

| Component | Weight |
|---|---:|
| Operation result | 40 |
| Expired keys | 25 |
| LRU order | 20 |
| Evicted keys | 15 |

The evaluator compares each required step and component against the reference trace. Missing values do not match explicit null values. The valid step domain is exactly 1–6: missing expected steps receive partial/no credit, while duplicate or unknown step IDs, unknown fields, and wrong field types are rejected. Missing result/list fields receive no credit.

### B01 — Root Cause Diagnosis

**Rubric version: 1.1.0.** The deterministic rubric has a maximum of 100 points:

| Component | Weight |
|---|---:|
| Primary file | 20 |
| Root cause ID | 30 |
| Affected function | 10 |
| Causal order | 20 |
| Evidence F1 | 15 |
| Alternative-hypothesis exclusion | 5 |

The reference diagnosis and evidence catalog define the expected answer. Evidence precision and recall are computed separately:

- Precision is the fraction of submitted evidence IDs that match the gold evidence set.
- Recall is the fraction of gold evidence IDs present in the submission.
- The 15-point evidence component uses their harmonic mean (F1).
- Unknown evidence IDs remain in the submitted set as unsupported predictions and reduce precision.
- Duplicate evidence IDs, malformed list values, wrong field types, and unknown top-level fields are rejected.
- Missing fields receive no credit rather than causing a crash.

This prevents a submission from obtaining full evidence credit by including the required evidence alongside arbitrary unsupported IDs.

### B03 — Test the Hidden Bug

The current local development evaluator has a maximum of 100 points:

| Component | Weight |
|---|---:|
| Reference implementation passes | 20 |
| Valid mutants killed | 60 |
| Determinism | 10 |
| Suite integrity | 10 |

The six mutants currently committed to the public repository are development/demo fixtures. They are visible to users and must not be described as secret official hidden mutants. Official hidden variants, if introduced, belong in a separate trusted evaluator.

A mutant is killed only by the defined behavioral/assertion failure. Import errors, collection errors, test errors and timeouts are not kills. The reference implementation must pass before mutant outcomes are accepted.

### C01 — Repository Bug Fix

The task specification currently declares these weights:

| Component | Declared weight |
|---|---:|
| Hidden-test outcome | 55 |
| Pre-edit plan | 15 |
| Verification | 15 |
| Efficiency | 10 |
| Patch quality | 5 |

The public/local pilot does not currently implement the trusted hidden-test component. Therefore:
- public/local reports must mark the 55-point hidden-test component as unavailable;
- the Agent cannot supply or self-report this score;
- the remaining 45 points must not be silently renormalized to 100;
- an official composite score is unavailable until a trusted evaluator provides the hidden-test result under a versioned rubric.

The current C01 prototype uses a mock client in automated tests. A real API run is opt-in and must record actual provider usage and the configured budget.

## 3. Future task scoring

New tasks must define before release:
- required output schema;
- reference/gold data and its provenance;
- component weights and score range;
- pass threshold, if any;
- partial-credit policy;
- malformed-output policy;
- timeout and budget-exhaustion policy;
- evaluator version and task version;
- which components are public, private, or unavailable.

For repository-analysis tasks, report localization and evidence separately from defect detection. For maintenance tasks, report correctness and regression outcomes at each checkpoint, alongside scope/rework proxies.

## 4. Suite-level aggregation

- Publish per-task scores and component results first.
- If a suite-level score is required, define task weights before evaluation.
- Prefer a macro-average or pre-registered task weights; do not pool raw counts from tasks with different denominators.
- Report the number of tasks and runs included.
- Show unavailable/not-applicable components explicitly.
- Do not publish a leaderboard until task comparability, model/version identity, budget parity, contamination policy and aggregation rules are documented.

## 5. Status vocabulary

Use these statuses consistently:

| Status | Meaning |
|---|---|
| `available` | The component was evaluated and a valid result exists |
| `unavailable` | The component applies but no valid measurement is available |
| `not_implemented` | The evaluator or execution path does not yet exist |
| `not_applicable` | The component does not apply to this task/strategy |
| `invalid` | The submitted artifact or run failed the component's validity requirements |

Do not encode these states as numeric zero. A measured zero is different from an unavailable score.
