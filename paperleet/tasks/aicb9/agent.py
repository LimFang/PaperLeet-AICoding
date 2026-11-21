"""Budgeted tool-calling runner for C01; uses an OpenAI-compatible chat API.

The runner is intentionally small and auditable. It is suitable for local research
prototypes only; it is not a hardened multi-tenant code execution service.
"""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import json
import math
import os
import subprocess
import sys
import time

from paperleet.providers.openai_compatible import OpenAICompatibleClient


class BudgetExceeded(RuntimeError):
    pass


class ToolRejected(RuntimeError):
    pass


@dataclass
class Budget:
    max_tool_calls: int = 24
    max_input_tokens: int = 40000
    max_output_tokens: int = 8000
    max_wall_seconds: float = 120.0
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    input_usage_complete: bool = True
    output_usage_complete: bool = True

    def check_time(self):
        if time.monotonic() - self.started_at > self.max_wall_seconds:
            raise BudgetExceeded("wall-clock budget exceeded")

    def reserve_request(self, estimated_input_tokens: int, requested_output_tokens: int):
        self.check_time()
        if self.input_tokens + self.estimated_input_tokens + estimated_input_tokens > self.max_input_tokens:
            raise BudgetExceeded("estimated input-token budget exceeded")
        remaining_output = self.max_output_tokens - self.output_tokens - self.estimated_output_tokens
        if remaining_output <= 0:
            raise BudgetExceeded("output-token budget exceeded")
        self.api_calls += 1
        return min(requested_output_tokens, remaining_output)

    def record_tool_call(self):
        self.check_time()
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded("tool-call budget exceeded")
        self.tool_calls += 1

    def add_usage(self, usage, estimated_input_tokens=0, estimated_output_tokens=0):
        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        if prompt_tokens is None:
            self.input_usage_complete = False
            self.estimated_input_tokens += estimated_input_tokens
        else:
            self.input_tokens += int(prompt_tokens)
        if completion_tokens is None:
            self.output_usage_complete = False
            self.estimated_output_tokens += estimated_output_tokens
        else:
            self.output_tokens += int(completion_tokens)
        if self.input_tokens > self.max_input_tokens or self.output_tokens > self.max_output_tokens:
            raise BudgetExceeded("provider-reported token budget exceeded")
        if self.output_tokens + self.estimated_output_tokens > self.max_output_tokens:
            raise BudgetExceeded("estimated output-token budget exceeded")
        if self.input_tokens + self.estimated_input_tokens > self.max_input_tokens:
            raise BudgetExceeded("estimated input-token budget exceeded")


