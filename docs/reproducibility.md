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

## 9. Example manifest

The following is an illustrative shape, not a claim that the current CLI emits these fields:

```json
{
  "schema_version": "1.0",
  "run_id": "example-run-0001",
  "status": "succeeded",
  "task": {
    "id": "C01",
    "version": "1.0.0",
    "fixture_digest": "sha256:<fixture-digest>",
    "repository_commit": "<fixture-commit>"
  },
  "protocol": {
    "version": "0.1",
    "strategy": "S3",
    "strategy_version": "0.1"
  },
  "model": {
    "provider": "provider-name",
    "model_id": "exact-model-id",
    "api_version": null,
    "seed": 42,
    "parameters": {
      "temperature": 0,
      "max_output_tokens": 2048
    }
  },
  "provenance": {
    "prompt_template_version": "1",
    "prompt_hash": "sha256:<prompt-digest>",
    "output_schema_version": "1",
    "runner_version": "<git-commit>",
    "evaluator_version": "<evaluator-version>",
    "rubric_version": "1"
  },
  "budget_limits": {
    "max_input_tokens": 40000,
    "max_output_tokens": 8000,
    "max_model_calls": 24,
    "max_tool_calls": 24,
    "max_wall_seconds": 120
  },
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "usage_source": "not_reported",
    "estimated_input_tokens": null,
    "estimated_output_tokens": null,
    "api_calls": 0,
    "tool_calls": 0,
    "wall_time_seconds": null,
    "cost": null,
    "currency": "USD",
    "price_table_version": null
  },
  "artifacts": {
    "patch_digest": null,
    "trace_digest": null,
    "test_report_digest": null
  },
  "stop_reason": null
}
```

Placeholder values above are illustrative and must be replaced with actual values in real reports.
