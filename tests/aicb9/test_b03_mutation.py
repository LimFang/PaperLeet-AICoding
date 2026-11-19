from pathlib import Path
from paperleet.tasks.aicb9.mutation import run_mutation_suite


def test_reference_contract_suite_passes_and_kills_all_mutants():
    test_file = Path(__file__).parent / "submissions" / "b03_reference_contract.py"
    report = run_mutation_suite(test_file)
    assert report["score"] == 100, report
    assert report["passed"], report
    assert len(report["killed_mutants"]) == 6


def test_non_assertion_failure_does_not_kill_a_mutant(tmp_path):
    test_file = tmp_path / "test_unexpected_error.py"
    test_file.write_text(
        "from ministore.pagination import list_orders\n"
        "def test_first_page():\n"
        "    page = list_orders([{'id': 'a', 'created_at': 1}], 1)\n"
        "    if page['next_cursor'] is not None:\n"
        "        raise RuntimeError('unexpected cursor')\n",
        encoding="utf-8",
    )
    report = run_mutation_suite(test_file)
    mutant = report["results"]["m3_has_more_greater_equal"]
    assert report["results"]["reference"]["passed"]
    assert mutant["summary"]["errors"] == 1
    assert report["killed_mutants"] == []
