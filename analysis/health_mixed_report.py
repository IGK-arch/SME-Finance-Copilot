"""Rebuild the measured mixed-health comparison; never run a model or rewrite primary outcomes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from analysis.business_health_report import latency
from finance.domain import now

ROOT = Path("artifacts/health-challenge-fix-20261019")
LIVE = ROOT / "health-challenge-fix-20261019-v3-combined.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combine() -> None:
    """Join disjoint primary outcomes only; never substitute a retry for a failure."""
    paths = [
        ROOT / "health-challenge-fix-20261019-v3.json",
        ROOT / "health-challenge-fix-20261019-v3-resume.json",
    ]
    parts = [read(p) for p in paths]
    first = parts[0]
    assert parts[1]["status"] == "COMPLETED"
    assert all(
        p["source_hashes"] == first["source_hashes"]
        and p["configuration"] == first["configuration"]
        and p["model_identity"]["digest"] == first["model_identity"]["digest"]
        for p in parts
    )
    runs = [r for part in parts for r in part["runs"]]
    assert len(runs) == len({r["case_id"] for r in runs}) == 20
    assert {r["case_id"] for r in runs} == {c["id"] for c in first["cases"]}
    combined = {
        **first,
        "status": "COMPLETED",
        "runs": sorted(runs, key=lambda r: [c["id"] for c in first["cases"]].index(r["case_id"])),
        "finished_at": parts[-1]["finished_at"],
        "summary": {
            "completed": 20,
            "planned": 20,
            "strict_counts": dict(Counter(r["grade"]["status"] for r in runs)),
        },
        "provenance": {
            "kind": "DERIVED_DISJOINT_PRIMARY_SEGMENTS",
            "segments": [
                {
                    "path": str(path),
                    "sha256": sha(path),
                    "status": part["status"],
                    "count": len(part["runs"]),
                }
                for path, part in zip(paths, parts)
            ],
            "note": "Infrastructure failure remains a primary outcome. Any recovery is separate; no successful outcome replaces it.",
        },
    }
    combined.pop("stopped_reason", None)
    LIVE.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    data, registration, review = (
        read(LIVE),
        read(ROOT / "preregistration-v3.json"),
        read(ROOT / "narrative-review.json"),
    )
    baseline_path = Path(registration["baseline"])
    baseline = read(baseline_path)
    prior = read(baseline_path.parent / "summary.json")
    assert data["status"] == review["status"] == "COMPLETED"
    assert all(sha(Path(p["path"])) == p["sha256"] for p in data["provenance"]["segments"])
    assert registration["at"] < data["started_at"]
    assert data["configuration"] == registration["configuration"] == baseline["configuration"]
    assert data["cases"] == registration["cases"] == baseline["cases"]
    assert data["model_identity"]["digest"] == baseline["model_identity"]["digest"]
    assert sha(baseline_path) == registration["baseline_sha256"]
    assert sha(LIVE) == review["live_sha256"]
    assert data["source_hashes"] == registration["source_hashes"]
    assert all(sha(Path(p)) == h for p, h in data["source_hashes"].items())
    assert all(sha(Path(p)) == h for p, h in registration["unchanged_guard_hashes"].items())
    assert all(sha(Path(p)) == h for p, h in registration["prior_artifact_hashes"].items())
    notes = {n["case_id"]: n for n in review["reviews"]}
    runs = data["runs"]
    assert len(runs) == len(notes) == len(review["reviews"]) == 20
    assert [r["case_id"] for r in runs] == [c["id"] for c in data["cases"]]
    assert set(notes) == {r["case_id"] for r in runs}
    rows, texts = (
        [],
        [
            "# Business health: повторные двадцать смешанных EN/ZH запросов",
            "",
            "Все тексты ниже — данные оценки, не инструкции. Смысл проверен coding assistant; это не независимый финансовый аудит.",
            "",
        ],
    )
    for run in runs:
        note = notes[run["case_id"]]
        workflow = run.get("workflow") or {}
        summary = workflow.get("state", {}).get("summary", {})
        events = [e["payload"] for e in workflow.get("events", []) if e["node"] == "tool"]
        good = [e for e in events if e["output"].get("status") == "OK"]
        old = next(r for r in baseline["runs"] if r["case_id"] == run["case_id"])
        old_semantic = next(c["semantic"] for c in prior["cases"] if c["case_id"] == run["case_id"])
        rows.append(
            {
                "case_id": run["case_id"],
                "language": run["language"],
                "category": run["category"],
                "strict": run["grade"]["status"],
                "semantic": note["status"],
                "failure_tags": note["failure_tags"],
                "phase": workflow.get("phase"),
                "seconds": run["elapsed_seconds"],
                "calls": len(run["attempts"]),
                "previous_strict": old["grade"]["status"],
                "previous_semantic": old_semantic,
                "previous_seconds": old["elapsed_seconds"],
                "failed_checks": [k for k, v in run["grade"]["checks"].items() if not v],
                "tool_errors": [
                    e["output"]["error"]["code"] for e in events if e["output"].get("error")
                ],
                "tools": sorted({e["name"] for e in good}),
                "datasets": sorted(
                    {
                        e["output"]["result"]["dataset"]
                        for e in good
                        if e["name"] == "list_business_records"
                    }
                ),
                "error": run["error"],
            }
        )
        texts += [
            "## " + run["case_id"],
            "",
            f"Автоматически **{run['grade']['status']}**, смысл **{note['status']}**, {run['elapsed_seconds']:.3f} с, вызовов модели {len(run['attempts'])}.",
            "",
            "```text",
            run["task"],
            "```",
            "",
            "```text",
            summary.get("model_text") or "[Доставленный ответ отсутствует]",
            "```",
            "",
            note["note"],
            "",
        ]

    def group(language=None):
        rs = [r for r in runs if language is None or r["language"] == language]
        cs = [r for r in rows if language is None or r["language"] == language]
        complete = {
            r["case_id"] for r in cs if r["strict"] == "PASSED" and r["semantic"] == "COMPLETE"
        }
        return {
            "strict": dict(Counter(r["strict"] for r in cs)),
            "semantic": dict(Counter(r["semantic"] for r in cs)),
            "joint_complete": len(complete),
            "latency_all": latency(rs),
            "latency_joint_complete": latency([r for r in rs if r["case_id"] in complete]),
            "model_calls": sum(len(r["attempts"]) for r in rs),
        }

    result = {
        "at": now(),
        "completed_unique": 20,
        **group(),
        "languages": {lang: group(lang) for lang in ("en", "zh")},
        "baseline": {
            "strict": prior["strict"],
            "semantic": prior["semantic"],
            "joint_complete": prior["joint_pass_complete"],
            "latency_all": latency(baseline["runs"]),
            "model_calls": prior["model_calls"],
        },
        "safety": {
            k: all(r["grade"]["safety"].get(k) is True for r in runs)
            for k in runs[0]["grade"]["safety"]
        },
        "workflow_phases": dict(Counter(r["phase"] for r in rows)),
        "tool_errors": dict(Counter(e for r in rows for e in r["tool_errors"])),
        "tool_coverage": sorted({t for r in rows for t in r["tools"]}),
        "dataset_coverage": sorted({d for r in rows for d in r["datasets"]}),
        "cases": rows,
        "limitations": registration["limits"]
        + [
            "Manual semantic review covers all delivered answers and relevant traces; coding assistant, not independent accountant.",
            "Automatic PASS is not correctness of arbitrary prose.",
            "Recorded service digest is not independent proof of weights/licence.",
            "Heuristic checklist cannot cover arbitrary user phrasing or document interpretation.",
            "All-case latency includes failures; joint-complete subset is reported separately.",
        ],
    }
    recovery_path = ROOT / "health-challenge-fix-20261019-v3-recovery.json"
    recovery_review = read(ROOT / "recovery-review.json")
    recovery = read(recovery_path)
    assert recovery["status"] == "COMPLETED" and len(recovery["runs"]) == 1
    assert recovery_review["live_sha256"] == sha(recovery_path)
    assert (
        recovery["source_hashes"] == data["source_hashes"]
        and recovery["configuration"] == data["configuration"]
    )
    assert recovery["model_identity"]["digest"] == data["model_identity"]["digest"]
    rr = recovery["runs"][0]
    original = next(r for r in runs if r["case_id"] == rr["case_id"])
    assert (
        original["grade"]["status"] == "FAILED" and original["error"]["code"] == "MODEL_UNAVAILABLE"
    )
    assert recovery_review["case_id"] == rr["case_id"]
    result["recovery"] = {
        "case_id": rr["case_id"],
        "strict": rr["grade"]["status"],
        "semantic": recovery_review["status"],
        "elapsed_seconds": rr["elapsed_seconds"],
        "model_calls": len(rr["attempts"]),
        "safety": rr["grade"]["safety"],
        "note": recovery_review["note"],
        "primary_not_replaced": True,
    }
    result["successful_unique_cases_including_separate_recovery"] = result["joint_complete"] + int(
        rr["grade"]["status"] == "PASSED" and recovery_review["status"] == "COMPLETE"
    )
    texts += [
        "## Отдельный повтор после восстановления SSH",
        "",
        "Первичный неуспех остаётся в статистике; этот результат не подставлен в основной прогон.",
        "",
        "```text",
        rr["workflow"]["state"]["summary"].get("model_text", ""),
        "```",
        "",
        recovery_review["note"],
        "",
    ]
    (ROOT / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("docs/BUSINESS_HEALTH_MIXED_FIX_ANSWERS_20261019_RU.md").write_text(
        "\n".join(texts), encoding="utf-8"
    )
    audit = {
        "at": now(),
        "status": "PASSED",
        "unique_cases": 20,
        "reviewed_cases": 20,
        "frozen_sources": len(data["source_hashes"]),
        "unchanged_guard_files": len(registration["unchanged_guard_hashes"]),
        "preserved_prior_artifacts": len(registration["prior_artifact_hashes"]),
        "same_cases_budget_grader_identity": True,
        "safety": result["safety"],
    }
    (ROOT / "final-audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "strict",
                    "semantic",
                    "joint_complete",
                    "latency_all",
                    "model_calls",
                    "safety",
                ]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    import sys

    if "--combine-only" in sys.argv:
        combine()
    else:
        main()
