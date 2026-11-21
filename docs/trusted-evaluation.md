# C01 Trusted Evaluation Result Contract

## Boundary

C01 has a 55-point hidden-test component. It must be evaluated outside the Agent workspace by a separately controlled evaluator. The public/local runner:
- does not load hidden tests or private labels;
- does not accept a hidden score from Agent output, model text, tool arguments, or CLI flags;
- always reports the hidden-test component as `unavailable`;
- does not combine a hidden score into an official total.

The Agent workspace exposes only the public fixture and public tests. Trusted tests, gold labels, signing keys, and evaluator credentials must remain outside it.

## Signed result envelope

The schema is [`trusted-c01-result.schema.json`](../paperleet/benchmark/schemas/trusted-c01-result.schema.json). A trusted evaluator returns one signed envelope tied to the exact run and task snapshot.

Required identity fields:
- `task_id` must be `C01`;
- `run_id` must match the benchmark report's manifest;
- `task_version`, `fixture_digest`, and `rubric_version` must match the evaluated run;
- `issuer` and `key_id` identify the trusted evaluator and its registered signing key;
- `test_suite_digest` identifies the private test suite without disclosing it.

The `hidden_test_score` is an integer from 0 through 55. `max_hidden_test_score` is fixed at 55. The envelope uses Ed25519.

## Signature verification

The signature is computed over the canonical UTF-8 JSON serialization of every envelope field except `signature`, with object keys sorted and separators `(",", ":")`. The trusted ingestion service must:
1. validate the envelope against the JSON Schema;
2. resolve `issuer` and `key_id` against an explicit trusted-key allowlist;
3. verify the Ed25519 signature;
4. match run ID, task version, fixture digest, and rubric version against the stored run manifest;
5. reject duplicate, stale, mismatched, or unverifiable results.

Schema validation alone is not proof of trust. The public repository currently defines the envelope contract but does not implement a trusted-key registry, signature verification service, or hidden-test evaluator.

## Combining scores

The public/local report contains at most 45 points from the pre-edit plan, public-test verification, budget compliance, and patch quality. It also reports how many of those 45 points were actually available.

Only after a trusted envelope has been verified and all 45 local points are available may an external result service calculate:

`official_score = public_local_earned_points + hidden_test_score`

The maximum is 100. Do not rescale a partial local score to 45, 100, or any other denominator. If the local report is incomplete, the official composite remains unavailable even when a hidden-test result exists.

## Interface isolation

The envelope is not an Agent tool, workspace file, prompt input, public CLI argument, or local evaluator input. The public/local evaluator ignores any similarly named field in Agent output. A future trusted ingestion service must be a separate process with access to private tests and signing keys; it must not mount those assets into the Agent workspace.
