import json

from paperleet.benchmark import cli
from paperleet.providers import ModelConfig
from paperleet.tasks.aicb9.registry import task_root


class FakeClient:
    def __init__(self, answer):
        self.answer = answer

    def complete(self, messages, tools, max_tokens):
        return {
            "choices": [{"message": {"content": json.dumps(self.answer)}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 20},
        }


def test_cli_runs_a01_with_fake_provider_and_writes_report(tmp_path, monkeypatch, capsys):
    reference = json.loads((task_root() / "A01" / "reference_trace.json").read_text(encoding="utf-8"))
    config = ModelConfig("fake", "fake-model", "https://example.invalid", "test-secret")
    monkeypatch.setattr(cli.ModelConfig, "from_env", staticmethod(lambda model: config))
    output = tmp_path / "run.json"
    result = cli.main(
        ["run", "--task", "A01", "--model", "fake-model", "--strategy", "s0",
         "--seed", "7", "--output", str(output)],
        client_factory=lambda config: FakeClient(reference),
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert report["metrics"]["correctness"]["score"] == 100
    assert report["manifest"]["seed"] == 7
    assert "test-secret" not in output.read_text(encoding="utf-8")
    assert capsys.readouterr().out == ""


def test_cli_runs_c01_s3_with_a_mock_agent_runner(tmp_path, monkeypatch, capsys):
    config = ModelConfig("fake", "fake-agent", "https://example.invalid", "test-secret")
    monkeypatch.setattr(cli.ModelConfig, "from_env", staticmethod(lambda model: config))

    class FakeAgentRunner:
        def __init__(self, client, workspace, budget):
            self.workspace = workspace
            self.budget = budget

        def run(self, instruction):
            assert "Required behavior" in instruction
            assert (self.workspace / "src" / "taskflow" / "worker.py").is_file()
            return {
                "task_id": "C01",
                "final_text": "mock patch",
                "plan": {"root_cause": "retry transient errors"},
                "trace": [],
                "budget": {
                    "api_calls": 1,
                    "tool_calls": 0,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "estimated_input_tokens": None,
                },
                "stopped_reason": None,
            }

    monkeypatch.setattr(cli, "AgentRunner", FakeAgentRunner)
    result = cli.main(
        ["run", "--task", "C01", "--model", "fake-agent", "--strategy", "s3"],
        client_factory=lambda config: object(),
    )
    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["metrics"]["correctness"]["status"] == "unavailable"
    assert report["manifest"]["strategy"] == "S3"
    assert report["manifest"]["model_id"] == "fake-agent"

def test_cli_deterministic_evaluation_requires_no_model_api(tmp_path, monkeypatch, capsys):
    answer = task_root() / "A01" / "reference_trace.json"
    def unexpected_model_config(*args, **kwargs):
        raise AssertionError("deterministic evaluation must not configure a model")
    monkeypatch.setattr(cli.ModelConfig, "from_env", staticmethod(unexpected_model_config))
    result = cli.main(["evaluate", "--task", "A01", "--answer", str(answer)])
    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["status"] == "succeeded"
    assert report["manifest"]["strategy"] == "DETERMINISTIC"
    assert report["manifest"]["provider"] == "local"
    assert report["metrics"]["correctness"]["score"] == 100
    assert report["metrics"]["efficiency"]["api_calls"] == 0

def test_cli_evaluates_saved_c01_agent_report_without_model_api(tmp_path, monkeypatch, capsys):
    report_path = tmp_path / "c01-agent-report.json"
    report_path.write_text(json.dumps({
        "task_id": "C01",
        "plan": {
            "root_cause": "TransientError is treated as terminal.",
            "affected_files": ["src/taskflow/worker.py"],
            "expected_invariants": ["PermanentError is not retried."],
            "test_plan": ["run public tests"],
            "risk_factors": ["duplicate terminal events"],
        },
        "trace": [{
            "tool": "run_public_tests",
            "result": {"returncode": 0, "output": "2 passed", "timed_out": False},
        }],
        "final_diff": "diff --git a/src/taskflow/worker.py b/src/taskflow/worker.py\n+retry",
        "changed_files": ["src/taskflow/worker.py"],
        "diff_check": {"returncode": 0, "output": ""},
        "snapshot_available": True,
        "budget": {
            "api_calls": 2, "tool_calls": 1,
            "input_tokens": 100, "output_tokens": 50,
            "estimated_input_tokens": None, "estimated_output_tokens": None,
            "wall_time_s": 5.0,
            "limits": {
                "max_tool_calls": 24, "max_input_tokens": 40000,
                "max_output_tokens": 8000, "max_wall_seconds": 120,
            },
        },
        "stopped_reason": None,
        "hidden_test_score": 55,
    }), encoding="utf-8")

    def unexpected_model_config(*args, **kwargs):
        raise AssertionError("offline C01 evaluation must not configure a model")
    monkeypatch.setattr(cli.ModelConfig, "from_env", staticmethod(unexpected_model_config))

    result = cli.main([
        "evaluate", "--task", "C01", "--answer", str(report_path)
    ])
    run_report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert run_report["status"] == "succeeded"
    assert run_report["manifest"]["provider"] == "local"
    assert run_report["manifest"]["strategy"] == "DETERMINISTIC"
    assert run_report["metrics"]["correctness"]["hidden_tests"]["score"] is None
    assert run_report["metrics"]["correctness"]["public_local_score"]["earned_points"] == 45
