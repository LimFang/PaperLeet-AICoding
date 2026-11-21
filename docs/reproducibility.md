# AICB-9 Reproducibility

**Status:** Required provenance contract for benchmark runs. The v0.2 runner emits the versioned manifest and report fields described here; provider seed forwarding and versioned price-table cost calculation remain unavailable.

## 1. Reproducibility objective

A result should be traceable to the exact task, repository state, prompt, model configuration, strategy implementation, evaluator, and resource limits that produced it.

Re-running the same configuration may still produce different outputs for stochastic models. Reproducibility therefore requires both complete provenance and repeated-run reporting; it does not promise bit-for-bit identical model outputs.

## 2. Required run manifest

Each run should persist a machine-readable manifest with the following fields.

| Field | Required meaning |
|---|---|
| `run_id` | Unique identifier for this execution |
| `created_at`, `started_at`, `finished_at` | UTC timestamps |
| `status` | queued, running, succeeded, failed, timed_out, budget_exceeded, or cancelled |
| `task_id`, `task_version` | Stable task identity and semantic version |
| `fixture_digest` | Digest of the exact task/repository fixture snapshot |
| `repository_commit` | Commit SHA when the fixture is Git-backed |
| `benchmark_protocol_version` | Version of the protocol used |
| `evaluator_version`, `rubric_version` | Exact scoring implementation and rubric |
| `runner_version` | Runner package version or Git commit SHA |
| `provider`, `model_id` | Provider and exact model identifier |
| `provider_api_version` | API version or endpoint compatibility version, if available |
| `strategy`, `strategy_version` | S0/S1/S2/S3 and adapter version |
| `prompt_template_version`, `prompt_hash` | Template version and hash of rendered prompt content |
| `output_schema_version` | Structured output contract version |
| `tool_schema_hash` | Hash of tool definitions for tool-enabled runs |
| `seed` | Requested seed, or null if unsupported |
| `model_parameters` | Temperature, top-p, max output tokens and other relevant parameters |
| `budget_limits` | Input/output token, call, tool, wall-time and cost ceilings |
| `usage` | Provider-reported usage and separately labelled estimates |
| `price_table_version` | Price configuration used, or null |
| `stop_reason` | Why the run ended |
| `artifact_digests` | Digests/references for output, patch, trace and test report |

The schema may evolve, but field meanings must remain stable within a schema version.

## 3. Prompt hashing

- Render the complete prompt using the declared template and task input.
- Normalize only line endings to LF and encode as UTF-8.
- Compute SHA-256 over the exact content submitted as model messages, preserving message roles and ordering in a canonical serialization.
- Exclude API keys, authorization headers and other transport credentials.
- Record the template version and serialization version alongside the hash.

A hash proves identity of the hashed content; it does not prove that the provider received or processed it. Preserve a secure prompt artifact when policy permits, otherwise retain the hash and non-sensitive prompt metadata.

## 4. Task and fixture identity

- Assign a semantic version to every task.
- Pin the fixture to a Git commit or content digest.
- Record all task assets that affect the answer: source files, public tests, configuration, input data, tool outputs and relevant environment settings.
- Do not rely on a moving branch name as the only snapshot identifier.
- Keep private test and gold-label digests in the trusted evaluator's records; never expose private contents to the Agent.

If a fixture changes, create a new task version or explicitly document a compatible patch-level change and update its digest.

## 5. Model and provider identity

Record the exact provider/model identifier, endpoint/API version where available, request parameters, requested seed, and provider-reported usage.

If the provider exposes only a mutable alias or does not disclose a model revision, record that limitation and the request date/time. Do not claim the model is immutable.

Do not store credentials in the manifest. Store only non-secret provider configuration needed to interpret the run.

## 6. Execution trace and artifacts

For S0/S1, preserve the prompt hash, response, output validation result, and provider usage.

For S2, additionally preserve the evidence bundle digest, evidence producer/version, source references, and preprocessing resource use.

