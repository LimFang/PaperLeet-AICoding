import json
from pathlib import Path

from paperleet.tasks.aicb9.evaluators import evaluate_a01, evaluate_b01
from paperleet.tasks.aicb9.registry import task_root, load_registry, get_task


def test_registry_loads_four_pilot_tasks():
    tasks = load_registry()
    assert [task["id"] for task in tasks] == ["A01", "B01", "B03", "C01"]
    assert get_task("C01")["api_required"] is True


def test_a01_reference_trace_scores_full_marks():
    answer = json.loads((task_root() / "A01" / "reference_trace.json").read_text())
    report = evaluate_a01(answer)
    assert report["score"] == 100
    assert report["passed"]


def test_a01_missing_result_does_not_match_explicit_null():
    report = evaluate_a01({"steps": [{"step": 1}]})
    assert report["score"] == 0


def test_b01_reference_diagnosis_scores_full_marks():
    answer = {
        "root_cause_id": "round_unit_price_before_quantity",
        "primary_file": "src/ministore/pricing.py",
        "affected_function": "calculate_total",
        "causal_order": ["multiply_unit_price_by_quantity", "apply_discount", "round_line_subtotal", "calculate_tax"],
        "evidence_ids": ["pricing.calculate_total", "pricing.unit_rounding"],
        "excluded_hypotheses": ["tax_rate_is_primary_cause"],
    }
    report = evaluate_b01(answer)
    assert report["score"] == 100
    assert report["passed"]


def test_wrong_b01_root_cause_loses_points():
    answer = {"root_cause_id": "tax_rate", "primary_file": "src/ministore/pricing.py",
              "affected_function": "calculate_total", "causal_order": [], "evidence_ids": [],
              "excluded_hypotheses": []}
    report = evaluate_b01(answer)
    assert report["score"] < 70


def test_a01_fixture_matches_published_reference_trace():
    import importlib.util
    fixture = task_root() / "fixtures" / "tinycache" / "repository" / "tinycache" / "cache.py"
    spec = importlib.util.spec_from_file_location("aicb9_tinycache", fixture)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = module.TinyCache(capacity=2, ttl=5)
    operations = [
        ("set", "a", 1, 0), ("set", "b", 2, 1), ("get", "a", None, 2),
        ("set", "c", 3, 3), ("get", "b", None, 4), ("get", "a", None, 5),
    ]
    actual = []
    for index, (kind, key, value, now) in enumerate(operations, 1):
        result = cache.set(key, value, now) if kind == "set" else cache.get(key, now)
        actual.append({"step": index, "result": result, "lru": cache.lru_order(),
                       "expired": cache.last_expired, "evicted": cache.last_evicted})
    expected = json.loads((task_root() / "A01" / "reference_trace.json").read_text())["steps"]
    assert actual == expected


def test_b01_fixture_exhibits_the_documented_rounding_bug():
    import importlib.util
    from decimal import Decimal
    fixture = task_root() / "fixtures" / "ministore" / "b01" / "repository" / "src" / "ministore" / "pricing.py"
    spec = importlib.util.spec_from_file_location("aicb9_buggy_pricing", fixture)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.calculate_total([{"unit_price": "19.95", "quantity": 3}], "0.10", "0.00")
    assert result["subtotal"] == Decimal("53.88")
    assert result["subtotal"] != Decimal("53.87")
