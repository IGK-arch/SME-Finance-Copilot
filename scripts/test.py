"""Run tests and derive acceptance status ONLY from actual unittest outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
import traceback
import unittest
from collections import Counter
from pathlib import Path
from typing import Any, cast

from finance.domain import now

UNIMPLEMENTED = {
    "T023": "No trained survival dataset/model in this milestone",
    "T031": "No training/temporal-validation pipeline; observed cutoff is covered by T016",
    "T032": "No training/company-holdout pipeline or downloaded dataset",
    "T097": "Observation capability is scoped but private files are not OS/container isolated from local administrators",
}


def v03_status(records: list[dict]) -> list[dict]:
    """Owner main-path matrix (V03-*). Model-dependent items stay DEFERRED_MODEL."""
    path = Path("checklists/v03_acceptance.json")
    if not path.exists():
        return []
    e2e_path = Path("artifacts/v03/e2e-latest.json")
    e2e = json.loads(e2e_path.read_text(encoding="utf-8")) if e2e_path.exists() else None
    output = []
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
        matched = [r for r in records if case["id"] in r["acceptance_ids"]]
        statuses = {r["status"] for r in matched}
        evidence = [e for e in case.get("evidence", []) if Path(e).exists()]
        if "e2e" in case["verification"] and e2e is not None:
            evidence.append(
                "artifacts/v03/e2e-latest.json"
                + (" (passed)" if e2e.get("passed") else " (FAILED)")
            )
            if not e2e.get("passed"):
                statuses.add("FAILED")
        if "FAILED" in statuses:
            status = "FAILED"
        elif case.get("deferred"):
            status = "DEFERRED_MODEL"
        elif case.get("not_started") and not matched:
            status = "NOT_RUN"
        elif "SKIPPED" in statuses:
            status = "SKIPPED"
        elif matched and (case.get("partial") or case.get("open")):
            status = "PARTIAL"
        elif matched:
            status = "PASSED"
        elif evidence:
            status = "PARTIAL" if (case.get("partial") or case.get("open")) else "EVIDENCE_RECORDED"
        else:
            status = "NOT_RUN"
        output.append(
            {
                "id": case["id"],
                "priority": case["priority"],
                "requirement": case["requirement"],
                "status": status,
                "tests": [r["test_id"] for r in matched],
                "evidence": evidence,
                "note": case.get("partial") or case.get("open"),
            }
        )
    return output


def acceptance_status(records: list[dict], cases: list[dict]) -> list[dict]:
    output = []
    for case in cases:
        identifier = case["id"]
        matched = [r for r in records if identifier in r["acceptance_ids"]]
        if identifier in UNIMPLEMENTED:
            status, reason = "NOT_RUN", UNIMPLEMENTED[identifier]
        elif not matched:
            status, reason = "NOT_RUN", "No executable acceptance implementation"
        else:
            statuses = {r["status"] for r in matched}
            status = (
                "FAILED"
                if "FAILED" in statuses
                else "SKIPPED"
                if "SKIPPED" in statuses
                else "PASSED"
            )
            reason = None
        output.append(
            {
                "id": identifier,
                "requirement": case["requirement"],
                "status": status,
                "tests": [r["test_id"] for r in matched],
                "reason": reason,
                "scope": "Synthetic local milestone; see docs/KNOWN_LIMITATIONS.md",
            }
        )
    return output


class RecordedResult(unittest.TextTestResult):
    def __init__(self, stream: Any, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.records: list[dict] = []
        self.started: dict[str, float] = {}

    def startTest(self, test: unittest.TestCase) -> None:
        self.started[test.id()] = time.perf_counter()
        super().startTest(test)

    def record(self, test: unittest.TestCase, status: str, reason: str | None = None) -> None:
        self.records.append(
            {
                "test_id": test.id(),
                "acceptance_ids": re.findall(r"T\d{3}", test.id())
                + ["V03-" + n for n in re.findall(r"V03_(\d{2})", test.id())],
                "status": status,
                "elapsed_seconds": time.perf_counter()
                - self.started.get(test.id(), time.perf_counter()),
                "reason": reason,
            }
        )

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self.record(test, "PASSED")

    def addFailure(self, test: unittest.TestCase, err: tuple) -> None:
        super().addFailure(test, err)
        self.record(test, "FAILED", "".join(traceback.format_exception(*err)))

    def addError(self, test: unittest.TestCase, err: tuple) -> None:
        super().addError(test, err)
        self.record(test, "FAILED", "".join(traceback.format_exception(*err)))

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.record(test, "SKIPPED", reason)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--output", default="artifacts/test-results.json")
    args = parser.parse_args()
    start = now()
    suite = unittest.defaultTestLoader.discover("tests", pattern=args.pattern, top_level_dir=".")
    result = cast(
        RecordedResult, unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    )
    cases = json.loads(Path("checklists/acceptance_cases.json").read_text(encoding="utf-8"))[
        "cases"
    ]
    supplemental = []
    # Recorded browser evidence counts only while it matches the current web files.
    for browser_path in (
        Path("artifacts/browser-smoke.json"),
        Path("artifacts/v03/browser-v03.json"),
    ):
        if not browser_path.exists():
            continue
        browser = json.loads(browser_path.read_text(encoding="utf-8"))
        hashes_match = bool(browser.get("webHashes")) and all(
            (Path("web") / name).is_file()
            and hashlib.sha256((Path("web") / name).read_bytes()).hexdigest() == hashed
            for name, hashed in browser.get("webHashes", {}).items()
        )
        screenshots_exist = all(
            (Path("artifacts") / name).is_file() for name in browser.get("screenshots", [])
        )
        if (
            hashes_match
            and screenshots_exist
            and browser.get("checks")
            and all(browser["checks"].values())
        ):
            supplemental.append(browser)
    acceptance = acceptance_status(result.records + supplemental, cases)
    report = {
        "schema_version": 1,
        "started_at": start,
        "finished_at": now(),
        "command": "python -m scripts.test --pattern " + args.pattern,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tests_run": result.testsRun,
        "test_counts": dict(Counter(r["status"] for r in result.records)),
        "acceptance_counts": dict(Counter(c["status"] for c in acceptance)),
        "actual_tests": result.records,
        "supplemental_checks": supplemental,
        "acceptance": acceptance,
        "v03_acceptance": (v03 := v03_status(result.records + supplemental)),
        "v03_counts": dict(Counter(c["status"] for c in v03)),
        "live_model_metrics": {
            "status": "NOT_RUN",
            "value": None,
            "reason": "No authorized live model",
        },
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(destination.resolve()),
                "tests": report["test_counts"],
                "acceptance": report["acceptance_counts"],
                "v03": report["v03_counts"],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
