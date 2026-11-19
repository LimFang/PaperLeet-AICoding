"""Local mutation evaluator for B03 student-authored pytest suites.

This is a development evaluator, not a secure hosted judge. Run only trusted tests
locally; production evaluation must execute inside a hardened OS-level sandbox.
"""
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .registry import task_root


def _run_variant(test_file, variant_root, timeout):
    report_file = variant_root / "outcomes.json"
    report_file.unlink(missing_ok=True)
    runner = Path(__file__).with_name("_pytest_outcomes.py")
    command = [sys.executable, str(runner), str(test_file), str(report_file)]
    env = {**os.environ, "PYTHONPATH": str(variant_root)}
    try:
        proc = subprocess.run(
            command, cwd=variant_root, env=env, text=True, capture_output=True, timeout=timeout
        )
        returncode = proc.returncode
        output = (proc.stdout + proc.stderr)[-12000:]
        outcomes = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    except subprocess.TimeoutExpired:
        returncode = 124
        output = "pytest timed out"
        outcomes = {}

    counts = Counter(outcomes.values())
    passed = returncode == 0 and counts["passed"] > 0 and counts["error"] == 0
    killed = returncode == 1 and counts["failed"] > 0 and counts["error"] == 0
    return {
        "valid": passed or killed,
        "passed": passed,
        "killed": killed,
        "summary": {"passed": counts["passed"], "failed": counts["failed"], "errors": counts["error"]},
        "output": output,
    }, outcomes


def run_mutation_suite(test_file, timeout_seconds=8):
    """Run one submitted test file against the reference and six mutants."""
    test_file = Path(test_file).resolve()
    if not test_file.is_file():
        raise FileNotFoundError(test_file)
    fixture = task_root() / "fixtures" / "ministore" / "b03"
    mutants = [path for path in sorted((fixture / "mutants").iterdir()) if path.is_dir()]
    mutant_names = [path.name for path in mutants]
    with tempfile.TemporaryDirectory(prefix="aicb9-b03-") as temp:
        base = Path(temp)
        reference_root = base / "reference"
        replay_root = base / "reference-replay"
        for directory in (reference_root, replay_root):
            shutil.copytree(fixture / "reference" / "ministore", directory / "ministore")
        first, first_outcomes = _run_variant(test_file, reference_root, timeout_seconds)
        replay, replay_outcomes = _run_variant(test_file, replay_root, timeout_seconds)
        valid_reference = first["passed"] and replay["passed"]
        deterministic = valid_reference and first_outcomes == replay_outcomes
        reference = first if replay["passed"] else replay
        results = {
            "reference": {
                "valid": valid_reference,
                "passed": valid_reference,
                "deterministic": deterministic,
                "summary": reference["summary"],
                "output": reference["output"],
            }
        }
        for mutant in mutants:
            if not valid_reference:
                results[mutant.name] = {
                    "valid": False, "passed": False, "killed": False, "reason": "reference_failed"
                }
                continue
            variant_root = base / mutant.name
            shutil.copytree(mutant / "ministore", variant_root / "ministore")
            results[mutant.name], _ = _run_variant(test_file, variant_root, timeout_seconds)

    killed_mutants = [name for name in mutant_names if results[name]["killed"]]
    killed = len(killed_mutants)
    valid_mutants = all(results[name]["valid"] for name in mutant_names)
    valid_suite = valid_reference and valid_mutants and len(mutant_names) == 6
    breakdown = {
        "reference_pass": 20 if valid_reference else 0,
        "mutants_killed": round(60 * killed / 6, 2),
        "determinism": 10 if deterministic else 0,
        "suite_integrity": 10 if valid_suite else 0,
    }
    return {
        "task_id": "B03", "score": round(sum(breakdown.values()), 2), "max_score": 100,
        "passed": valid_suite and killed == 6 and deterministic,
        "breakdown": breakdown,
        "mutation_score": round(killed / 6, 4),
        "killed_mutants": killed_mutants,
        "survived_mutants": [name for name in mutant_names if results[name]["passed"]],
        "results": results,
        "security_note": "Local trusted-code evaluator only; use an OS-level sandbox for untrusted submissions.",
    }
