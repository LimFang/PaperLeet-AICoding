"""Record pytest outcomes for a single local B03 variant."""

import json
from pathlib import Path
import sys

import pytest


class Outcomes:
    def __init__(self):
        self.tests = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if self.tests.get(item.nodeid) == "error":
            return
        if report.failed:
            assertion_failure = (
                report.when == "call"
                and call.excinfo is not None
                and isinstance(call.excinfo.value, (AssertionError, pytest.fail.Exception))
            )
            self.tests[item.nodeid] = "failed" if assertion_failure else "error"
        elif report.skipped:
            self.tests[item.nodeid] = "skipped"
        elif report.when == "call":
            self.tests[item.nodeid] = "passed"


if __name__ == "__main__":
    test_file, report_file = sys.argv[1:]
    outcomes = Outcomes()
    exit_code = pytest.main(
        ["-q", "--noconftest", "--import-mode=importlib", test_file],
        plugins=[outcomes],
    )
    Path(report_file).write_text(json.dumps(outcomes.tests), encoding="utf-8")
    raise SystemExit(exit_code)
