"""Derive paired quality/latency evidence; never promote retries or missing results to PASS."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from finance.domain import Json
from scripts.agent_report import coverage, safety_checks


def percentile(values: list[float], quantile: float) -> float | None:
    """Nearest-rank percentile; null for no observations."""
    return (
        round(sorted(values)[max(0, math.ceil(quantile * len(values)) - 1)], 3) if values else None
    )


def measurements(run: Json) -> Json:
    attempts = run.get("attempts", [])
    measured = [a.get("provider_measurement", {}).get("metrics", {}) for a in attempts]
    known = [m for m in measured if m.get("measurement_source") == "STRATA_RESPONSE_USAGE"]
    return {
        "elapsed_seconds": run["elapsed_seconds"],
        "calls": len(attempts),
        "model_roundtrip_seconds": sum(a["elapsed_seconds"] for a in attempts),
        "measured_calls": len(known),
        "unmeasured_calls": len(attempts) - len(known),
        "prompt_tokens_known": sum(m["prompt_eval_count"] for m in known),
        "completion_tokens_known": sum(m["eval_count"] for m in known),
        "reasoning_observed_calls": sum(m.get("reasoning_observed") is True for m in known),
        "reasoning_tokens": sum(m["reasoning_tokens"] for m in known)
        if known
        and len(known) == len(attempts)
        and all(m.get("reasoning_tokens") is not None for m in known)
        else None,
        "errors": [
            a.get("error", {}).get("error", {}).get("code", "UNKNOWN")
            for a in attempts
            if a.get("status") == "FAILED"
        ],
    }


def visible_answer(run: Json) -> str:
    return (run.get("workflow") or {}).get("state", {}).get("summary", {}).get("model_text", "")


def combine(paths: list[Path]) -> Json:
    cases: dict[str, Json] = {}
    rows: dict[tuple[str, str], Json] = {}
    provenance = []
    for path in paths:
        raw = path.read_bytes()
        report = json.loads(raw)
        for case in report["cases"]:
            if case["id"] in cases and cases[case["id"]] != case:
                raise ValueError("Changed case definition: " + case["id"])
            cases[case["id"]] = case
        for run in report["runs"]:
            effort = run.get("reasoning_effort") or report.get("configuration", {}).get(
                "strata_reasoning_effort"
            )
            if effort not in {"none", "medium"}:
                raise ValueError("Primary comparison only accepts explicit none/medium")
            key = (run["case_id"], effort)
            if key in rows:
                raise ValueError(
                    "Duplicate primary outcome; retries must be reported separately: " + str(key)
                )
            rows[key] = {
                "case_id": run["case_id"],
                "reasoning_effort": effort,
                "source_report": path.as_posix(),
                "run": run,
                "measurements": measurements(run),
                "configuration": report.get("configurations", {}).get(effort)
                or report.get("configuration"),
                "model_identity": report.get("model_identity"),
                "source_hashes": report.get("source_hashes"),
            }
        provenance.append(
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "status": report["status"],
                "runs": len(report["runs"]),
            }
        )
    pairs = []
    for identifier in sorted(cases):
        before, after = rows.get((identifier, "none")), rows.get((identifier, "medium"))
        if before is None or after is None:
            continue
        first, second = before["run"], after["run"]
        config_a, config_b = before["configuration"], after["configuration"]
        ignore = {"think", "strata_reasoning_effort"}
        pairs.append(
            {
                "case_id": identifier,
                "category": cases[identifier].get("category", first.get("category", identifier)),
                "none": first["grade"]["status"],
                "medium": second["grade"]["status"],
                "none_seconds": first["elapsed_seconds"],
                "medium_seconds": second["elapsed_seconds"],
                "latency_ratio": second["elapsed_seconds"] / first["elapsed_seconds"],
                "same_service_identity": before["model_identity"] == after["model_identity"],
                "same_budget": {k: v for k, v in config_a.items() if k not in ignore}
                == {k: v for k, v in config_b.items() if k not in ignore},
                "source_differences": [
                    p
                    for p in set(before["source_hashes"]) & set(after["source_hashes"])
                    if before["source_hashes"][p] != after["source_hashes"][p]
                ],
            }
        )
    summaries = {}
    for effort in ("none", "medium"):
        selected = [r for (_, e), r in rows.items() if e == effort]
        times = [r["run"]["elapsed_seconds"] for r in selected]
        summaries[effort] = {
            "completed": len(selected),
            "counts": dict(Counter(r["run"]["grade"]["status"] for r in selected)),
            "task_seconds_p50": percentile(times, 0.5),
            "task_seconds_p95": percentile(times, 0.95),
            "calls": sum(r["measurements"]["calls"] for r in selected),
            "completion_tokens_known": sum(
                r["measurements"]["completion_tokens_known"] for r in selected
            ),
            "unmeasured_calls": sum(r["measurements"]["unmeasured_calls"] for r in selected),
            "reasoning_observed_calls": sum(
                r["measurements"]["reasoning_observed_calls"] for r in selected
            ),
            "coverage": coverage([r["run"] for r in selected]),
            "safety_failures": {
                r["case_id"]: [k for k, v in safety_checks(r["run"]).items() if not v]
                for r in selected
                if not all(safety_checks(r["run"]).values())
            },
        }
    both_pass = [p for p in pairs if p["none"] == p["medium"] == "PASSED"]
    return {
        "status": "COMPLETED"
        if len(cases) == 100
        and len(pairs) == 100
        and len(rows) == 200
        and all(p["status"] == "COMPLETED" for p in provenance)
        else "PARTIAL",
        "scope": "Fixed-budget per-call reasoning; no retained reasoning history. Strict grades are not full narrative review.",
        "provenance": provenance,
        "cases": list(cases.values()),
        "outcomes": list(rows.values()),
        "summary": summaries,
        "pairs": pairs,
        "paired_summary": {
            "completed_pairs": len(pairs),
            "improved": [
                p["case_id"] for p in pairs if p["none"] == "FAILED" and p["medium"] == "PASSED"
            ],
            "regressed": [
                p["case_id"] for p in pairs if p["none"] == "PASSED" and p["medium"] == "FAILED"
            ],
            "both_pass_count": len(both_pass),
            "both_pass_latency_ratio_median": statistics.median(
                p["latency_ratio"] for p in both_pass
            )
            if both_pass
            else None,
        },
        "missing": [
            {"case_id": i, "effort": e}
            for i in sorted(cases)
            for e in ("none", "medium")
            if (i, e) not in rows
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--answers", required=True)
    args = parser.parse_args()
    report = combine([Path(p) for p in args.runs])
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    cases = {c["id"]: c for c in report["cases"]}
    lines = [
        "# Reasoning: ответы на 100 сценариев EN/ZH",
        "",
        "Производный документ. Исходные попытки сохранены в JSON; текст размышлений не сохраняется.",
        "",
        f"Статус: {report['status']}. Неполные/неуспешные ответы не заменены успешными повторами.",
        "",
    ]
    for item in sorted(report["outcomes"], key=lambda r: (r["case_id"], r["reasoning_effort"])):
        run = item["run"]
        lines += [
            f"## {item['case_id']} — {item['reasoning_effort']}",
            "",
            f"Результат: {run['grade']['status']}; {run['elapsed_seconds']:.3f} с.",
            "",
            "Запрос:",
            "```text",
            run["task"],
            "```",
            "",
        ]
        if cases[item["case_id"]].get("answer"):
            lines += [
                "Скриптовый ответ пользователя на уточнение:",
                "```text",
                cases[item["case_id"]]["answer"],
                "```",
                "",
            ]
        answer = visible_answer(run)
        lines += [
            "Итоговый текст:",
            "```text",
            answer or "[Нет завершённого итогового текста]",
            "```",
            "",
        ]
        if not answer:
            drafts = [
                a.get("message", {}).get("content")
                for a in run.get("attempts", [])
                if a.get("message", {}).get("content")
            ]
            if drafts:
                lines += [
                    "Последний видимый текст модели (может быть отклонён сервером; не успешный ответ):",
                    "```text",
                    drafts[-1],
                    "```",
                    "",
                ]
        failures = [
            k
            for section in ("checks", "safety")
            for k, v in run["grade"].get(section, {}).items()
            if not v
        ]
        lines += [
            "Не прошли: " + (", ".join(failures) or "нет автоматических нарушений"),
            "",
            "Рубрика смысловой проверки: "
            + cases[item["case_id"]].get(
                "review_rubric",
                "Проверить полноту, суммы, источники, состояния и отсутствие недоказанных утверждений.",
            ),
            "",
        ]
    Path(args.answers).write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {"status": report["status"], "pairs": report["paired_summary"]}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
