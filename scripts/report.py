"""Build reports from actual test/demo/quality artifacts, never estimates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from finance.domain import now
from scripts.browser_evidence import load as load_browser
from scripts.test import acceptance_status

INVARIANT_MAP = {
    "I01": ("ingestion.snapshot", ["T021"]),
    "I02": ("compute.obligation_flows / ingestion.snapshot", ["T021", "T024", "T025"]),
    "I03": ("contingency.request_extension / observe_decisions", ["T043", "T051"]),
    "I04": ("store.objects / ingestion.snapshot", ["T044"]),
    "I05": ("execution.deliver / refresh", ["T080", "T082", "T095"]),
    "I06": ("ingestion.import_csv / store.add_fact", ["T002", "T020"]),
    "I07": ("execution.prepare / sandbox.World.submit", ["T074", "T075", "T078"]),
    "I08": ("store.authorize / execution._approval_checks", ["T071", "T072"]),
    "I09": ("execution.prepare / BEGIN IMMEDIATE", ["T076"]),
    "I10": ("execution.deliver / refresh", ["T079", "T080", "T081"]),
    "I11": ("domain.Money / ingestion.parse_row", ["T014"]),
    "I12": ("domain.minor / rate_charge", ["T014", "T015"]),
    "I13": ("ingestion.allocate / snapshot", ["T007", "T025"]),
    "I14": ("ingestion.allocate_in_transaction", ["T008", "T009"]),
    "I15": ("ingestion.snapshot / execution.refresh", ["T010", "T011", "T090"]),
    "I16": ("compute.merchant_bridge", ["T013"]),
    "I17": ("compute.factoring_flows / obligation_flows", ["T041"]),
    "I18": ("compute.forecast residual de-duplication", ["T022"]),
    "I19": ("store.facts / objects", ["T016", "T017"]),
    "I20": ("store.facts cutoff / forecast", ["T016", "T031"]),
    "I21": ("compute.trajectory / validation.validate_plan", ["T027"]),
    "I22": ("compute.financing / forecast", ["T028", "T040"]),
    "I23": ("planner.solve / validation.validate_plan", ["T045", "T046"]),
    "I24": ("sandbox capability interface / future OS isolation", ["T097"]),
    "I25": ("planner.solve statuses / tests.test_planner", ["T047", "T048"]),
    "I26": ("compute.forecast provenance labels", ["T029", "T030"]),
    "I27": ("execution.approve / _approval_checks", ["T059", "T073"]),
    "I28": ("store.authorize / evidence / API / cache", ["T004", "T060", "T061", "T062", "T097"]),
    "I29": ("agents.ToolRegistry / server policy", ["T056", "T057", "T058"]),
    "I30": ("execution.prepare / worker / LangGraph resume", ["T077", "T078", "T086"]),
    "I31": ("immutable ledger / execution.cancel_plan", ["T087", "T089"]),
    "I32": ("agents.ModelGateway / execution.approve", ["T066"]),
    "I33": ("compute.financing / immutable DEMO terms", ["T042"]),
    "I34": ("scripts.test / benchmark / report", ["T098", "T099"]),
    "I35": ("docs/data_cards / source manifest", ["T100"]),
    "I36": ("execution.refresh / deliver funds recheck", ["T090", "T092"]),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", type=Path, default=Path("artifacts/test-results.json"))
    args = parser.parse_args()
    path = args.tests
    if not path.is_file():
        raise SystemExit("No actual test report. Run python -m scripts.test first.")
    tests = json.loads(path.read_text(encoding="utf-8"))
    browser = load_browser()
    # Refresh the derived matrix from actual recorded runs without pretending to
    # rerun unittest or altering its timestamp/results artifact.
    acceptance = acceptance_status(tests["actual_tests"] + browser, tests["acceptance"])
    cases = {c["id"]: c for c in acceptance}
    invariants = json.loads(Path("checklists/invariants.json").read_text(encoding="utf-8"))[
        "invariants"
    ]
    trace = []
    for invariant in invariants:
        function, identifiers = INVARIANT_MAP[invariant["id"]]
        statuses = [cases[identifier]["status"] for identifier in identifiers]
        status = "VERIFIED" if all(s == "PASSED" for s in statuses) else "PARTIAL"
        trace.append(
            invariant
            | {
                "responsible_function": function,
                "acceptance_ids": identifiers,
                "status": status,
                "evidence": path.as_posix(),
                "limitations": "docs/KNOWN_LIMITATIONS.md",
            }
        )
    Path("docs/traceability.json").write_text(
        json.dumps({"at": now(), "invariants": trace}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Actual local product results",
        "",
        f"Generated from real artifacts at {now()}.",
        "",
        f"Unittest checks: {tests['tests_run']}; outcomes: {tests['test_counts']}.",
        f"Acceptance targets, including current recorded browser evidence: {dict(Counter(c['status'] for c in acceptance))}.",
        f"Supplemental browser records verified against web hashes: {len(browser)}.",
        "",
        "These are synthetic/local checks, not real-agent or Chinese-SME quality metrics.",
        "",
    ]
    golden = Path("artifacts/golden-latest.json")
    if golden.exists():
        evidence = json.loads(golden.read_text(encoding="utf-8"))
        lines += [
            "Independent golden world result:",
            "",
            f"```json\n{json.dumps(evidence['independent_evaluation'], indent=2)}\n```",
            "",
            f"Reconciliation: {evidence['reconciliation']['status']}; discrepancy_minor={evidence['reconciliation']['discrepancy_minor']}.",
            "",
        ]
    quality = Path("artifacts/quality-results.json")
    if quality.exists():
        lines += ["Quality commands actually run:", ""]
        for check in json.loads(quality.read_text(encoding="utf-8"))["checks"]:
            lines.append(f"- `{' '.join(check['command'])}` — {check['status']}")
        lines.append("")
    lines += [
        "Live local-model evidence is recorded separately in docs/model_cards/local-gateway.md; it is not counted as a unittest or production-quality metric. B1/B2/B3 ablations: **NOT_RUN**.",
        "Production banking, real data, legal/competition refresh, external CI and release tag: **NOT_RUN**.",
        "",
        "See KNOWN_LIMITATIONS.md, SECURITY.md, ITERATIONS.md and the full machine report.",
        "",
        "| Target | Actual status | Executed implementation / reason |",
        "|---|---|---|",
    ]
    for case in acceptance:
        explanation = ", ".join(case["tests"]) or case["reason"]
        lines.append(f"| {case['id']} | {case['status']} | {explanation} |")
    Path("docs/RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    catalog = json.loads(Path("docs/implementation_catalog.json").read_text(encoding="utf-8"))[
        "tasks"
    ]
    backlog = json.loads(Path("checklists/backlog.json").read_text(encoding="utf-8"))["tasks"]
    matrix = [
        "# Acceptance matrix — original I01–I36, T001–T100, W01–W36",
        "",
        f"Generated {now()} from actual {path.as_posix()} and hash-checked browser-smoke.json.",
        "VERIFIED means demonstrated within the stated synthetic local scope. It is not full production acceptance.",
        "PARTIAL means a requirement has remaining work; MISSING/IMPLEMENTED_UNVERIFIED/BLOCKED are never counted as verified.",
        "Source checklist text remains unchanged. Detailed test outcomes (PASSED/FAILED/SKIPPED/NOT_RUN) are retained below.",
        "",
        "| ID | Original requirement | Status | Code / actual verification |",
        "|---|---|---|---|",
    ]
    for invariant in trace:
        matrix.append(
            f"| {invariant['id']} | {invariant['requirement']} | {invariant['status']} | {invariant['responsible_function']}; {', '.join(invariant['acceptance_ids'])}; {path.as_posix()} |"
        )
    for c in acceptance:
        status = (
            "VERIFIED"
            if c["status"] == "PASSED"
            else "MISSING"
            if c["status"] == "NOT_RUN"
            else "PARTIAL"
        )
        evidence = "; ".join(c["tests"]) or c["reason"]
        matrix.append(f"| {c['id']} | {c['requirement']} | {status} ({c['status']}) | {evidence} |")
    tasks = {t["id"]: t for t in catalog}
    for original in backlog:
        t = tasks[original["id"]]
        matrix.append(
            f"| {t['id']} | {original['task']} | {t['status']} | {t['code']}; {t['result']} |"
        )
    matrix += [
        "",
        "Live provider/novel-task evidence and its limits: docs/model_cards/local-gateway.md. Connectivity, structural task outcomes and narrative quality are separate claims.",
        "Full private-truth OS isolation: MISSING. Full-product overall gate: PARTIAL. See KNOWN_LIMITATIONS.md.",
        "",
    ]
    Path("docs/ACCEPTANCE_MATRIX.md").write_text("\n".join(matrix), encoding="utf-8")
    progress = [
        "# Current W01–W36 implementation assessment",
        "",
        f"Actual test evidence: {path.as_posix()}; browser evidence: artifacts/browser-smoke.json.",
        "",
        "| Task | Status | Code | Result / remaining work |",
        "|---|---|---|---|",
    ]
    progress += [f"| {t['id']} | {t['status']} | {t['code']} | {t['result']} |" for t in catalog]
    Path("docs/BACKLOG_PROGRESS.md").write_text("\n".join(progress) + "\n", encoding="utf-8")
    Path("artifacts/acceptance-current.json").write_text(
        json.dumps(
            {
                "generated_at": now(),
                "unittest_source": str(path),
                "unittest_finished_at": tests["finished_at"],
                "browser_records": browser,
                "cases": acceptance,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Built docs/RESULTS.md and traceability for {len(trace)} invariants from actual tests")


if __name__ == "__main__":
    main()