def estimate_tokens(messages):
    text = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    return max(1, (len(text) + 2) // 3)


AGENT_SYSTEM_PROMPT = "You are a coding agent operating in a bounded local repository. Inspect before editing. Submit an immutable structured plan before any patch. Use only provided tools. Never claim tests passed unless run_public_tests confirms it."


TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "list_files", "description": "List source files in the task repository.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a repository file by relative path.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_code", "description": "Search text in repository source files.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "submit_plan", "description": "Submit the immutable pre-edit diagnosis and repair plan. Must be called before apply_patch.", "parameters": {"type": "object", "properties": {"root_cause": {"type": "string"}, "affected_files": {"type": "array", "items": {"type": "string"}}, "expected_invariants": {"type": "array", "items": {"type": "string"}}, "test_plan": {"type": "array", "items": {"type": "string"}}, "risk_factors": {"type": "array", "items": {"type": "string"}}, "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["root_cause", "affected_files", "expected_invariants", "test_plan", "risk_factors"]}}},
    {"type": "function", "function": {"name": "apply_patch", "description": "Replace one exact text span in a repository file. A plan must be submitted first. Tests and private paths are protected.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "run_public_tests", "description": "Run the repository's public pytest suite.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "git_diff", "description": "Show the current working diff.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "git_status", "description": "Show working-tree status.", "parameters": {"type": "object", "properties": {}, "required": []}}},
]


class TaskWorkspace:
    PROTECTED_PARTS = {".git", ".env", ".aicb9", ".venv", "venv", "node_modules",
                       "__pycache__", "hidden", "private", "reference", "mutants", "secrets"}

    def __init__(self, root, command_timeout=15):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace directory does not exist: {self.root}")
        self.command_timeout = command_timeout
        self.plan = None

    def _path(self, relative, write=False):
        rel = PurePosixPath(str(relative))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ToolRejected("path must be a non-empty repository-relative path")
        if any(part in self.PROTECTED_PARTS for part in rel.parts):
            raise ToolRejected("path is protected")
        if write and ("tests" in rel.parts or rel.suffix in {".yaml", ".yml"} and rel.name in {"task.yaml", "registry.yaml"}):
            raise ToolRejected("tests and task specifications are read-only")
        candidate = self.root
        for part in rel.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ToolRejected("symbolic links are not allowed")
        target = candidate.resolve()
        if self.root not in target.parents and target != self.root:
            raise ToolRejected("path escapes the workspace")
        return target

    def list_files(self, pattern="**/*.py"):
        paths = []
        for path in self.root.glob(pattern):
            if path.is_file() and not any(part in self.PROTECTED_PARTS for part in path.relative_to(self.root).parts):
                paths.append(path.relative_to(self.root).as_posix())
        return sorted(paths)[:500]

    def read_file(self, path):
        target = self._path(path)
        if not target.is_file():
            raise ToolRejected("file does not exist")
        content = target.read_text(encoding="utf-8")
        if len(content) > 30000:
            raise ToolRejected("file exceeds the 30,000-character read limit")
        return content

    def search_code(self, query):
        if not query:
            raise ToolRejected("query cannot be empty")
        matches = []
        for relative in self.list_files("**/*"):
            path = self._path(relative)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(lines, 1):
                if query.casefold() in line.casefold():
                    matches.append({"path": relative, "line": number, "text": line[:500]})
                    if len(matches) >= 100:
                        return matches
        return matches

    def submit_plan(self, plan):
        if self.plan is not None:
            raise ToolRejected("the initial plan is immutable; submit revisions as ordinary messages")
        if not isinstance(plan, dict):
            raise ToolRejected("plan must be an object")
        required = ("root_cause", "affected_files", "expected_invariants", "test_plan", "risk_factors")
        if any(key not in plan for key in required):
            raise ToolRejected("plan is missing required fields")
        if not isinstance(plan["root_cause"], str) or not plan["root_cause"].strip():
            raise ToolRejected("root_cause must be a non-empty string")
        normalized = {"root_cause": plan["root_cause"].strip()}
        for key in required[1:]:
            value = plan[key]
            if not isinstance(value, list) or not value or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ToolRejected(f"{key} must be a non-empty list of strings")
            normalized[key] = [item.strip() for item in value]
        evidence = plan.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ToolRejected("evidence must be a list of non-empty strings")
        normalized["evidence"] = [item.strip() for item in evidence]
        self.plan = normalized
        return {"accepted": True, "immutable": True, "plan": self.plan}

    def apply_patch(self, path, old_text, new_text):
        if self.plan is None:
            raise ToolRejected("submit_plan must be called before apply_patch")
        target = self._path(path, write=True)
        if not target.is_file():
            raise ToolRejected("target file does not exist")
        source = target.read_text(encoding="utf-8")
        count = source.count(old_text)
        if not old_text or count != 1:
            raise ToolRejected(f"old_text must match exactly once; found {count}")
        target.write_text(source.replace(old_text, new_text, 1), encoding="utf-8")
        return {"updated": path, "replacements": 1}

    def run_public_tests(self):
        started = time.monotonic()
        test_dir = self.root / "tests" / "public"
        if not test_dir.is_dir():
            return {
                "returncode": 2,
                "output": "No tests/public directory in this task workspace",
                "duration_s": 0.0,
                "timed_out": False,
            }
        env = os.environ.copy()
        env.pop("AICB9_API_KEY", None)
        env.pop("DEEPSEEK_API_KEY", None)
        try:
            proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/public"], cwd=self.root,
                                  text=True, capture_output=True, timeout=self.command_timeout, env=env)
            return {
                "returncode": proc.returncode,
                "output": (proc.stdout + proc.stderr)[-10000:],
                "duration_s": round(time.monotonic() - started, 4),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": 124,
                "output": "Public tests exceeded the command timeout",
                "duration_s": round(time.monotonic() - started, 4),
                "timed_out": True,
            }

    def _git(self, *args, max_output_chars=10000):
        try:
            proc = subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, timeout=5)
            output = proc.stdout + proc.stderr
            if max_output_chars is not None:
                output = output[-max_output_chars:]
            return {"returncode": proc.returncode, "output": output}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"returncode": 127, "output": "git is unavailable or timed out"}

    def git_diff(self):
        return self._git("diff", "--", ".")

    def git_status(self):
        return self._git("status", "--short", "--", ".")

    def final_snapshot(self):
        diff = self._git("diff", "--no-ext-diff", "--", ".", max_output_chars=None)
        names = self._git("diff", "--name-only", "--", ".")
        check = self._git("diff", "--check", "--", ".")
        status = self._git("status", "--short", "--", ".")
        changed_files = (
            [line for line in names["output"].splitlines() if line.strip()]
            if names["returncode"] == 0 else []
        )
        return {
            "final_diff": diff["output"] if diff["returncode"] == 0 else "",
            "changed_files": changed_files,
            "diff_check": check,
            "working_tree_status": status,
            "snapshot_available": all(
                item["returncode"] == 0 for item in (diff, names, check, status)
            ),
        }

    def dispatch(self, name, arguments):
        if name == "list_files": return self.list_files(arguments.get("pattern", "**/*.py"))
        if name == "read_file": return self.read_file(arguments["path"])
        if name == "search_code": return self.search_code(arguments["query"])
        if name == "submit_plan": return self.submit_plan(arguments)
        if name == "apply_patch": return self.apply_patch(**arguments)
        if name == "run_public_tests": return self.run_public_tests()
        if name == "git_diff": return self.git_diff()
        if name == "git_status": return self.git_status()
        raise ToolRejected(f"unknown tool: {name}")


