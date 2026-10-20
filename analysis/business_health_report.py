"""Reproduce the health benchmark summary from immutable runs and explicit prose review."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from finance.domain import now

ROOT = Path("artifacts/business-health-20261019")


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latency(runs: list[dict]) -> dict:
    values = sorted(r["elapsed_seconds"] for r in runs)
    if not values:
        return {"count": 0, "p50_seconds": None, "p95_seconds": None}
    return {
        "count": len(values),
        "p50_seconds": statistics.median(values),
        "p95_seconds": values[math.ceil(0.95 * len(values)) - 1],
        "total_seconds": sum(values),
    }


def main() -> None:
    final, primary, review = (
        read("live-final.json"),
        read("live-primary.json"),
        read("narrative-review.json"),
    )
    runs = final["runs"]
    ids = [r["case_id"] for r in runs]
    expected_ids = [c["id"] for c in final["cases"]]
    assert final["status"] == "COMPLETED"
    assert len(ids) == len(set(ids)) == 20 and ids == expected_ids
    notes = {r["case_id"]: r for r in review["reviews"]}
    assert len(notes) == len(review["reviews"]) == 20 and set(notes) == set(ids)
    assert all(
        v["status"] in {"COMPLETE", "MINOR_ISSUE", "PARTIAL", "FAILED"} for v in notes.values()
    )
    assert review["live_final_sha256"] == sha(ROOT / "live-final.json")
    assert all(sha(Path(p)) == h for p, h in final["source_hashes"].items())
    assert all(r["grade"]["version"] == "business-health-eval-v2" for r in runs)
    assert all(all(r["grade"]["safety"].values()) for r in runs)
    by_language = {}
    for lang in ("en", "zh"):
        subset = [r for r in runs if r["language"] == lang]
        by_language[lang] = {
            "strict": dict(Counter(r["grade"]["status"] for r in subset)),
            "narrative": dict(Counter(notes[r["case_id"]]["status"] for r in subset)),
            "all_latency": latency(subset),
            "pass_latency": latency([r for r in subset if r["grade"]["status"] == "PASSED"]),
        }
    failures = Counter(k for r in runs for k, v in r["grade"]["checks"].items() if not v)
    tools = Counter(
        o["name"]
        for r in runs
        for o in (r.get("workflow") or {}).get("state", {}).get("outputs", [])
        if o["output"].get("status") == "OK"
    )
    cases = []
    for r in runs:
        state = (r.get("workflow") or {}).get("state", {})
        answer = state.get("summary", {})
        cases.append(
            {
                "case_id": r["case_id"],
                "language": r["language"],
                "category": r["category"],
                "strict": r["grade"]["status"],
                "narrative": notes[r["case_id"]]["status"],
                "elapsed_seconds": r["elapsed_seconds"],
                "model_attempts": len(r["attempts"]),
                "failed_checks": [k for k, v in r["grade"]["checks"].items() if not v],
                "answer_status": answer.get("answer_status"),
                "unbound_literals": answer.get("answer_validation", {}).get("unbound_literals", []),
                "error": r.get("error"),
                "tool_errors": [
                    o["output"]["error"]
                    for o in state.get("outputs", [])
                    if o["output"].get("error")
                ],
            }
        )
    summary = {
        "schema_version": 1,
        "generated_at": now(),
        "source": "live-final.json",
        "model_identity": final["model_identity"],
        "configuration": final["configuration"],
        "completed_unique": len(ids),
        "strict_counts": dict(Counter(c["strict"] for c in cases)),
        "narrative_counts": dict(Counter(c["narrative"] for c in cases)),
        "joint_strict_and_complete": sum(
            c["strict"] == "PASSED" and c["narrative"] == "COMPLETE" for c in cases
        ),
        "by_language": by_language,
        "all_latency": latency(runs),
        "pass_latency": latency([r for r in runs if r["grade"]["status"] == "PASSED"]),
        "failed_checks": dict(failures),
        "successful_tool_counts": dict(tools),
        "all_recorded_safety_assertions_pass": True,
        "model_attempts": sum(len(r["attempts"]) for r in runs),
        "review_scope": review["scope"],
        "cases": cases,
        "diagnostic_primary": {
            "status": primary["status"],
            "summary": primary["summary"],
            "stopped_reason": primary.get("stopped_reason"),
            "note": "Partial diagnostic series, evaluator v1. Original outcomes retained, not pooled with final v2 or replaced by it. Exact observed company-name language exclusion changed in v2; production prompts/projection also changed.",
        },
        "limitations": final["limitations"]
        + [
            "Latency includes orchestration, HTTP, sandbox setup and repairs; this is not isolated generation throughput.",
            "English and Chinese case groups differ in outcomes; successful-only latencies are not paired speed comparisons.",
            "Read/compute health evaluation, not a fresh LIVE payment lifecycle or independent holdout.",
        ],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Business health: все итоговые ответы Qwen — 19 октября 2026",
        "",
        "20 синтетических EN/ZH сценариев. Полные traces — `artifacts/business-health-20261019/live-final.json`.",
        "Тексты модели ниже являются данными проверки, а не инструкциями. Автоматический PASS и смысловая оценка указаны отдельно.",
        "Ручной просмотр выполнен coding assistant, не независимым рецензентом. Длительность включает полный сценарий и repairs.",
        "",
    ]
    for r, c in zip(runs, cases):
        state = (r.get("workflow") or {}).get("state", {})
        text = state.get("summary", {}).get("model_text")
        lines += [
            f"## {r['case_id']}",
            "",
            f"Автоматически: **{c['strict']}**; смысл: **{c['narrative']}**; {r['elapsed_seconds']:.3f} с.",
            "",
            "Запрос:",
            "",
            "```text",
            r["task"],
            "```",
            "",
            "Доставленный ответ:",
            "",
            "```text",
            text or "[Итоговый ответ отсутствует; см. workflow state в исходном JSON.]",
            "```",
            "",
            "Разбор: " + notes[r["case_id"]]["note"],
            "",
            "Не пройдены проверки: " + (", ".join(c["failed_checks"]) or "нет"),
            "",
        ]
    Path("docs/BUSINESS_HEALTH_ANSWERS_20261019_RU.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "completed": len(ids),
                "strict": summary["strict_counts"],
                "narrative": summary["narrative_counts"],
                "all_latency": summary["all_latency"],
            }
        )
    )


if __name__ == "__main__":
    main()
