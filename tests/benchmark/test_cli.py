import json
import subprocess

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
    monkeypatch.setattr(cli.ModelConfig, "from_env", lambda model: config)
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
    monkeypatch.setattr(cli.ModelConfig, "from_env", lambda model: config)

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
