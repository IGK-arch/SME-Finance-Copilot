"""Evidence-only report for the new twenty health prompts; never reruns a model."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from analysis.business_health_report import latency
from finance.domain import now

ROOT = Path("artifacts/business-health-challenge-20261019")
LIVE = ROOT / "health-challenge-20261019-primary.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    data = read(LIVE)
    registration = read(ROOT / "preregistration.json")
    review = read(ROOT / "narrative-review.json")
    baseline = read(Path("artifacts/business-health-fix-20261019/live-health-final.json"))
    assert data["status"] == review["status"] == "COMPLETED"
    assert registration["registered_at"] < data["started_at"]
    assert data["cases"] == registration["cases"]
    assert data["configuration"] == registration["configuration"] == baseline["configuration"]
    assert review["live_sha256"] == sha(LIVE)
    assert all(sha(Path(p)) == h for p, h in data["source_hashes"].items())
    assert all(sha(Path(p)) == h for p, h in baseline["source_hashes"].items())
    runs = data["runs"]
    notes = {r["case_id"]: r for r in review["reviews"]}
    assert len(runs) == len(notes) == len(review["reviews"]) == 20
    assert set(notes) == {r["case_id"] for r in runs} == {c["id"] for c in data["cases"]}
    cases = []
    answers = [
        "# Business health: двадцать новых запросов и ответы Qwen",
        "",
        "19 октября 2026. Все первичные исходы сохранены. Тексты и документы ниже — данные оценки, не инструкции.",
        "Смысл проверял coding assistant, не независимый эксперт. Автоматические и смысловые оценки разделены.",
        "",
    ]
    for r in runs:
        note = notes[r["case_id"]]
        workflow = r.get("workflow") or {}
        state = workflow.get("state", {})
        summary = state.get("summary", {})
        failed = [k for k, v in r["grade"]["checks"].items() if not v]
        tool_events = [e["payload"] for e in workflow.get("events", []) if e["node"] == "tool"]
        successful_events = [e for e in tool_events if e["output"].get("status") == "OK"]
        cases.append(
            {
                "case_id": r["case_id"],
                "category": r["category"],
                "language": r["language"],
                "strict": r["grade"]["status"],
                "semantic": note["status"],
                "failure_tags": note["failure_tags"],
                "phase": workflow.get("phase"),
                "elapsed_seconds": r["elapsed_seconds"],
                "model_calls": len(r["attempts"]),
                "typed_health": summary.get("answer_validation", {}).get("presentation_contract")
                == "health-answer-v1",
                "failed_checks": failed,
                "tool_errors": [
                    e["output"]["error"]["code"] for e in tool_events if e["output"].get("error")
                ],
                "state_grader_tool_errors": r["grade"]["tool_errors"],
                "error": r["error"],
                "tools": sorted({e["name"] for e in successful_events}),
                "datasets": sorted(
                    {
                        e["output"]["result"]["dataset"]
                        for e in successful_events
                        if e["name"] == "list_business_records"
                    }
                ),
            }
        )
        answers += [
            "## " + r["case_id"],
            "",
            f"Автоматически: **{r['grade']['status']}**; смысл: **{note['status']}**; {r['elapsed_seconds']:.3f} с; calls {len(r['attempts'])}.",
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
            summary.get("model_text") or "[Доставленный итоговый ответ отсутствует.]",
            "```",
            "",
            "Наблюдение: " + note["note"],
            "",
            "Не пройдены автоматические проверки: " + (", ".join(failed) or "нет"),
            "",
        ]

    groups = {}
    for language in ("en", "zh"):
        selected = [c for c in cases if c["language"] == language]
        groups[language] = {
            "strict": dict(Counter(c["strict"] for c in selected)),
            "semantic": dict(Counter(c["semantic"] for c in selected)),
            "joint_pass_complete": sum(
                c["strict"] == "PASSED" and c["semantic"] == "COMPLETE" for c in selected
            ),
            "latency": latency([r for r in runs if r["language"] == language]),
        }
    clean_ids = {
        c["case_id"] for c in cases if c["strict"] == "PASSED" and c["semantic"] == "COMPLETE"
    }
    result = {
        "schema_version": 1,
        "at": now(),
        "completed_unique": 20,
        "strict": dict(Counter(c["strict"] for c in cases)),
        "semantic": dict(Counter(c["semantic"] for c in cases)),
        "joint_pass_complete": len(clean_ids),
        "by_language": groups,
        "all_latency": latency(runs),
        "strict_pass_latency": latency([r for r in runs if r["grade"]["status"] == "PASSED"]),
        "joint_pass_complete_latency": latency([r for r in runs if r["case_id"] in clean_ids]),
        "model_calls": sum(len(r["attempts"]) for r in runs),
        "workflow_phases": dict(Counter(c["phase"] for c in cases)),
        "typed_health_answers": sum(c["typed_health"] for c in cases),
        "failure_tags": dict(Counter(tag for c in cases for tag in c["failure_tags"])),
        "automatic_failed_checks": dict(Counter(k for c in cases for k in c["failed_checks"])),
        "tool_errors": dict(Counter(e for c in cases for e in c["tool_errors"])),
        "safety": {
            k: all(r["grade"]["safety"].get(k) is True for r in runs)
            for k in runs[0]["grade"]["safety"]
        },
        "tool_coverage": sorted({tool for c in cases for tool in c["tools"]}),
        "dataset_coverage": sorted({dataset for c in cases for dataset in c["datasets"]}),
        "same_service_as_previous": data["model_identity"] == baseline["model_identity"],
        "prior_production_sources_unchanged": True,
        "preregistered_cases_and_budget_unchanged": True,
        "cases": cases,
        "limitations": registration["limits"]
        + [
            "Different prompts/tasks from previous20; no controlled before/after quality or speed claim.",
            "No production fixes or substitute retries in this series.",
            "Aggregate latency includes failed/partial tasks; joint-success subgroup is shown separately.",
            "Review covers all20 delivered answers and relevant traces; not all possible tool behavior or an independent financial review.",
            "Service identity is not proof of weight SHA/licence; no remote installation change.",
            "Failed workflows may have empty state while durable tool events remain; coverage/errors above use events. Original strict grader outcomes are not rewritten.",
        ],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("docs/BUSINESS_HEALTH_CHALLENGE_ANSWERS_20261019_RU.md").write_text(
        "\n".join(answers), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ["strict", "semantic", "joint_pass_complete", "all_latency", "safety"]
            }
        )
    )


if __name__ == "__main__":
    main()