For S3, additionally preserve the ordered sequence of model requests, tool calls, tool results, patches, test executions, budget checks, and terminal stop reason.

Artifacts should be immutable or content-addressed where practical. The manifest should reference their digests. Do not include hidden tests, private labels, API keys, or host secrets in public artifacts.

## 7. Environment and dependencies

Record relevant runtime information:
- Python/runtime version;
- operating system and architecture;
- dependency lockfile digest;
- evaluator/runner commit;
- container image digest where containerized;
- locale/time zone if they affect parsing or tests;
- relevant environment variables by name and non-secret value only.

Avoid recording irrelevant host-specific data that could expose user information.

## 8. Repeated runs

For stochastic model-backed tasks, record each run independently. The experiment summary must include:
- number of attempted/completed/failed runs;
- all exclusion reasons;
- aggregation method;
- median and interquartile range by default;
- mean and standard deviation when useful;
- seed policy and whether the provider honors it.

Do not overwrite earlier run records when repeating an experiment.

## 9. Example run report

The following is an illustrative shape of the v0.2 report schema. Placeholder values are not measured results.

```json
{
  "schema_version": "1.0",
  "status": "succeeded",
  "manifest": {
    "run_id": "example-run-0001",
    "created_at": "2026-11-21T00:00:00Z",
    "started_at": "2026-11-21T00:00:00Z",
    "finished_at": "2026-11-21T00:00:12Z",
    "task_id": "C01",
    "task_version": "1.0.0",
    "fixture_digest": "git-tree-sha1:<fixture-tree-sha>",
    "repository_commit": null,
    "protocol_version": "0.1",
    "evaluator_version": "1.0.0",
    "rubric_version": "1.0.0",
    "runner_version": "0.1.0",
    "provider": "provider-name",
    "model_id": "exact-model-id",
    "strategy": "S3",
    "strategy_version": "0.1.0",
    "prompt_template_version": "1",
    "prompt_hash": "sha256:<prompt-digest>",
    "output_schema_version": "1",
    "tool_schema_hash": "sha256:<tool-schema-digest>",
    "seed": 42,
    "seed_applied": false,
    "seed_status": "recorded_only_provider_seed_not_forwarded",
    "model_parameters": {
      "max_output_tokens": 8000
    },
    "budget_limits": {
      "max_tool_calls": 24,
      "max_input_tokens": 40000,
      "max_output_tokens": 8000,
      "max_wall_seconds": 120
    },
    "usage": {
      "input_tokens": null,
      "output_tokens": null,
      "estimated_input_tokens": 1800,
      "estimated_output_tokens": null,
      "usage_source": "unavailable",
      "api_calls": 2,
      "tool_calls": 3,
      "wall_time_seconds": 12.0,
      "cost_usd": null,
      "currency": "USD",
      "price_table_version": null
    }
  },
  "metrics": {
    "correctness": {
      "status": "unavailable",
      "reason": "trusted hidden-test evaluation is not implemented"
    },
    "reasoning": {"status": "not_implemented"},
    "robustness": {"status": "not_implemented"},
    "efficiency": {"status": "available"},
    "maintainability": {"status": "not_implemented"}
  },
  "artifacts": {
    "output_digest": "sha256:<output-digest>",
    "patch_digest": null,
    "trace_digest": "sha256:<trace-digest>",
    "test_report_digest": null
  },
  "output": {},
  "stop_reason": null
}
```

The report deliberately keeps provider-reported usage separate from local estimates. Cost remains null until a versioned price table is configured.

## 10. Trusted C01 evaluation

The public/local C01 report must keep the hidden-test component unavailable. A separately operated trusted evaluator may return a signed result envelope matching the run ID, task version, fixture digest, and rubric version. The envelope schema, Ed25519 signing rules, and score-combination boundary are documented in [Trusted C01 Evaluation](trusted-evaluation.md).

The Agent workspace and public CLI must never receive the hidden test suite, signing keys, or trusted hidden score. A JSON field supplied by an Agent is not a trusted result.
