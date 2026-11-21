"""Regression and adversarial validation for the versioned AICB-9 registry."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from paperleet.tasks.aicb9.registry import get_task, load_registry, task_root
from scripts import aicb9 as cli


@pytest.fixture
def schema_root(tmp_path):
    """Minimal complete v2 registry so metadata errors fail in isolation."""
    base = tmp_path / "aicb9"
    (base / "A01").mkdir(parents=True)
    source = task_root()
    for name in ("statement.md", "starter_answer.json"):
        (base / "A01" / name).write_text(
            (source / "A01" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (base / "fixtures" / "tinycache" / "repository").mkdir(parents=True)
    task = yaml.safe_load((source / "A01" / "task.yaml").read_text(encoding="utf-8"))
    registry = {
        "version": 1,
        "schema_version": 2,
        "benchmark": "AICB-9",
        "tasks": [{
            "id": "A01",
            "slug": "trace-the-execution",
            "title": "Trace the Execution",
            "category": "code_understanding",
            "api_required": False,
        }],
    }
    write_specs(base, registry, task)
    return base


def write_specs(base, registry, task):
    (base / "registry.yaml").write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (base / "A01" / "task.yaml").write_text(
        yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def change_task(base, update):
    registry = yaml.safe_load((base / "registry.yaml").read_text(encoding="utf-8"))
    task = yaml.safe_load((base / "A01" / "task.yaml").read_text(encoding="utf-8"))
    update(registry, task)
    write_specs(base, registry, task)


def test_v2_registry_has_four_current_tasks_with_explicit_status():
    tasks = load_registry()
    assert [task["id"] for task in tasks] == ["A01", "B01", "B03", "C01"]
    assert all(task["task_version"] == "1.0.0" for task in tasks)
    assert {task["id"]: task["rubric_version"] for task in tasks} == {
        "A01": "1.0.0",
        "B01": "1.1.0",
        "B03": "1.0.0",
        "C01": "1.1.0",
    }
    assert all(task["schema_version"] == 2 for task in tasks)
    assert {task["id"]: task["strategies"]["supported"] for task in tasks} == {
        "A01": ["S0", "S1", "S2"],
        "B01": ["S0", "S1", "S2"],
        "B03": [],
        "C01": ["S3"],
    }
    assert get_task(301)["id"] == "C01"
    assert get_task("repository-bug-fix")["id"] == "C01"
    assert tasks[2]["evaluation"]["private"]["status"] == "not_implemented"
    assert tasks[3]["evaluation"]["private"]["status"] == "not_implemented"
    assert tasks[3]["budget_limits"]["max_tool_calls"] == 24


def test_valid_v2_metadata(schema_root):
    task = load_registry(schema_root)[0]
    assert task["cli"]["command"] == "evaluate"
    assert task["fixture"]["digest"].startswith("git-tree-sha1:")
    assert task["directory"] == schema_root / "A01"


@pytest.mark.parametrize("case,expected", [
    ("duplicate_id", "Duplicate AICB-9 task id"),
    ("missing_spec", "Missing task specification"),
    ("id_mismatch", "Task id mismatch"),
    ("slug_mismatch", "Registry slug mismatch"),
    ("api_mismatch", "Registry API requirement mismatch"),
    ("invalid_semver", "semantic version"),
    ("invalid_strategy", "list of S0-S3"),
    ("duplicate_strategy", "contains duplicates"),
    ("strategy_overlap", "supported/planned overlap"),
    ("negative_budget", "positive integer"),
    ("boolean_budget", "positive integer"),
    ("invalid_timeout", "positive finite number"),
    ("bad_private_status", "status is invalid"),
    ("missing_contract", "not found"),
    ("escaping_contract", "escapes the task root"),
    ("bad_digest", "content-addressed tree SHA"),
    ("invalid_handler", "AICB-9 evaluator"),
    ("non_bool_api", "api_required must be boolean"),
    ("invalid_scoring", "weights must sum to 100"),
])
def test_v2_metadata_rejects_invalid_inputs(schema_root, case, expected):
    def modify(registry, task):
        if case == "duplicate_id":
            registry["tasks"].append(copy.deepcopy(registry["tasks"][0]))
        elif case == "missing_spec":
            registry["tasks"][0]["id"] = "Z99"
        elif case == "id_mismatch":
            task["id"] = "Z99"
        elif case == "slug_mismatch":
            registry["tasks"][0]["slug"] = "some-other-task"
        elif case == "api_mismatch":
            registry["tasks"][0]["api_required"] = True
        elif case == "invalid_semver":
            task["task_version"] = "v1"
        elif case == "invalid_strategy":
            task["strategies"]["planned"].append("S4")
        elif case == "duplicate_strategy":
            task["strategies"]["supported"].append("S0")
        elif case == "strategy_overlap":
            task["strategies"]["planned"].append("S0")
        elif case == "negative_budget":
            task["runtime"]["max_tool_calls"] = -1
        elif case == "boolean_budget":
            task["runtime"]["max_tool_calls"] = True
        elif case == "invalid_timeout":
            task["runtime"]["timeout_seconds"] = 0
        elif case == "bad_private_status":
            task["evaluation"]["private"]["status"] = "ready"
        elif case == "missing_contract":
            task["interfaces"]["input"] = "A01/missing.md"
        elif case == "escaping_contract":
            task["interfaces"]["output"] = "../private.json"
        elif case == "bad_digest":
            task["fixture"]["digest"] = "sha256:invalid"
        elif case == "invalid_handler":
            task["cli"]["handler"] = "os:system"
        elif case == "non_bool_api":
            task["api_required"] = "false"
        elif case == "invalid_scoring":
            task["scoring"]["result"] = 41
        else:
            raise AssertionError(case)

    change_task(schema_root, modify)
    with pytest.raises(ValueError, match=expected):
        load_registry(schema_root)


def test_v1_legacy_registry_is_still_readable(schema_root):
    def legacy(registry, task):
        registry.pop("schema_version")
        for field in ("task_version", "rubric_version", "cli", "interfaces",
                      "strategies", "fixture", "evaluation"):
            task.pop(field)
    change_task(schema_root, legacy)
    task = load_registry(schema_root)[0]
    assert task["id"] == "A01"
    assert task["task_version"] == "0.0.0"
    assert task["strategies"] == {"supported": [], "planned": []}


def test_cli_choices_and_dispatch_use_registry(monkeypatch, capsys):
    reference_path = task_root() / "A01" / "reference_trace.json"
    task = copy.deepcopy(get_task("A01"))
    task["id"] = "Z01"
    monkeypatch.setattr(cli, "load_registry", lambda: [task])
    assert cli.main(["evaluate", "Z01", "--answer", str(reference_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed"]
    with pytest.raises(SystemExit) as exc:
        cli.main(["evaluate", "A01", "--answer", str(reference_path)])
    assert exc.value.code == 2


def test_cli_task_limits_read_task_execution_settings():
    from argparse import Namespace
    task = get_task("C01")
    args = Namespace(max_tool_calls=None, max_input_tokens=None,
                     max_output_tokens=None, max_wall_seconds=None)
    assert cli._task_limits(task, args)["max_tool_calls"] == 24
    args.max_tool_calls = 3
    assert cli._task_limits(task, args)["max_tool_calls"] == 3
