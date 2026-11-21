# AICB-9 Benchmark Protocol

**Status:** Protocol specification for the AICB-9 pilot. This document defines how future benchmark runs should be compared; it does not claim that the unified runner or all four strategies are already implemented.

## 1. Purpose and scope

AICB-9 evaluates software-engineering capabilities and the contribution of the methods used by coding models and agents. A task result alone is not enough: an evaluation should also identify the execution strategy, evidence supplied to the model, resources consumed, and artifacts produced.

The protocol is designed to answer three separate questions:

1. **Capability:** Can the system complete the software-engineering task?
2. **Method contribution:** Does a strategy improve the result over a simpler baseline?
3. **Efficiency:** What additional resources are required to obtain that improvement?

The benchmark must not treat a more elaborate workflow as inherently better. A strategy is useful only when its measured contribution justifies its additional cost and complexity.

This protocol covers controlled benchmark experiments on versioned tasks and repository snapshots. It does not, by itself, establish long-term production maintenance outcomes.

## 2. Execution strategies

Every run must be assigned one strategy identifier. The strategy describes how the target model receives information and acts; it is not a model capability label.

### S0 — Black-box Single-Prompt (Pb)

- Exactly one target-model completion.
- The prompt contains the task statement, task input, repository context explicitly allowed by the task, the required output contract, and any shared minimal examples.
- It does not contain a prescribed method, original-paper procedure, hidden answer, or tool result prepared specifically for the task.
- No model tool calls, iterative refinement, execution feedback, or follow-up completion are allowed.

S0 measures what the target model can do from the task information and its own learned capabilities.

### S1 — White-box Single-Prompt (Pw)

- Exactly one target-model completion.
- Uses the same prompt template, task input, repository context, output contract, examples, model settings, and budget as S0.
- Adds only a declared `method_steps` field describing the method or procedure being evaluated.
- No model tool calls, iterative refinement, execution feedback, or follow-up completion are allowed.

The S0/S1 comparison estimates the effect of supplying method knowledge. If any other prompt field changes, the comparison is not a valid S0/S1 ablation and must be reported as a protocol deviation.

### S2 — Tool-Augmented Single-Prompt

- Exactly one target-model completion.
- The target model receives the task prompt plus a separately recorded evidence bundle produced before that completion.
- Evidence may include deterministic retrieval results, symbol/dependency information, static-analysis output, or other explicitly named tool output.
- The target model does not call tools, request additional evidence, or iterate after receiving the bundle.
- The evidence producer, version, configuration, input snapshot, output digest, runtime, and resource use must be recorded.

If an auxiliary LLM is used to produce evidence, it is part of the evaluated system: record its model and calls, and include its usage and cost in total system efficiency. Do not silently treat auxiliary model work as free preprocessing.

S2 measures the contribution of externally supplied information, not the target model's ability to discover that information through an agent loop.

### S3 — Agentic

- The model may perform multiple bounded completion calls.
- It may use the declared repository tools, inspect files, submit a plan, edit code, run permitted tests, inspect feedback, and revise its patch.
- All model calls, tool calls, inputs, outputs, tool results, patches, tests, and budget events must be recorded.
- The task-specific maximum calls, tokens, wall time, and tool permissions must be fixed before the run.

S3 measures the complete bounded workflow. It must not receive hidden tests, private scoring rules, or evaluator-only artifacts.

## 3. Fair comparison design

### 3.1 Strategy comparison

To estimate a strategy effect, hold constant:

- task ID and semantic version;
- repository/fixture snapshot and task input;
- target model and provider configuration;
- output contract and scoring/evaluator version;
- random seed where supported;
- maximum resource budget and timeout policy.

Change only the strategy-specific component under study. For S0 versus S1, the only permitted prompt difference is the method-steps field. For S2, the evidence bundle is the treatment and its generation cost must be counted. For S3, the additional interaction and tool loop are the treatment.

A comparison is invalid if one strategy receives a different task instance, additional undisclosed context, a larger resource budget, or access to private evaluator information.

### 3.2 Model comparison

To estimate a model-generation effect, hold constant:

- task version, snapshot, and input;
- strategy definition and prompt template;
- evaluator version and scoring rules;
- resource budget and tool permissions;
- run count and aggregation method.

Change only the target model/provider configuration. Record the exact model identifier returned/configured by the provider. Avoid mutable aliases such as `latest` where a stable model identifier is available.