class AgentRunner:
    def __init__(self, client, workspace, budget=None, max_rounds=30):
        self.client = client
        self.workspace = workspace if isinstance(workspace, TaskWorkspace) else TaskWorkspace(workspace)
        self.budget = budget or Budget()
        self.max_rounds = max_rounds
        self.trace = []

    def run(self, instruction):
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ]
        final_text = ""
        stopped_reason = None
        for _ in range(self.max_rounds):
            try:
                estimated = estimate_tokens(messages)
                max_tokens = self.budget.reserve_request(estimated, 2048)
                response = self.client.complete(messages, TOOL_DEFINITIONS, max_tokens)
                choice = response.get("choices", [{}])[0]
                message = choice.get("message", {})
                self.budget.add_usage(
                    response.get("usage"),
                    estimated_input_tokens=estimated,
                    estimated_output_tokens=estimate_tokens([message]),
                )
                self.budget.check_time()
            except BudgetExceeded as exc:
                stopped_reason = str(exc)
                break
            messages.append(message)
            calls = message.get("tool_calls", []) or []
            if not calls:
                final_text = message.get("content") or ""
                break
            for call in calls:
                name = call.get("function", {}).get("name", "")
                raw_args = call.get("function", {}).get("arguments", "{}")
                arguments = raw_args
                try:
                    self.budget.record_tool_call()
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    started = time.monotonic()
                    result = self.workspace.dispatch(name, arguments)
                    error = None
                except BudgetExceeded as exc:
                    result = {"error": str(exc)}
                    error = str(exc)
                    stopped_reason = str(exc)
                    started = time.monotonic()
                except Exception as exc:
                    result = {"error": str(exc)}
                    error = str(exc)
                    started = time.monotonic()
                elapsed = time.monotonic() - started
                self.trace.append({"tool": name, "arguments": arguments,
                                   "result": result, "error": error, "duration_s": round(elapsed, 4)})
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result, ensure_ascii=False, default=str)[:12000]})
                if stopped_reason:
                    break
            if stopped_reason:
                break
        else:
            stopped_reason = "maximum agent rounds reached"
        input_rate = os.environ.get("AICB9_INPUT_PRICE_PER_M")
        output_rate = os.environ.get("AICB9_OUTPUT_PRICE_PER_M")
        price_table_version = os.environ.get("AICB9_PRICE_TABLE_VERSION")
        cost_usd = None
        try:
            input_rate_value = float(input_rate) if input_rate is not None else None
            output_rate_value = float(output_rate) if output_rate is not None else None
            valid_rates = (
                input_rate_value is not None and output_rate_value is not None
                and math.isfinite(input_rate_value) and math.isfinite(output_rate_value)
                and input_rate_value >= 0 and output_rate_value >= 0
            )
        except (TypeError, ValueError):
            valid_rates = False
        usage_complete = (
            self.budget.api_calls > 0
            and self.budget.input_usage_complete
            and self.budget.output_usage_complete
        )
        if valid_rates and price_table_version and usage_complete:
            cost_usd = round(
                self.budget.input_tokens * input_rate_value / 1_000_000
                + self.budget.output_tokens * output_rate_value / 1_000_000,
                8,
            )
        snapshot = self.workspace.final_snapshot()
        public_test_runs = [
            item["result"] for item in self.trace
            if item.get("tool") == "run_public_tests" and isinstance(item.get("result"), dict)
        ]
        public_test_result = public_test_runs[-1] if public_test_runs else None
        return {
            "task_id": "C01",
            "final_text": final_text,
            "plan": self.workspace.plan,
            "trace": self.trace,
            "final_diff": snapshot["final_diff"],
            "changed_files": snapshot["changed_files"],
            "diff_check": snapshot["diff_check"],
            "working_tree_status": snapshot["working_tree_status"],
            "snapshot_available": snapshot["snapshot_available"],
            "public_test_runs": public_test_runs,
            "public_test_result": public_test_result,
            "budget": {
                "tool_calls": self.budget.tool_calls,
                "api_calls": self.budget.api_calls,
                "input_tokens": (
                    self.budget.input_tokens
                    if self.budget.api_calls and self.budget.input_usage_complete else None
                ),
                "output_tokens": (
                    self.budget.output_tokens
                    if self.budget.api_calls and self.budget.output_usage_complete else None
                ),
                "estimated_input_tokens": (
                    self.budget.input_tokens + self.budget.estimated_input_tokens
                    if self.budget.api_calls and not self.budget.input_usage_complete else None
                ),
                "estimated_output_tokens": (
                    self.budget.output_tokens + self.budget.estimated_output_tokens
                    if self.budget.api_calls and not self.budget.output_usage_complete else None
                ),
                "input_usage_complete": self.budget.input_usage_complete,
                "output_usage_complete": self.budget.output_usage_complete,
                "cost_usd": cost_usd,
                "estimated_cost_usd": cost_usd,
                "price_table_version": price_table_version if cost_usd is not None else None,
                "wall_time_s": round(time.monotonic() - self.budget.started_at, 3),
                "limits": {"max_tool_calls": self.budget.max_tool_calls,
                           "max_input_tokens": self.budget.max_input_tokens,
                           "max_output_tokens": self.budget.max_output_tokens,
                           "max_wall_seconds": self.budget.max_wall_seconds},
            },
            "stopped_reason": stopped_reason,
        }
