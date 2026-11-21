# AICB-9 Security Model

**Status:** Threat model and local-execution boundaries for the AICB-9 pilot. The current implementation is **not** a secure sandbox and must not accept arbitrary untrusted online submissions.

## 1. Trust domains

| Domain | Contents | Security role |
|---|---|---|
| Public repository | Task statements, public fixtures, public tests, public B03 mutants, runner code | Readable and untrusted as a secrecy boundary |
| Local task workspace | Public repository snapshot, Agent patch, generated tests/results | Treated as code executing with the local user's privileges |
| Public/local evaluator | Deterministic A01/B01 scoring, B03 development mutation runner, C01 45-point local rubric | Can produce practice feedback; **cannot** certify hidden-test success |
| Trusted private evaluator (planned) | Private tests/mutants, gold labels, signing keys, evaluator manifests | Separately isolated service; **not implemented in this public repo** |
| Benchmark result publication (planned) | Verified scores, model/task/rubric versions, audited run metadata | Must reject unverified or mismatched trusted results |

The GitHub repository and its branches are not a suitable place to store hidden tests, secret labels, API keys, evaluation signing keys, or private evaluator code.

## 2. Threats and non-goals

The local B03 mutation runner executes submitted Python tests, and the C01 Agent may invoke a public pytest suite against a modified workspace. A malicious test or repository file can execute arbitrary Python with the user's operating-system permissions. It can attempt to:
- read files from the user's home directory, SSH agent, cloud configuration, or accessible mounted volumes;
- contact the network and exfiltrate secrets;
- spawn subprocesses or consume CPU, memory, disk, and process resources;
- attempt symlink/path traversal or manipulate local Git state;
- inject instructions into model-visible repository files;
- claim that private tests passed or that a hidden score was awarded;
- tamper with local reports or test output.

**Important:** A timeout, path filter, immutable plan, or sanitized environment is not an OS security boundary. They are defense-in-depth measures for *trusted* local practice only. The current implementation does not contain untrusted filesystem/network accesses.

## 3. Controls implemented in the pilot

### 3.1 Task workspace controls

C01's `TaskWorkspace`:
- requires repository-relative file paths for tool reads and edits;
- rejects parent-directory traversal, symbolic links, protected paths, test edits, and task/registry configuration writes;
- requires a structured pre-edit plan before patching; the plan is immutable;
- limits model/tool interactions, token estimates, wall time, and local subprocess execution duration;
- requires a clean Git working tree for user-supplied CLI workspaces and captures the final diff.

Protected names include `.git`, `.env*`, `.ssh`, `.aws`, `.config`, `.netrc`, `.npmrc`, `.pypirc`, `hidden`, `private`, `reference`, `mutants`, `secrets`, and other local directories. This list is not an exhaustive filesystem access-control mechanism.

### 3.2 Subprocess environment minimization

Public C01 tests and B03 mutants use `task_subprocess_env` instead of inheriting the parent's full environment. The function retains only a small allowlist for Python/process operation (e.g. PATH, locale, temporary-directory settings), sets `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1`, and does not forward cloud/API keys, HOME, or the parent's PYTHONPATH. B03 sets PYTHONPATH explicitly to the selected mutant fixture.

This reduces **accidental** credential propagation through `os.environ` and subprocess diagnostics. It does **not** prevent arbitrary code from reading accessible credential files or using the network.

### 3.3 Local reporting and test outcomes

- B03's six mutants committed under `tasks/aicb9/fixtures/ministore/b03/mutants/` are **public development fixtures**, not official hidden mutants.
- C01 locally scores only the 45 public points (plan completeness, public-test verification, budget compliance, and basic patch hygiene).
- C01's 55 hidden-test points remain `unavailable` and `null` locally. The 45 local points are never rescaled to 100.
- Agent assertions about hidden-test success cannot become official score fields.
- The signed result envelope in [Trusted C01 Evaluation](trusted-evaluation.md) is **only a schema and protocol**; a trusted-key registry, signature verification service, and private hidden-test runner do not yet exist.

## 4. Private evaluation boundary

Future official evaluation must use a **separate private repository or service** containing all hidden tests, mutations, gold labels, and signing secrets. Private test source must never be mounted into the Agent workspace.

The trusted result handoff requires:
- exact run identity (`run_id`) and task identity/version;
- exact fixture content digest (not merely a mutable branch name);
- evaluator/rubric version and private-suite digest;
- a structured hidden-test result and scoring rationale;
- trusted issuer identity, key ID, timestamp, and a verified signature.

For C01, the [signed envelope contract](trusted-evaluation.md) specifies Ed25519 and a 0–55 hidden-test component. A JSON file resembling this envelope is **not** sufficient: the independent ingestion service must validate its signature and match identifiers against stored run manifests before accepting it.

No public CLI flag, user-supplied score, or Agent tool response may submit a trusted hidden-test score.

## 5. Requirements before accepting untrusted submissions

A hosted evaluator must first implement and independently review:

1. **Process/OS isolation:** disposable per-submission containers or VMs with non-root identities, hardened syscall policy, independent process namespace, and no host mounts.
2. **Resource limits:** cgroup/VM caps for CPU, memory, PIDs, temporary disk, file size, and elapsed time; forced cleanup after timeout/crash.
3. **Network isolation:** deny network by default, or explicitly allow a minimal audited set of endpoints when a task requires it.
4. **Credential isolation:** no API keys, host SSH agents, cloud metadata endpoints, provider tokens, or home-directory mounts visible to submissions.
5. **Private test isolation:** private fixtures are injected only into a trusted verifier after the Agent produces its artifact, without revealing test source.
6. **Artifact controls:** cap stdout/stderr and diff sizes; redact credentials; retain immutable per-run digests, task versions, and evaluator identity.
7. **Operational controls:** request authentication, rate limiting, abuse detection, logging, retention/deletion policy, incident response, and periodic patching of execution images.
8. **Adversarial verification:** test file escape, symlink traversal, network egress, CPU/memory/process exhaustion, malicious pytest plugins, and attempts to inject forged scores or result envelopes.

Until these requirements pass a separate security review, do not deploy the local B03/C01 runner as a public code-execution endpoint or leaderboard back end.

## 6. Practical local-use guidance

Use A01/B01 deterministic scoring freely; they parse structured input and do not execute submitted Python. Use B03 and C01 only on a trusted local machine with trusted repository/test content. Avoid running them on a machine containing sensitive credentials if the submitted source code is not trusted.

Do not confuse “local CPU evaluation” with “safe to execute untrusted code.” The security limitation is independent of whether the model API is paid, free, or absent.

Related: [Benchmark Protocol](benchmark-protocol.md), [Scoring Rules](scoring-rules.md), [Trusted C01 Evaluation](trusted-evaluation.md).
