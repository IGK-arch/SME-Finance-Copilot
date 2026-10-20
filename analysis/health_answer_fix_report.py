"""Compare the preserved health baseline with the complete typed-answer run."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from analysis.business_health_report import latency
from finance.domain import now

ROOT = Path("artifacts/business-health-fix-20261019")
BASE = Path("artifacts/business-health-20261019")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    before = read(BASE / "live-final.json")
    after = read(ROOT / "live-health-final.json")
    review = read(ROOT / "narrative-review.json")
    old_review = read(BASE / "narrative-review.json")
    assert after["status"] == review["status"] == "COMPLETED"
    assert before["cases"] == after["cases"] and before["configuration"] == after["configuration"]
    assert review["live_sha256"] == sha(ROOT / "live-health-final.json")
    assert all(sha(Path(p)) == h for p, h in after["source_hashes"].items())
    assert all(
        before["source_hashes"][p] == after["source_hashes"][p]
        for p in ("scripts/business_health_eval.py", "scripts/business_health_scenarios.py")
    )
    runs = after["runs"]
    notes = {v["case_id"]: v for v in review["reviews"]}
    old_notes = {v["case_id"]: v for v in old_review["reviews"]}
    old_runs = {v["case_id"]: v for v in before["runs"]}
    assert len(runs) == len(notes) == len(set(r["case_id"] for r in runs)) == 20
    assert set(notes) == set(old_runs) == {r["case_id"] for r in runs}
    assert all(all(r["grade"]["safety"].values()) for r in runs)
    cases = []
    answer_lines = [
        "# Business health: повтор после исправлений — все ответы Qwen",
        "",
        "Исходный запрос и решения о чтении/compute выполняет LIVE Qwen. Финальный JSON выбирает разделы и разрешённые IDs; финансовый текст формирует сервер по связанным полям.",
        "Это проверка составной системы, не свободной финансовой прозы модели. Все исходы сохранены, reviewer — coding assistant, не независимый эксперт.",
        "",
    ]
    for r in runs:
        key = r["case_id"]
        state = (r.get("workflow") or {}).get("state", {})
        result = state.get("summary", {})
        cases.append(
            {
                "case_id": key,
                "before_strict": old_runs[key]["grade"]["status"],
                "after_strict": r["grade"]["status"],
                "before_semantic": old_notes[key]["status"],
                "after_semantic": notes[key]["status"],
                "elapsed_seconds": r["elapsed_seconds"],
                "failed_checks": [k for k, v in r["grade"]["checks"].items() if not v],
                "tool_errors": [
                    o["output"]["error"]
                    for o in state.get("outputs", [])
                    if o["output"].get("error")
                ],
                "error": r["error"],
                "presentation_contract": result.get("answer_validation", {}).get(
                    "presentation_contract"
                ),
            }
        )
        answer_lines += [
            "## " + key,
            "",
            f"Автоматически: {r['grade']['status']}; смысл: {notes[key]['status']}; {r['elapsed_seconds']:.3f} с.",
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
            result.get("model_text") or "[Итоговый ответ отсутствует.]",
            "```",
            "",
            "Разбор: " + notes[key]["note"],
            "",
        ]
    groups = {}
    for language in ("en", "zh"):
        subset = [r for r in runs if r["language"] == language]
        groups[language] = {
            "strict": dict(Counter(r["grade"]["status"] for r in subset)),
            "semantic": dict(Counter(notes[r["case_id"]]["status"] for r in subset)),
            "latency": latency(subset),
        }
    paired = [
        r["elapsed_seconds"] / old_runs[r["case_id"]]["elapsed_seconds"]
        for r in runs
        if r["grade"]["status"] == old_runs[r["case_id"]]["grade"]["status"] == "PASSED"
        and notes[r["case_id"]]["status"] == old_notes[r["case_id"]]["status"] == "COMPLETE"
    ]
    summary = {
        "schema_version": 1,
        "generated_at": now(),
        "complete": 20,
        "before_strict": before["summary"]["strict_counts"],
        "after_strict": dict(Counter(r["grade"]["status"] for r in runs)),
        "before_semantic": dict(Counter(v["status"] for v in old_review["reviews"])),
        "after_semantic": dict(Counter(v["status"] for v in notes.values())),
        "by_language": groups,
        "before_latency": latency(before["runs"]),
        "after_latency": latency(runs),
        "before_attempts": sum(len(r["attempts"]) for r in before["runs"]),
        "after_attempts": sum(len(r["attempts"]) for r in runs),
        "paired_strict_and_semantic_pass": {
            "count": len(paired),
            "median_after_before_latency_ratio": statistics.median(paired) if paired else None,
        },
        "all_recorded_safety_passed": True,
        "same_cases_budgets_and_grader": True,
        "same_service_identity": before["model_identity"] == after["model_identity"],
        "model_identity": after["model_identity"],
        "configuration": after["configuration"],
        "cases": cases,
        "limitations": [
            "Changed system presentation and finalization; not a measurement of improved free-form model prose.",
            "Same development cases used for fixes; not an independent holdout.",
            "Latency includes tools, setup, transport and bounded repair, not isolated token generation speed.",
            "Runtime service identity is not proof of weight SHA-256 or licence.",
            "Typed renderer is bounded EN/ZH aggregate health reporting; broader/mixed tasks retain the general path.",
        ],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("docs/BUSINESS_HEALTH_FIX_ANSWERS_20261019_RU.md").write_text(
        "\n".join(answer_lines), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "after_strict",
                    "after_semantic",
                    "after_latency",
                    "after_attempts",
                    "paired_strict_and_semantic_pass",
                    "same_service_identity",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
