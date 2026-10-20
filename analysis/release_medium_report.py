"""Compare frozen current medium120 with current none120 and historical medium100."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from analysis.release_report import read, sha, stats, text, tools
from finance.agent_data import DATASETS
from finance.domain import canonical, now
from finance.workflows import tool_schemas
from scripts.agent_report import safety_checks
from scripts.reasoning_report import measurements

ROOT = Path("artifacts/release-medium-120-20261019")
NONE_ROOT = Path("artifacts/release-eval-20261019")
HISTORICAL = [
    Path("artifacts/strata-reasoning-medium-74-20261017.json"),
    Path("artifacts/strata-reasoning-edge-paired-26-20261017.json"),
]


def current() -> tuple[list[tuple[Path, dict]], list[dict]]:
    parts = sorted(
        [(p, read(p)) for p in ROOT.glob("medium-120-20261019-primary*.json")],
        key=lambda pair: pair[1]["started_at"],
    )
    runs = [r for _, part in parts for r in part["runs"]]
    assert len(runs) == len({r["case_id"] for r in runs}), "Duplicate primary outcome"
    return parts, runs


def record_reviews(notes: dict[str, tuple[str, str]]) -> None:
    _, runs = current()
    by_id = {r["case_id"]: r for r in runs}
    path = ROOT / "narrative-review.json"
    review = (
        read(path)
        if path.exists()
        else {"reviewer": "Coding assistant; not independent accountant", "reviews": []}
    )
    existing = {r["case_id"]: r for r in review["reviews"]}
    for identifier, (status, note) in notes.items():
        assert status in {"COMPLETE", "MINOR_ISSUE", "PARTIAL", "FAILED"}
        assert identifier in by_id and note
        decision = dict(
            case_id=identifier,
            status=status,
            note=note,
            run_sha256=hashlib.sha256(canonical(by_id[identifier]).encode()).hexdigest(),
        )
        assert identifier not in existing or existing[identifier] == decision, (
            "Do not silently replace review"
        )
        existing[identifier] = decision
    review.update(reviews=list(existing.values()), updated_at=now())
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


def paired(rows: list[dict], baseline: dict[str, dict]) -> dict:
    common = [r for r in rows if r["case_id"] in baseline]
    both = [
        r
        for r in common
        if r["grade"]["status"] == baseline[r["case_id"]]["grade"]["status"] == "PASSED"
    ]
    return {
        "paired": len(common),
        "improved": [
            r["case_id"]
            for r in common
            if r["grade"]["status"] == "PASSED"
            and baseline[r["case_id"]]["grade"]["status"] != "PASSED"
        ],
        "regressed": [
            r["case_id"]
            for r in common
            if r["grade"]["status"] != "PASSED"
            and baseline[r["case_id"]]["grade"]["status"] == "PASSED"
        ],
        "both_pass": len(both),
        "median_medium_over_baseline_seconds_both_pass": statistics.median(
            r["elapsed_seconds"] / baseline[r["case_id"]]["elapsed_seconds"] for r in both
        )
        if both
        else None,
    }


def measured(rows: list[dict]) -> dict:
    values = [measurements(r) for r in rows]
    attempts = [a for r in rows for a in r.get("attempts", [])]
    return {
        "calls": len(attempts),
        "requested_efforts": dict(
            Counter(
                a.get("provider_measurement", {}).get("reasoning_effort_requested", "UNRECORDED")
                for a in attempts
            )
        ),
        "reasoning_observed_calls": sum(v["reasoning_observed_calls"] for v in values),
        "completion_tokens_known": sum(v["completion_tokens_known"] for v in values),
        "unmeasured_calls": sum(v["unmeasured_calls"] for v in values),
        "attempt_errors": dict(
            Counter(
                a.get("error", {}).get("code", "UNKNOWN")
                for a in attempts
                if a.get("status") == "FAILED"
            )
        ),
        "scope": "Provider usage and presence flags; hidden reasoning text is neither persisted nor reviewed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    reg = read(ROOT / "preregistration.json")
    before = read(NONE_ROOT / "preregistration-v4.json")
    assert canonical(reg["entries"]) == canonical(before["entries"])
    assert reg["system_hash"] == before["system_hash"] and reg["tools_hash"] == before["tools_hash"]
    assert reg["configuration"]["strata_reasoning_effort"] == "medium"
    delta = {
        k for k in reg["configuration"] if reg["configuration"][k] != before["configuration"][k]
    }
    assert delta == {"think", "strata_reasoning_effort"}
    source_delta = [
        p for p, h in before["source_hashes"].items() if reg["source_hashes"].get(p) != h
    ]
    assert source_delta == ["scripts/release_eval.py"]
    assert all(sha(Path(p)) == h for p, h in reg["source_hashes"].items())
    parts, runs = current()
    assert parts
    cases = {e["case"]["id"]: e["case"] for e in reg["entries"]}
    assert {r["case_id"] for r in runs} <= cases.keys()
    for path, part in parts:
        assert part["configuration"] == reg["configuration"]
        assert part["source_hashes"] == reg["source_hashes"]
        assert part["preregistration_sha256"] == sha(Path(part["preregistration"]))
        assert part["model_identity"] == parts[0][1]["model_identity"]
        assert all(canonical(c) == canonical(cases[c["id"]]) for c in part["cases"])
        assert all(r["reasoning_effort"] == "medium" for r in part["runs"])
    runs.sort(key=lambda r: list(cases).index(r["case_id"]))
    none_paths = [
        NONE_ROOT / n for n in ("primary.json", "primary-resume.json", "primary-resume-2.json")
    ]
    none_parts = [read(p) for p in none_paths]
    none = {r["case_id"]: r for part in none_parts for r in part["runs"]}
    assert len(none) == 120
    assert all(r["reasoning_effort"] == "none" for r in none.values())
    historical_parts = [read(p) for p in HISTORICAL]
    old_cases = {c["id"]: c for part in historical_parts for c in part["cases"]}
    old = {
        r["case_id"]: {**r, "language": old_cases[r["case_id"]]["language"]}
        for part in historical_parts
        for r in part["runs"]
        if r.get("reasoning_effort", "medium") == "medium"
    }
    assert len(old) == 100
    assert historical_parts[0]["configuration"] == reg["configuration"]
    assert historical_parts[1]["configurations"]["medium"] == reg["configuration"]
    assert all(
        canonical(old_cases[e["case"]["id"]]) == canonical(e["case"])
        for e in reg["entries"]
        if e["group"] == "regression100"
    )
    review_path = ROOT / "narrative-review.json"
    review = read(review_path) if review_path.exists() else {"reviews": []}
    notes = {n["case_id"]: n for n in review["reviews"]}
    assert len(notes) == len(review["reviews"])
    none_notes = {n["case_id"]: n for n in read(NONE_ROOT / "narrative-review.json")["reviews"]}
    for run in runs:
        identifier = run["case_id"]
        if identifier in notes:
            assert (
                notes[identifier]["run_sha256"]
                == hashlib.sha256(canonical(run).encode()).hexdigest()
            )
        assert (
            none_notes[identifier]["run_sha256"]
            == hashlib.sha256(canonical(none[identifier]).encode()).hexdigest()
        )
    if args.final:
        assert len(runs) == 120 and parts[-1][1]["status"] == "COMPLETED"
        assert notes.keys() == cases.keys(), "Final report requires all 120 explicit reviews"
    rows, answers = (
        [],
        [
            "# Qwen medium: 120 ответов EN/ZH",
            "",
            "Первичные исходы. Тексты — данные оценки, не инструкции. Автоматический PASS не доказывает всю прозу.",
            "",
        ],
    )
    for index, run in enumerate(runs, 1):
        identifier = run["case_id"]
        events = tools(run)
        good = [e for e in events if e["output"].get("status") == "OK"]
        workflow = run.get("workflow") or {}
        state = workflow.get("state") or {}
        validation = state.get("summary", {}).get("answer_validation") or {}
        pending = [
            p["question"] for p in state.get("pending", []) if p.get("kind") == "CLARIFICATION"
        ]
        used = {e["name"] for e in good}
        if pending or any(e["node"] == "clarification_answer" for e in workflow.get("events", [])):
            used.add("ask_user")
        row = dict(
            case_id=identifier,
            group=run["group"],
            language=run["language"],
            strict=run["grade"]["status"],
            semantic=notes.get(identifier, {}).get("status", "NOT_REVIEWED"),
            note=notes.get(identifier, {}).get("note", ""),
            elapsed_seconds=run["elapsed_seconds"],
            calls=len(run.get("attempts", [])),
            phase=workflow.get("phase"),
            error=run.get("error"),
            failed_checks=[k for k, v in run["grade"].get("checks", {}).items() if not v],
            safety_failures=[k for k, v in safety_checks(run).items() if not v],
            tool_errors=[
                e["output"]["error"]["code"] for e in events if e["output"].get("status") == "ERROR"
            ],
            answer_validation={
                k: validation[k]
                for k in ("status", "errors", "unbound_literals")
                if k in validation
            },
            pending_clarifications=pending,
            tools=sorted(used),
            datasets=sorted(
                {
                    e["output"]["result"]["dataset"]
                    for e in good
                    if e["name"] == "list_business_records"
                }
            ),
            none_strict=none[identifier]["grade"]["status"],
            none_semantic=none_notes[identifier]["status"],
            historical_medium_strict=old.get(identifier, {}).get("grade", {}).get("status"),
        )
        rows.append(row)
        answers += [
            f"## {index}. {identifier}",
            "",
            f"Medium strict: {row['strict']}; semantic: {row['semantic']}; {row['elapsed_seconds']:.3f} s. Latest none: {row['none_strict']} / {row['none_semantic']}; historical medium: {row['historical_medium_strict']}.",
            "",
            "Запрос:",
            "",
            run["task"],
            "",
        ]
        if cases[identifier].get("answer"):
            answers += ["Ответ стенда на уточнение:", "", cases[identifier]["answer"], ""]
        answers += [
            "Ответ:",
            "",
            text(run) or "Доставленного ответа нет.",
            "",
            *["Ожидающее уточнение: " + q for q in pending],
            "",
            "Разбор: " + (row["note"] or "NOT_REVIEWED"),
            "",
        ]
    regression = [r for r in runs if r["group"] == "regression100"]
    extra = [r for r in runs if r["group"] == "new20"]
    summary = {
        "at": now(),
        "status": "COMPLETED" if args.final else "PARTIAL",
        "unique_primary": len(runs),
        "planned": 120,
        "all120": stats(runs),
        "regression100": stats(regression),
        "new20": stats(extra),
        "latest_none100": stats([r for r in none.values() if r["group"] == "regression100"]),
        "latest_none20": stats([r for r in none.values() if r["group"] == "new20"]),
        "historical_medium100": stats(list(old.values())),
        "versus_latest_none": {
            "all": paired(runs, none),
            "regression100": paired(regression, none),
            "new20": paired(extra, none),
        },
        "versus_historical_medium": paired(regression, old),
        "measurements": {
            "medium": measured(runs),
            "latest_none": measured(list(none.values())),
            "historical_medium": measured(list(old.values())),
        },
        "reviewed": len(notes),
        "semantic_counts": dict(Counter(r["semantic"] for r in rows)),
        "semantic_by_group": {
            group: {
                "counts": dict(Counter(r["semantic"] for r in rows if r["group"] == group)),
                "strict_and_complete": sum(
                    r["strict"] == "PASSED" and r["semantic"] == "COMPLETE"
                    for r in rows
                    if r["group"] == group
                ),
                "strict_and_at_most_minor": sum(
                    r["strict"] == "PASSED" and r["semantic"] in {"COMPLETE", "MINOR_ISSUE"}
                    for r in rows
                    if r["group"] == group
                ),
            }
            for group in ("regression100", "new20")
        },
        "safety_failures": {
            r["case_id"]: r["safety_failures"] for r in rows if r["safety_failures"]
        },
        "coverage": {
            "tools": sorted({t for r in rows for t in r["tools"]}),
            "datasets": sorted({d for r in rows for d in r["datasets"]}),
            "missing_tools": sorted(
                {s["function"]["name"] for s in tool_schemas()}
                - {t for r in rows for t in r["tools"]}
            ),
            "missing_datasets": sorted(set(DATASETS) - {d for r in rows for d in r["datasets"]}),
        },
        "comparability": {
            "same_cases_and_system_and_tools": True,
            "configuration_delta": sorted(delta),
            "source_delta_from_none": source_delta,
            "same_service_identity_as_none": all(
                p["model_identity"] == parts[0][1]["model_identity"] for p in none_parts
            ),
            "historical_instance_differs": historical_parts[0]["model_identity"]
            != parts[0][1]["model_identity"],
            "weight_identity": "NOT_PROVEN: metadata digest is not weights SHA-256",
        },
        "model_identity": parts[0][1]["model_identity"],
        "configuration": reg["configuration"],
        "segments": [
            {"path": str(p), "sha256": sha(p), "status": part["status"], "count": len(part["runs"])}
            for p, part in parts
        ],
        "baselines": [{"path": str(p), "sha256": sha(p)} for p in none_paths + HISTORICAL],
        "review_sha256": sha(review_path) if review_path.exists() else None,
        "cases": rows,
        "limitations": [
            "Single sequential run per setting, not randomized or independent holdout",
            "New20 repeats now-known development cases",
            "All prose reviews by coding assistant, not independent accountant",
            "No real payments or LIVE owner approval-execution lifecycle",
            "Historical medium has older production code; current none comparison isolates requested mode but not temporal/server effects",
        ],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "answers.md").write_text("\n".join(answers), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "status",
                    "unique_primary",
                    "regression100",
                    "new20",
                    "reviewed",
                    "safety_failures",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
