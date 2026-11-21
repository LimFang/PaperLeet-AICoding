"""Trust-boundary checks for local AICB-9 subprocesses.

These tests verify environment filtering and path checks only. They do not
claim the local evaluator securely isolates untrusted Python from the OS.
"""
from pathlib import Path

import pytest

from paperleet.tasks.aicb9 import agent, mutation
from paperleet.tasks.aicb9.agent import TaskWorkspace, ToolRejected
from paperleet.tasks.aicb9.registry import get_task
from paperleet.tasks.aicb9.security import task_subprocess_env
from scripts import aicb9 as legacy_cli


def test_subprocess_environment_drops_secrets_and_inherited_pythonpath():
    source = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONPATH": "/private/untrusted/modules",
        "HOME": "/home/user",
        "AICB9_API_KEY": "secret-aicb9",
        "DEEPSEEK_API_KEY": "secret-deepseek",
        "OPENAI_API_KEY": "secret-openai",
        "ANTHROPIC_API_KEY": "secret-anthropic",
        "AWS_SECRET_ACCESS_KEY": "secret-aws",
        "GH_TOKEN": "secret-github",
        "DATABASE_URL": "postgres://example.invalid/secret",
        "GITHUB_TOKEN": "secret-token",
    }
    sanitized = task_subprocess_env(source=source)
    assert sanitized["PATH"] == source["PATH"]
    assert sanitized["LANG"] == source["LANG"]
    assert sanitized["PYTHONNOUSERSITE"] == "1"
    assert sanitized["PYTHONDONTWRITEBYTECODE"] == "1"
    for key in ("PYTHONPATH", "HOME", "AICB9_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", "GH_TOKEN",
                "DATABASE_URL", "GITHUB_TOKEN"):
        assert key not in sanitized
    assert "secret" not in repr(sanitized)


def test_mutation_environment_uses_only_controlled_pythonpath(monkeypatch, tmp_path):
    variant = tmp_path / "variant"
    variant.mkdir()
    submitted_test = tmp_path / "test_submitted.py"
    submitted_test.write_text("def test_example(): assert True\n", encoding="utf-8")
    seen = {}

    class Process:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args, **kwargs):
        seen["env"] = kwargs["env"]
        return Process()

    monkeypatch.setenv("AICB9_API_KEY", "private-api-key")
    monkeypatch.setenv("PYTHONPATH", "/private/path")
    monkeypatch.setattr(mutation.subprocess, "run", fake_run)

    mutation._run_variant(submitted_test, variant, timeout=2)
    assert seen["env"]["PYTHONPATH"] == str(variant)
    assert "AICB9_API_KEY" not in seen["env"]
    assert "/private/path" not in repr(seen["env"])


def test_c01_public_tests_use_filtered_environment(monkeypatch, tmp_path):
    (tmp_path / "tests" / "public").mkdir(parents=True)
    observed = {}

    class Process:
        returncode = 0
        stdout = "1 passed\n"
        stderr = ""

    def fake_run(*args, **kwargs):
        observed["env"] = kwargs["env"]
        return Process()

    monkeypatch.setenv("AICB9_API_KEY", "api-token")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    monkeypatch.setenv("HOME", "/home/secret-owner")
    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    result = TaskWorkspace(tmp_path).run_public_tests()
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert "AICB9_API_KEY" not in observed["env"]
    assert "OPENAI_API_KEY" not in observed["env"]
    assert "HOME" not in observed["env"]


def test_task_workspace_protects_credential_paths_and_symlinks(tmp_path):
    for path in (".env.production", ".ssh/id_rsa", ".aws/credentials", ".npmrc"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("secret", encoding="utf-8")
    workspace = TaskWorkspace(tmp_path)
    for path in (".env.production", ".ssh/id_rsa", ".aws/credentials", ".npmrc"):
        with pytest.raises(ToolRejected, match="protected"):
            workspace.read_file(path)
        assert path not in workspace.list_files("**/*")

    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (tmp_path / "external-link.py").symlink_to(outside)
    assert "external-link.py" not in workspace.list_files("**/*")
    with pytest.raises(ToolRejected, match="symbolic links"):
        workspace.read_file("external-link.py")


def test_b03_mutants_are_explicitly_public_development_assets():
    task = get_task("B03")
    assert task["mutation_assets"]["visibility"] == "public_development"
    assert task["mutation_assets"]["public_fixture_count"] == 6
    assert task["mutation_assets"]["official_hidden_status"] == "not_implemented"


def test_local_code_execution_warning_is_visible_in_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        legacy_cli.main(["mutate", "--help"])
    assert exc.value.code == 0
    assert "TRUSTED CODE ONLY" in capsys.readouterr().out
