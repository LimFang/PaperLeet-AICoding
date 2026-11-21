from pathlib import Path
import json
import subprocess
import pytest

from paperleet.tasks.aicb9.agent import AgentRunner, Budget, BudgetExceeded, TaskWorkspace, ToolRejected


class FakeClient:
    def __init__(self):
        self.calls = 0
    def complete(self, messages, tools, max_tokens):
        self.calls += 1
        if self.calls == 1:
            return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "1", "type": "function", "function": {"name": "submit_plan", "arguments": '{"root_cause":"retry handler marks transient errors failed","affected_files":["src/taskflow/worker.py"],"expected_invariants":["permanent errors are not retried"],"test_plan":["run public tests"],"risk_factors":["duplicate terminal events"]}'}},
                {"id": "2", "type": "function", "function": {"name": "read_file", "arguments": '{"path":"src/taskflow/worker.py"}'}}
            ]}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        return {"choices": [{"message": {"role": "assistant", "content": "Inspected the Worker. No patch applied in this mock run."}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def test_plan_gate_blocks_patch_before_plan(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "worker.py").write_text("x = 1\n")
    workspace = TaskWorkspace(tmp_path)
    with pytest.raises(ToolRejected, match="submit_plan"):
        workspace.apply_patch("src/worker.py", "x = 1", "x = 2")


def test_path_traversal_and_test_edits_are_rejected(tmp_path):
    workspace = TaskWorkspace(tmp_path)
    with pytest.raises(ToolRejected):
        workspace.read_file("../secret")
    workspace.plan = {"root_cause": "test"}
    with pytest.raises(ToolRejected, match="read-only"):
        workspace.apply_patch("tests/public/test_x.py", "a", "b")


def test_agent_runner_records_immutable_plan_and_usage(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "worker.py").write_text("x = 1\n")
    result = AgentRunner(FakeClient(), tmp_path, budget=Budget(max_tool_calls=5)).run("Inspect and plan.")
    assert result["plan"]["root_cause"].startswith("retry handler")
    assert result["budget"]["tool_calls"] == 2
    assert result["budget"]["api_calls"] == 2
    assert result["budget"]["input_tokens"] == 200
    assert len(result["trace"]) == 2


def test_budget_rejects_excess_tool_calls():
    budget = Budget(max_tool_calls=1)
    budget.record_tool_call()
    with pytest.raises(BudgetExceeded):
        budget.record_tool_call()


def test_provider_usage_over_budget_stops_before_dispatch(tmp_path):
    result = AgentRunner(FakeClient(), tmp_path, budget=Budget(max_output_tokens=10)).run("Inspect.")
    assert result["stopped_reason"] == "provider-reported token budget exceeded"
    assert result["budget"]["tool_calls"] == 0


def test_agent_cli_includes_c01_statement(tmp_path, monkeypatch, capsys):
    import scripts.aicb9 as cli

    class RecordingClient:
        def complete(self, messages, tools, max_tokens):
            prompt = messages[1]["content"]
            assert "retry_wait" in prompt
            assert "PermanentError" in prompt
            assert "Do not edit tests" in prompt
            return {"choices": [{"message": {"role": "assistant", "content": "Read the task."}}]}

    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=PaperLeet", "-c", "user.email=paperleet@example.invalid",
         "commit", "--allow-empty", "--quiet", "-m", "Initialize C01 test workspace"],
        cwd=tmp_path, check=True,
    )
    monkeypatch.setattr(cli, "OpenAICompatibleClient", RecordingClient)
    assert cli.main(["agent", "C01", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["final_text"] == "Read the task."


def test_git_tools_scope_to_task_directory(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    inside = tmp_path / "task" / "worker.py"
    inside.parent.mkdir()
    outside = tmp_path / "other.py"
    for path in (inside, outside):
        path.write_text("value = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    for path in (inside, outside):
        path.write_text("value = 2\n")

    workspace = TaskWorkspace(inside.parent)
    for git_tool in (workspace.git_status, workspace.git_diff):
        result = git_tool()
        assert result["returncode"] == 0, result
        assert "worker.py" in result["output"]
        assert "other.py" not in result["output"]


def test_c01_public_fixture_passes_its_smoke_tests():
    fixture = Path(__file__).resolve().parents[2] / "tasks" / "aicb9" / "fixtures" / "taskflow" / "repository"
    workspace = TaskWorkspace(fixture)
    result = workspace.run_public_tests()
    assert result["returncode"] == 0, result


def test_c01_workspace_blocks_symlink_escape(tmp_path):
    outside = tmp_path.parent / "aicb9-outside.txt"
    outside.write_text("secret")
    (tmp_path / "link.txt").symlink_to(outside)
    workspace = TaskWorkspace(tmp_path)
    with pytest.raises(ToolRejected, match="symbolic links"):
        workspace.read_file("link.txt")


def test_plan_is_immutable(tmp_path):
    workspace = TaskWorkspace(tmp_path)
    plan = {"root_cause": "transient errors are terminal", "affected_files": ["src/taskflow/worker.py"],
            "expected_invariants": ["permanent errors are not retried"], "test_plan": ["run tests"],
            "risk_factors": ["duplicate terminal event"]}
    workspace.submit_plan(plan)
    with pytest.raises(ToolRejected, match="immutable"):
        workspace.submit_plan(plan)


def test_apply_patch_requires_unique_match_and_plan(tmp_path):
    source = tmp_path / "src" / "worker.py"
    source.parent.mkdir()
    source.write_text("return False\n")
    workspace = TaskWorkspace(tmp_path)
    workspace.submit_plan({"root_cause": "x", "affected_files": ["src/worker.py"],
                           "expected_invariants": ["preserve terminal states"],
                           "test_plan": ["run public tests"],
                           "risk_factors": ["duplicate events"]})
    with pytest.raises(ToolRejected, match="found 0"):
        workspace.apply_patch("src/worker.py", "missing", "replacement")
    assert workspace.apply_patch("src/worker.py", "return False", "return True")["replacements"] == 1


def test_c01_fixture_reproduces_transient_retry_bug():
    import importlib
    import sys

    fixture = Path(__file__).resolve().parents[2] / "tasks" / "aicb9" / "fixtures" / "taskflow" / "repository"
    sys.path.insert(0, str(fixture / "src"))
    try:
        errors = importlib.import_module("taskflow.errors")
        events = importlib.import_module("taskflow.events")
        models = importlib.import_module("taskflow.models")
        worker_module = importlib.import_module("taskflow.worker")
        calls = {"count": 0}
        def flaky():
            calls["count"] += 1
            if calls["count"] == 1:
                raise errors.TransientError("temporary")
            return "ok"
        task = models.Task("transient", flaky, max_retries=2)
        worker = worker_module.Worker(events.EventLog())
        worker.run(task)
        # This assertion documents the starter's defect; the learner must change it.
        assert task.status == "failed"
        assert task.attempts == 1
        assert calls["count"] == 1
    finally:
        sys.path.remove(str(fixture / "src"))
        for module_name in list(sys.modules):
            if module_name == "taskflow" or module_name.startswith("taskflow."):
                sys.modules.pop(module_name, None)


def test_openai_compatible_client_uses_injected_transport_without_network():
    from paperleet.tasks.aicb9.agent import OpenAICompatibleClient

    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {}}).encode()
    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return Response()

    client = OpenAICompatibleClient(api_key="unit-test-key", model="unit-test-model",
                                    base_url="https://example.invalid", opener=fake_opener)
    result = client.complete([{"role": "user", "content": "hello"}], [], 32)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["url"] == "https://example.invalid/chat/completions"
    assert captured["authorization"] == "Bearer unit-test-key"
    assert captured["payload"]["model"] == "unit-test-model"
    assert captured["payload"]["max_tokens"] == 32

def test_agent_runner_keeps_missing_provider_usage_unknown(tmp_path):
    class NoUsageClient:
        def complete(self, messages, tools, max_tokens):
            return {"choices": [{"message": {"role": "assistant", "content": "Done."}}]}

    result = AgentRunner(NoUsageClient(), tmp_path).run("Inspect the repository.")
    assert result["budget"]["api_calls"] == 1
    assert result["budget"]["input_tokens"] is None
    assert result["budget"]["output_tokens"] is None
    assert result["budget"]["estimated_input_tokens"] is not None
    assert result["budget"]["estimated_input_tokens"] > 0
    assert result["budget"]["estimated_output_tokens"] is not None
    assert result["budget"]["estimated_output_tokens"] > 0
    assert result["budget"]["cost_usd"] is None
    assert result["budget"]["price_table_version"] is None

def test_budget_accumulates_estimated_input_when_provider_usage_is_missing():
    budget = Budget(max_input_tokens=100)
    budget.reserve_request(60, 20)
    budget.add_usage({}, estimated_input_tokens=60)
    with pytest.raises(BudgetExceeded, match="estimated input-token budget exceeded"):
        budget.reserve_request(50, 20)

def test_agent_runner_captures_final_diff_changed_files_and_public_test_output(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    source = tmp_path / "src" / "worker.py"
    source.parent.mkdir()
    source.write_text("def run():\\n    return False\\n", encoding="utf-8")
    tests_dir = tmp_path / "tests" / "public"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_public.py").write_text("def test_public_contract():\\n    assert True\\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=PaperLeet", "-c", "user.email=paperleet@example.invalid",
         "commit", "--quiet", "-m", "Initial C01 test fixture"],
        cwd=tmp_path, check=True,
    )

    class PatchAndTestClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools, max_tokens):
            self.calls += 1
            if self.calls == 1:
                calls = [
                    {"id": "plan", "type": "function", "function": {
                        "name": "submit_plan",
                        "arguments": json.dumps({
                            "root_cause": "Worker returns terminal failure for retryable errors.",
                            "affected_files": ["src/worker.py"],
                            "expected_invariants": ["successful tasks complete once"],
                            "test_plan": ["run public tests"],
                            "risk_factors": ["duplicate terminal events"],
                        }),
                    }},
                    {"id": "patch", "type": "function", "function": {
                        "name": "apply_patch",
                        "arguments": json.dumps({
                            "path": "src/worker.py",
                            "old_text": "return False",
                            "new_text": "return True",
                        }),
                    }},
                    {"id": "tests", "type": "function", "function": {
                        "name": "run_public_tests", "arguments": "{}",
                    }},
                ]
                message = {"role": "assistant", "content": None, "tool_calls": calls}
            else:
                message = {"role": "assistant", "content": "Patch applied and public tests run."}
            return {
                "choices": [{"message": message}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 12},
            }

    result = AgentRunner(
        PatchAndTestClient(), tmp_path,
        budget=Budget(max_tool_calls=5, max_wall_seconds=20),
    ).run("Fix the worker.")
    assert result["plan"]["root_cause"].startswith("Worker returns")
    assert "return True" in result["final_diff"]
    assert result["changed_files"] == ["src/worker.py"]
    assert result["diff_check"]["returncode"] == 0
    assert result["snapshot_available"] is True
    assert result["public_test_result"]["returncode"] == 0
    assert result["public_test_runs"][-1]["timed_out"] is False


def test_agent_runner_records_tool_budget_exhaustion_and_final_snapshot(tmp_path):
    class OneToolClient:
        def complete(self, messages, tools, max_tokens):
            return {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "plan",
                        "type": "function",
                        "function": {"name": "submit_plan", "arguments": "{}"},
                    }],
                }}],
            }

    result = AgentRunner(OneToolClient(), tmp_path, budget=Budget(max_tool_calls=0)).run("Inspect.")
    assert result["stopped_reason"] == "tool-call budget exceeded"
    assert result["budget"]["tool_calls"] == 0
    assert result["snapshot_available"] is False


def test_budget_accounts_for_estimated_output_when_provider_omits_usage():
    budget = Budget(max_output_tokens=100)
    budget.reserve_request(10, 50)
    budget.add_usage({}, estimated_output_tokens=80)
    with pytest.raises(BudgetExceeded, match="estimated output-token budget exceeded"):
        budget.reserve_request(10, 50)
