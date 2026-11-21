# AICB-9 Evaluation Metrics

**Status:** Metric definitions for the AICB-9 protocol. A metric is available only when the task provides the required ground truth and evaluator implementation.

## 1. Reporting principles

1. Report task-level results before any cross-task aggregation.
2. Separate outcome quality from resource consumption.
3. Prefer deterministic, inspectable evaluation over free-form model judging.
4. Mark unavailable metrics as unavailable; do not substitute zero or infer a value.
5. Preserve the numerator, denominator, sample size, evaluator version, and exclusions behind every reported rate.
6. Do not treat a proxy such as changed lines as a direct measurement of maintainability.

The five reporting dimensions are correctness, reasoning/evidence, robustness, efficiency, and maintainability.

## 2. Correctness

### Task score

A task may define a weighted score from deterministic components. The score must be accompanied by its rubric version and component breakdown.

`TaskScore = sum(component_score_i)`

The denominator and weights are task-specific. A score of 80 on one task is not necessarily equivalent in difficulty or construct coverage to 80 on another task.

### Pass rate

`PassRate = successful_runs / eligible_attempted_runs`

Define success before evaluation. Timeouts, budget exhaustion, invalid outputs, and execution failures remain in the attempted-run denominator unless the protocol explicitly identifies an infrastructure failure and documents its exclusion.

### Hidden-test pass

Report the trusted evaluator's result separately from public tests. The Agent must not see hidden test contents or be allowed to self-report hidden-test outcomes.

## 3. Reasoning and evidence

Use these metrics only when the task defines a gold evidence set or structured reasoning rubric.

### Evidence precision and recall

`EvidencePrecision = |predicted_evidence ∩ gold_evidence| / |predicted_evidence|`

`EvidenceRecall = |predicted_evidence ∩ gold_evidence| / |gold_evidence|`

If the predicted set is empty, precision is undefined; report it as unavailable or use a task-defined convention. If the gold set is empty, recall is undefined. Do not silently assign 1.0.

F1 may be reported when both values are defined:

`EvidenceF1 = 2 * Precision * Recall / (Precision + Recall)`

Evidence units must be specified per task: file, symbol, line span, dependency edge, log event, or another explicit unit. For line-level localization, document the overlap/tolerance rule.

### Plan quality

A plan may be scored only against a published structured rubric, such as root-cause plausibility, affected-file coverage, invariant identification, test adequacy, and risk identification. Report each component. Do not use an LLM-as-a-Judge as the sole basis for the official score.

## 4. Robustness

### Mutation score

`MutationScore = killed_valid_mutants / evaluable_non_equivalent_mutants`

A mutant is killed only when the submitted tests fail for the defined assertion/behavioral reason. Collection errors, import errors, test errors, and timeouts are not kills. The reference implementation must pass the submitted suite before mutant outcomes are considered valid.

Report the number of valid mutants and their visibility status. Public demonstration mutants are not hidden benchmark assets.

### Regression rate

For a task with a baseline test suite:

`RegressionRate = newly_failing_baseline_tests / baseline_passing_tests`

Report the raw counts as well. A test that was already failing before the change is not a new regression.

### Run stability

For repeated runs, report score distribution and success frequency. Do not use the best run as the headline result.

## 5. Efficiency

Record actual usage and configured limits separately.

| Metric | Definition | Unit |
|---|---|---|
| Input tokens | Provider-reported prompt/input tokens | tokens |
| Output tokens | Provider-reported completion/output tokens | tokens |
| Estimated tokens | Local estimate of input/output tokens, reported separately from provider usage | tokens; clearly labelled estimate |
| API calls | Requests sent to model endpoints | calls |
| Tool calls | Agent tool invocations | calls |
| Wall time | Run start to terminal completion/stop | seconds |
| Cost | Calculated from provider usage and a versioned price table | currency |
| Budget utilization | Actual consumption divided by configured limit | ratio |

Provider-reported usage and estimated usage must never be merged into one field. The local estimate may be reported alongside actual usage for calibration; it must never replace a missing provider value silently.

### Cost calculation

When a versioned price table is available:

`Cost = sum(token_count_k * price_per_million_k / 1,000,000) + declared_non_token_costs`

The price table must identify provider, exact model identifier, effective date, currency, input/output rates, cached-token treatment, and any other applicable pricing dimensions. Store the price-table version with the run.

If a price cannot be verified for the exact model and run date, report cost as unavailable/null. Do not infer cost from a nearby model or current price when evaluating historical runs.

### Cost per successful run

This may be reported as total cost divided by successful runs. If there are no successful runs, report it as unavailable. Always show the success rate beside it; cost per success alone can hide failure frequency.

## 6. Maintainability and change behavior

These measures are proxies unless supported by longitudinal repository evidence.

| Metric | Definition | Interpretation constraint |
|---|---|---|
| Changed files | Number of files modified | Scope only; not quality by itself |
| Added/deleted LOC | Lines added and deleted in the patch | Churn proxy; formatting and generated files can distort it |
| Changed symbols | Number of functions/classes/modules changed | Requires a defined parser and language coverage |
| Out-of-scope changes | Changes outside a task-defined affected/allowed set | Requires gold scope or a reviewed reference set |
| Rework | Later edits that revise/revert earlier task changes | Requires sequential checkpoints and lineage |
| Regression rate | Previously passing tests that fail after a change | Correctness/maintenance interaction |

Do not assume that a larger diff is worse, that a smaller diff is better, or that one short synthetic sequence measures long-term production maintenance. Interpret scope and rework alongside correctness, test coverage, and task requirements.

For sequential tasks, report each metric per checkpoint and cumulatively.

## 7. Aggregation and comparison

- Report per-task and per-strategy metrics first.
- For repeated runs, report sample size, median, and interquartile range; mean and standard deviation may be added.
- If a suite-level score is needed, publish task weights before running the benchmark. Use a documented macro-average or pre-registered weights; do not pool raw counts from different tasks.
- Report strategy deltas per task:

`DeltaScore(strategy) = Score(strategy) - Score(S0)`

- Report cost and quality together. A strategy with a positive score delta may still be inefficient.
- For comparisons across models, preserve the same task version, strategy, budget, evaluator, and input set.
- Any excluded run must have a recorded reason.

## 8. Availability requirements

A metric must not be emitted as a measured value unless:
- its required data were captured;
- its evaluator or calculation is implemented;
- the evaluator/version is recorded;
- its denominator and exclusion policy are known.

Use explicit statuses such as `available`, `not_applicable`, `not_implemented`, and `unavailable`. Do not encode all four states as numeric zero.
