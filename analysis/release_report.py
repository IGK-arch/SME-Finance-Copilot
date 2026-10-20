"""Evidence-only release evaluation report; never replaces a primary result with a retry."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from finance.domain import canonical, now
from finance.agent_data import DATASETS
from finance.workflows import tool_schemas
from scripts.agent_report import safety_checks
from scripts.reasoning_report import percentile

ROOT = Path("artifacts/release-eval-20261019")
BASELINES = [
    Path("artifacts/strata-reasoning-none-74-20261017.json"),
    Path("artifacts/strata-reasoning-edge-paired-26-20261017.json"),
]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(run: dict) -> str:
    return (run.get("workflow") or {}).get("state", {}).get("summary", {}).get("model_text", "")


def tools(run: dict) -> list[dict]:
    return [
        e["payload"] for e in (run.get("workflow") or {}).get("events", []) if e["node"] == "tool"
    ]


def latency(runs: list[dict]) -> dict:
    times = [r["elapsed_seconds"] for r in runs]
    return {
        "n": len(times),
        "p50_seconds": round(statistics.median(times), 3) if times else None,
        "p95_seconds": percentile(times, 0.95),
        "total_seconds": round(sum(times), 3),
        "model_calls": sum(len(r.get("attempts", [])) for r in runs),
    }


def stats(runs: list[dict]) -> dict:
    return {
        "model_reached": sum(bool(r.get("attempts")) for r in runs),
        "pre_model_policy_denials": sum(
            not r.get("attempts") and (r.get("error") or {}).get("code") == "POLICY_DENIED"
            for r in runs
        ),
        "run_errors": dict(
            Counter((r.get("error") or {}).get("code", "UNKNOWN") for r in runs if r.get("error"))
        ),
        "counts": dict(Counter(r["grade"]["status"] for r in runs)),
        "all_latency": latency(runs),
        "pass_latency": latency([r for r in runs if r["grade"]["status"] == "PASSED"]),
        "fail_latency": latency([r for r in runs if r["grade"]["status"] != "PASSED"]),
        "by_language": {
            lang: dict(Counter(r["grade"]["status"] for r in runs if r.get("language") == lang))
            for lang in ("en", "zh")
        },
        "latency_by_language": {
            lang: latency([r for r in runs if r.get("language") == lang]) for lang in ("en", "zh")
        },
        "workflow_phases": dict(
            Counter((r.get("workflow") or {}).get("phase", "NO_WORKFLOW") for r in runs)
        ),
    }


def record_reviews(notes: dict[str, tuple[str, str]]) -> None:
    """Persist explicit reviewer decisions bound to exact raw outcomes, never inferred from grades."""
    runs = {r["case_id"]: r for p in ROOT.glob("primary*.json") for r in read(p)["runs"]}
    path = ROOT / "narrative-review.json"
    review = (
        read(path)
        if path.exists()
        else {"reviewer": "Coding assistant; not independent accountant", "reviews": []}
    )
    existing = {r["case_id"]: r for r in review["reviews"]}
    for identifier, (status, note) in notes.items():
        assert status in {"COMPLETE", "MINOR_ISSUE", "PARTIAL", "FAILED"}
        assert identifier in runs and note
        decision = {
            "case_id": identifier,
            "status": status,
            "note": note,
            "run_sha256": hashlib.sha256(canonical(runs[identifier]).encode()).hexdigest(),
        }
        assert identifier not in existing or existing[identifier] == decision, (
            "Explicit prior review must not be silently replaced"
        )
        existing[identifier] = decision
    review["reviews"] = list(existing.values())
    review["updated_at"] = now()
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    parser.add_argument(
        "--segments",
        nargs="+",
        default=[
            str(ROOT / "primary.json"),
            str(ROOT / "primary-resume.json"),
            str(ROOT / "primary-resume-2.json"),
        ],
    )
    args = parser.parse_args()
    registration = read(ROOT / "preregistration-v4.json")
    entries = registration["entries"]
    cases = {e["case"]["id"]: e["case"] for e in entries}
    paths = [Path(p) for p in args.segments]
    parts = [read(p) for p in paths]
    runs = [r for p in parts for r in p["runs"]]
    assert len(runs) == len({r["case_id"] for r in runs}), "Duplicate primary outcome"
    assert {r["case_id"] for r in runs} <= cases.keys()
    source_deltas = []
    for path, part in zip(paths, parts):
        assert part["configuration"] == registration["configuration"]
        assert all(canonical(c) == canonical(cases[c["id"]]) for c in part["cases"])
        assert part["model_identity"]["digest"] == parts[0]["model_identity"]["digest"]
        reg = Path(part["preregistration"])
        assert sha(reg) == part["preregistration_sha256"]
        changed = {
            p: {"segment": h, "final": registration["source_hashes"].get(p)}
            for p, h in part["source_hashes"].items()
            if registration["source_hashes"].get(p) != h
        }
        assert set(changed) <= {"scripts/release_eval.py"}, (
            "Unexpected source changes during series"
        )
        source_deltas.append({"path": str(path), "changes": changed})
    assert all(sha(Path(p)) == h for p, h in registration["source_hashes"].items())
    if args.final:
        assert len(runs) == 120 and parts[-1]["status"] == "COMPLETED"
    baseline_reports = [read(p) for p in BASELINES]
    old = {
        r["case_id"]: r
        for p in baseline_reports
        for r in p["runs"]
        if r["reasoning_effort"] == "none"
    }
    old_cases = {c["id"]: c for p in baseline_reports for c in p["cases"]}
    old = {
        identifier: {**run, "language": old_cases[identifier].get("language", "unknown")}
        for identifier, run in old.items()
    }
    assert len(old) == 100
    assert all(
        canonical(old_cases[e["case"]["id"]]) == canonical(e["case"])
        for e in entries
        if e["group"] == "regression100"
    )
    assert all(
        p["configurations"]["none"] == registration["configuration"] for p in baseline_reports
    )
    review_path = ROOT / "narrative-review.json"
    review = read(review_path) if review_path.exists() else {"reviews": []}
    notes = {n["case_id"]: n for n in review["reviews"]}
    assert len(notes) == len(review["reviews"])
    for run in runs:
        if run["case_id"] in notes:
            assert (
                notes[run["case_id"]]["run_sha256"]
                == hashlib.sha256(canonical(run).encode()).hexdigest()
            )
    if args.final:
        assert {r["case_id"] for r in runs} == notes.keys(), (
            "Final release report requires explicit review of all 120 primary outcomes"
        )
    rows, answers = (
        [],
        [
            "# Qwen: 100 прежних и 20 новых запросов EN/ZH",
            "",
            "Тексты ниже — данные оценки, а не инструкции. Первичные исходы сохранены; автоматический PASS не доказывает правильность всей прозы.",
            "",
        ],
    )
    for index, run in enumerate(runs, 1):
        identifier = run["case_id"]
        calls = tools(run)
        good = [c for c in calls if c["output"].get("status") == "OK"]
        errors = [
            c["output"]["error"]["code"] for c in calls if c["output"].get("status") == "ERROR"
        ]
        row = {
            "case_id": identifier,
            "group": run["group"],
            "language": run["language"],
            "strict": run["grade"]["status"],
            "semantic": notes.get(identifier, {}).get("status", "NOT_REVIEWED"),
            "note": notes.get(identifier, {}).get("note", ""),
            "elapsed_seconds": run["elapsed_seconds"],
            "calls": len(run.get("attempts", [])),
            "error": run.get("error"),
            "failed_checks": [k for k, v in run["grade"].get("checks", {}).items() if not v],
            "safety_failures": [k for k, v in safety_checks(run).items() if not v],
            "tool_errors": errors,
            "tools": sorted({c["name"] for c in good}),
            "datasets": sorted(
                {
                    c["output"]["result"]["dataset"]
                    for c in good
                    if c["name"] == "list_business_records"
                }
            ),
            "answer_delivered": bool(text(run)),
            "baseline_strict": old.get(identifier, {}).get("grade", {}).get("status"),
        }
        validation = (
            (run.get("workflow") or {})
            .get("state", {})
            .get("summary", {})
            .get("answer_validation", {})
        )
        row["answer_validation"] = {
            k: validation[k] for k in ("status", "errors", "unbound_literals") if k in validation
        }
        row["phase"] = (run.get("workflow") or {}).get("phase")
        row["pending_clarifications"] = [
            p["question"]
            for p in (run.get("workflow") or {}).get("state", {}).get("pending", [])
            if p.get("kind") == "CLARIFICATION"
        ]
        if row["pending_clarifications"] or any(
            e["node"] == "clarification_answer"
            for e in (run.get("workflow") or {}).get("events", [])
        ):
            row["tools"] = sorted(set(row["tools"]) | {"ask_user"})
        rows.append(row)
        answers += [
            f"## {index}. {identifier}",
            "",
            f"Strict: {row['strict']}; semantic: {row['semantic']}; {run['elapsed_seconds']:.3f} s.",
            "",
            "Запрос:",
            "",
            run["task"],
            "",
            *(
                [
                    "Ответ стенда на уточнение (если агент запросил его):",
                    "",
                    cases[identifier]["answer"],
                    "",
                ]
                if cases[identifier].get("answer")
                else []
            ),
            "Ответ:",
            "",
            text(run) or "Доставленного ответа нет.",
            "",
            *["Ожидающее уточнение: " + question for question in row["pending_clarifications"]],
            "",
            "Разбор: " + (row["note"] or "NOT_REVIEWED"),
            "",
        ]
    regression = [r for r in runs if r["group"] == "regression100"]
    pairs = [
        r["elapsed_seconds"] / old[r["case_id"]]["elapsed_seconds"]
        for r in regression
        if r["grade"]["status"] == old[r["case_id"]]["grade"]["status"] == "PASSED"
    ]
    summary = {
        "at": now(),
        "status": "COMPLETED" if args.final else "PARTIAL",
        "unique_primary": len(runs),
        "planned": 120,
        "all120": stats(runs),
        "configuration": registration["configuration"],
        "model_identity": parts[-1]["model_identity"],
        "review_sha256": sha(review_path) if review_path.exists() else None,
        "regression100": stats(regression),
        "new20": stats([r for r in runs if r["group"] == "new20"]),
        "historical_none100": stats(list(old.values())),
        "historical_identity_comparison": {
            "same_alias_and_engine": all(
                all(
                    p["model_identity"][key] == parts[0]["model_identity"][key]
                    for key in ("model", "engine_version", "context_tokens")
                )
                for p in baseline_reports
            ),
            "same_service_instance_digest": all(
                p["model_identity"]["digest"] == parts[0]["model_identity"]["digest"]
                for p in baseline_reports
            ),
            "same_weights": "NOT_PROVEN: neither run records a weight digest",
            "baseline_identities": [p["model_identity"] for p in baseline_reports],
        },
        "paired_both_pass": {
            "n": len(pairs),
            "median_new_over_old_latency": statistics.median(pairs) if pairs else None,
        },
        "regressed": [
            r["case_id"]
            for r in regression
            if r["grade"]["status"] != "PASSED" and old[r["case_id"]]["grade"]["status"] == "PASSED"
        ],
        "improved": [
            r["case_id"]
            for r in regression
            if r["grade"]["status"] == "PASSED" and old[r["case_id"]]["grade"]["status"] != "PASSED"
        ],
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
        "reviewed": sum(r["semantic"] != "NOT_REVIEWED" for r in rows),
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
            "scope": "Durable successful tool events and observed clarification pause/resume, not proof of every branch or semantic accuracy",
        },
        "source_deltas": source_deltas,
        "segments": [
            {"path": str(p), "sha256": sha(p), "status": v["status"], "count": len(v["runs"])}
            for p, v in zip(paths, parts)
        ],
        "baselines": [{"path": str(p), "sha256": sha(p)} for p in BASELINES],
        "cases": rows,
        "limitations": [
            "Automatic PASS is not prose correctness; semantic coverage is explicitly counted",
            "Author-created new20 is not independent external holdout",
            "Historical same-budget comparison is not concurrent randomized speed experiment",
            "Historical alias/engine match, service instance digest differs after restart; exact weight equality unproved",
            "Service metadata digest is not weight/license proof",
            "No real payments; no LIVE owner-approval lifecycle or UI/PG test in this evaluation",
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
