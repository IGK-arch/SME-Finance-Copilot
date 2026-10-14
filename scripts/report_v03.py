"""Write docs/ACCEPTANCE_MATRIX_V03.md from recorded artifacts only (runs no tests)."""

from __future__ import annotations

import json
from pathlib import Path

STATUS_TEXT = {
    "PASSED": "PASSED",
    "PARTIAL": "PARTIAL",
    "DEFERRED_MODEL": "DEFERRED (target model)",
    "NOT_RUN": "NOT_RUN",
    "EVIDENCE_RECORDED": "EVIDENCE_RECORDED",
    "FAILED": "FAILED",
    "SKIPPED": "SKIPPED",
}


def main() -> None:
    regression = json.loads(Path("artifacts/v03/regression-v03.json").read_text(encoding="utf-8"))
    e2e_path = Path("artifacts/v03/e2e-latest.json")
    e2e = json.loads(e2e_path.read_text(encoding="utf-8")) if e2e_path.exists() else None
    browser_path = Path("artifacts/v03/browser-v03.json")
    browser = (
        json.loads(browser_path.read_text(encoding="utf-8")) if browser_path.exists() else None
    )
    lines = [
        "# Acceptance matrix v0.3 — V03-01…V03-25",
        "",
        f"Generated from `artifacts/v03/regression-v03.json` (started {regression['started_at']}, "
        f"{regression['tests_run']} tests: {regression['test_counts']}).",
        "IDs and wording come from the v0.3 audit package; T001–T100 remain in ACCEPTANCE_MATRIX.md "
        f"(current counts {regression['acceptance_counts']}).",
        "DEFERRED (target model) items are model-dependent and are not counted as passed from MOCK runs.",
        "",
        "| ID | Priority | Requirement | Status | Evidence | Note |",
        "|---|---|---|---|---|---|",
    ]
    for case in regression.get("v03_acceptance", []):
        evidence = [t.split(".")[-1] for t in case["tests"]] + case["evidence"]
        lines.append(
            f"| {case['id']} | {case['priority']} | {case['requirement']} | "
            f"{STATUS_TEXT.get(case['status'], case['status'])} | {'<br>'.join(evidence) or '—'} | "
            f"{(case.get('note') or '').replace('|', '/')} |"
        )
    lines += ["", f"Counts: {regression.get('v03_counts')}", ""]
    if e2e:
        lines += [
            "## Product-path E2E (`python -m scripts.e2e_v03`)",
            "",
            f"Scope: {e2e['scope']}. Passed: **{e2e['passed']}**. Workspace `{e2e['workspace']}`.",
            "",
            "| Check | Result |",
            "|---|---|",
            *[f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in e2e["checks"].items()],
            "",
            "Not covered: " + "; ".join(e2e["not_covered"]) + ".",
            "",
        ]
    if browser:
        lines += [
            "## Browser walkthrough (built-in browser pane, real backend)",
            "",
            f"Scope: {browser['scope']}",
            "",
            *[f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in browser["checks"].items()],
            "",
            "Screenshots: " + ", ".join(browser["screenshots"]),
            "",
        ]
    Path("docs/ACCEPTANCE_MATRIX_V03.md").write_text("\n".join(lines), encoding="utf-8")
    print("docs/ACCEPTANCE_MATRIX_V03.md written")


if __name__ == "__main__":
    main()