### 3.3 Budget parity

A budget is a set of limits, not a target to be exhausted. Define the limits before running an experiment.

At minimum record:
- maximum input tokens;
- maximum output tokens;
- maximum target-model completion calls;
- maximum tool calls;
- maximum wall-clock time;
- maximum monetary cost, if a trustworthy price configuration is available.

S0 and S1 have one completion call and zero model tool calls. S2 has one target-model completion; evidence-generation resources are recorded separately and included in total system cost. S3 uses the declared multi-call and tool budgets.

For a strategy comparison, use the same overall resource ceilings where technically meaningful. If a strategy requires a resource that another does not use, report the unused budget and actual consumption rather than inventing a penalty.

### 3.4 Prompt and context control

Store the exact rendered prompt or a privacy-safe, access-controlled artifact reference. Compute a prompt hash over the canonical UTF-8 prompt content after template rendering and before provider submission. Exclude credentials and transport headers from the hash.

Record the prompt template version, output schema version, tool schema version (when applicable), context sources, and context truncation behavior.

Examples included in prompts must not contain hidden answers or task-specific gold labels.

## 4. Repeated runs and aggregation

Model-backed strategies may be stochastic. For a new task/strategy/model comparison, the recommended default is at least five independent runs per condition when the budget permits. If fewer runs are used, report the actual sample size and treat the result as exploratory.

- Use the same task instances across strategies.
- Pair seeds across conditions when the provider supports seeds; record when a provider ignores or does not expose seed control.
- Do not assume identical seeds guarantee identical outputs across providers or model versions.
- Report the number of attempted, completed, failed, and excluded runs, with exclusion reasons.
- For repeated runs, report median and interquartile range; mean and standard deviation may be added.
- For deterministic CPU-only evaluators, one run can establish the deterministic score, but tests should still verify repeatability.

Do not select only the best run. Do not silently drop timeouts, malformed outputs, or budget-exhausted runs; report them as failures or separately defined execution outcomes.

## 5. Task eligibility and strategy applicability

Not every strategy is meaningful for every task.

- A structured answer task may support S0/S1/S2, but not S3 if there is no permitted action loop.
- A repository repair task may support all four strategies if the task input and evidence can be presented consistently.
- If a task input exceeds a single-prompt context budget, mark S0/S1/S2 as unsupported for that task or define a task-level context protocol before evaluation. Do not truncate one strategy silently.
- A task may list only strategies that have an implemented adapter and a valid evaluation path. Planned support must be labelled as planned, not runnable.

The task registry should be the source of truth for task-specific strategy support and budget limits.

## 6. Run artifacts and provenance

Every completed or failed run should have a manifest containing the fields defined in [Reproducibility](reproducibility.md). Preserve, where applicable:

- rendered prompt hash and template version;
- task input and repository snapshot digest;
- model/provider configuration;
- strategy identifier and adapter version;
- model/tool execution trace;
- patch or structured answer;
- public test report;
- evaluator output and rubric version;
- budget and usage record;
- final status and stop reason.

Do not put API keys, hidden tests, private gold labels, or private scoring logic in public artifacts.

## 7. Interpretation

Report task-level correctness, evidence, robustness, efficiency, and maintainability separately. Do not collapse unrelated task metrics into a single leaderboard score without a pre-registered aggregation rule.

A positive strategy delta does not automatically imply that the strategy is cost-effective. A low-cost strategy is not automatically better if it materially reduces correctness or robustness. Present the performance/cost trade-off explicitly.

For sequential maintenance tasks, report outcomes at each checkpoint and cumulatively. A short controlled sequence is evidence about the benchmark fixture under that sequence; it is not direct evidence of years-long production maintenance cost.

## 8. Current implementation status

This document specifies the target protocol. At the time of this protocol revision:

- AICB-9 includes A01, B01, B03, and C01 pilot tasks.
- A01/B01 have deterministic structured-answer evaluators.
- B03 has a local mutation-testing development evaluator and public demonstration mutants.
- C01 has a bounded local Agent prototype and mock-based tests.
- A unified benchmark runner and complete S0-S3 adapters are not yet implemented.
- C01's declared hidden-test scoring component is not available in the public/local evaluator.

Do not describe a strategy or metric as implemented until a runnable adapter and corresponding tests exist.
