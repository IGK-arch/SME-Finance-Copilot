"""Read-only five-model report; refuse incomplete or substituted primary evidence."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scripts.agent_report import coverage, safety_checks


def load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(quantile * len(values)) - 1)], 3)


def error_code(error: object) -> str | None:
    if not isinstance(error, dict):
        return None
    inner = error.get("error", error)
    return inner.get("code") if isinstance(inner, dict) else None


def durable_coverage(runs: list[dict]) -> dict:
    """Include retained events and a proven clarification resume, not requests alone."""
    normalized = []
    for run in runs:
        workflow = run.get("workflow") or {}
        state = workflow.get("state") or {}
        events = workflow.get("events", [])
        outputs = state.get("outputs", []) + [
            e["payload"]
            for e in events
            if e.get("node") == "tool" and isinstance(e.get("payload", {}).get("output"), dict)
        ]
        requested_question = any(
            c.get("function", {}).get("name") == "ask_user"
            for a in run.get("attempts", [])
            if a.get("status") == "OK"
            for c in a.get("message", {}).get("tool_calls", [])
        )
        resumed = any(e.get("node") == "clarification_answer" for e in events)
        succeeded = set(run["grade"].get("tools_succeeded", []))
        if requested_question and resumed:
            succeeded.add("ask_user")
        normalized.append(
            {
                "case_id": run["case_id"],
                "workflow": {"state": {"outputs": outputs}},
                "grade": {"tools_succeeded": sorted(succeeded)},
            }
        )
    result = coverage(normalized)
    result["scope"] += (
        "; includes durable tool events and ask_user followed by clarification_answer"
    )
    return result


def describe(run: dict, case: dict, source: str) -> dict:
    workflow = run.get("workflow") or {}
    state = workflow.get("state") or {}
    answer = (state.get("summary") or {}).get("model_text") or ""
    attempts = run.get("attempts", [])
    known = []
    for attempt in attempts:
        metrics = (attempt.get("provider_measurement") or {}).get("metrics") or {}
        if metrics.get("measurement_source") == "LLAMACPP_RESPONSE_USAGE":
            known.append(metrics)
    seconds = run["elapsed_seconds"]
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid recorded elapsed time")
    return {
        "case_id": run["case_id"],
        "language": case["language"],
        "category": case.get("category", run.get("category", "original")),
        "source_report": source,
        "task": run["task"],
        "grade": run["grade"]["status"],
        "failed_checks": [k for k, v in run["grade"].get("checks", {}).items() if v is not True],
        "failed_safety": [k for k, v in safety_checks(run).items() if v is not True],
        "tool_errors": run["grade"].get("tool_errors", []),
        "error": error_code(run.get("error")),
        "call_errors": [
            error_code(a.get("error")) or "UNKNOWN" for a in attempts if a.get("status") == "FAILED"
        ],
        "phase": workflow.get("phase"),
        "answer": answer,
        "answer_reference_status": (state.get("summary") or {})
        .get("answer_validation", {})
        .get("status"),
        "seconds": seconds,
        "calls_attempted": len(attempts),
        "calls_with_usage": len(known),
        "model_roundtrip_seconds": sum(a["elapsed_seconds"] for a in attempts),
        "prompt_tokens_known": sum(m["prompt_eval_count"] for m in known),
        "completion_tokens_known": sum(m["eval_count"] for m in known),
        "reasoning_observed_calls": sum(m.get("reasoning_observed") is True for m in known),
        "finish_reasons": dict(Counter(m.get("done_reason", "UNKNOWN") for m in known)),
        "tools_succeeded": run["grade"].get("tools_succeeded", []),
        "datasets_read": run["grade"].get("datasets_read", []),
    }


def summarize(rows: list[dict], runs: list[dict]) -> dict:
    attempted = [r for r in rows if r["calls_attempted"]]
    good = [r for r in attempted if r["grade"] == "PASSED"]
    groups = {}
    for dimension in ("language", "category"):
        groups[dimension] = {
            name: {
                "n": len(selected := [r for r in rows if r[dimension] == name]),
                "passed": sum(r["grade"] == "PASSED" for r in selected),
                "p50_seconds": percentile([r["seconds"] for r in selected], 0.5),
            }
            for name in sorted({r[dimension] for r in rows})
        }
    return {
        "n": len(rows),
        "grades": dict(Counter(r["grade"] for r in rows)),
        "answered": sum(bool(r["answer"].strip()) for r in rows),
        "empty_final_text": sum(not r["answer"].strip() for r in rows),
        "reference_rejection_fallback": sum(
            r["answer"].startswith("Answer validation failed.") for r in rows
        ),
        "phases": dict(Counter(r["phase"] or "NONE" for r in rows)),
        "all_p50_seconds": percentile([r["seconds"] for r in rows], 0.5),
        "all_p95_seconds": percentile([r["seconds"] for r in rows], 0.95),
        "attempted_case_count": len(attempted),
        "usage_confirmed_case_count": sum(r["calls_with_usage"] > 0 for r in rows),
        "passed_attempted_case_count": len(good),
        "passed_p50_seconds": percentile([r["seconds"] for r in good], 0.5),
        "passed_p95_seconds": percentile([r["seconds"] for r in good], 0.95),
        "calls_attempted": sum(r["calls_attempted"] for r in rows),
        "calls_with_usage": sum(r["calls_with_usage"] for r in rows),
        "prompt_tokens_known": sum(r["prompt_tokens_known"] for r in rows),
        "completion_tokens_known": sum(r["completion_tokens_known"] for r in rows),
        "reasoning_observed_calls": sum(r["reasoning_observed_calls"] for r in rows),
        "case_errors": dict(Counter(r["error"] for r in rows if r["error"])),
        "call_errors": dict(Counter(e for r in rows for e in r["call_errors"])),
        "failed_checks": dict(Counter(k for r in rows for k in r["failed_checks"])),
        "safety_failures": {r["case_id"]: r["failed_safety"] for r in rows if r["failed_safety"]},
        "coverage": durable_coverage(runs),
        "groups": groups,
    }


def collect(root: Path, queue: dict, manifest: dict, frozen: dict) -> dict:
    cases = {c["id"]: c for c in frozen["cases"]}
    if len(cases) != 100 or len(frozen["cases"]) != 100 or len(queue["models"]) != 5:
        raise ValueError("Expected five models and 100 unique frozen cases")
    if (
        hashlib.sha256((root / manifest["frozen_case_artifact"]).read_bytes()).hexdigest()
        != manifest["frozen_case_artifact_sha256"]
    ):
        raise ValueError("Frozen artifact changed")
    # Check completeness before computing any quality or latency summary.
    for item in queue["models"]:
        recorded: list[str] = []
        for name in item["reports"]:
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("Report outside repository")
            recorded.extend(r["case_id"] for r in load(path)["runs"])
        if len(recorded) != len(set(recorded)):
            raise ValueError("Duplicate primary case")
        if len(recorded) != 100 or set(recorded) != cases.keys():
            raise ValueError(
                f"Incomplete {item['model']}: {len(recorded)}/100; analysis requires all 500"
            )
    summaries, outcomes, provenance, identities = {}, {}, [], {}
    budgets = []
    models_seen = set()
    for item in queue["models"]:
        slug = item["model"]
        if slug in models_seen:
            raise ValueError("Duplicate model")
        models_seen.add(slug)
        rows, runs, seen, ids = [], [], set(), []
        for name in item["reports"]:
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("Report outside repository")
            raw = path.read_bytes()
            report = json.loads(raw)
            if report["source_hashes"] != manifest["source_hashes"]:
                raise ValueError("Source freeze changed in primary report")
            if any(c != cases.get(c["id"]) for c in report["cases"]):
                raise ValueError("Scenario definition changed")
            identity = report.get("model_identity")
            pin = manifest["download_plan"]["files"][item["index"] - 1]["sha256"]
            if not identity or identity.get("weight_digest") != pin:
                raise ValueError("Missing or changed weight identity")
            ids.append(identity)
            budgets.append({k: v for k, v in report["configuration"].items() if k != "model"})
            provenance.append(
                {
                    "model": slug,
                    "path": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "status": report["status"],
                    "n": len(report["runs"]),
                }
            )
            for run in report["runs"]:
                key = run["case_id"]
                if key in seen or key not in cases:
                    raise ValueError("Duplicate or unknown primary case: " + key)
                if run["grade"]["status"] not in {"PASSED", "FAILED"}:
                    raise ValueError("Missing primary grade")
                seen.add(key)
                rows.append(describe(run, cases[key], name))
                runs.append(run)
        if seen != cases.keys():
            raise ValueError(f"Incomplete {slug}: {len(seen)}/100; analysis requires all 500")
        outcomes[slug] = sorted(rows, key=lambda r: r["case_id"])
        summaries[slug] = summarize(rows, runs)
        identities[slug] = list({i["digest"]: i for i in ids}.values())
    if not all(b == budgets[0] for b in budgets):
        raise ValueError("Different inference budgets across primary reports")
    pairs = []
    for first, second in itertools.combinations(outcomes, 2):
        a = {r["case_id"]: r for r in outcomes[first]}
        b = {r["case_id"]: r for r in outcomes[second]}
        both = [
            i
            for i in cases
            if a[i]["grade"] == b[i]["grade"] == "PASSED"
            and a[i]["calls_with_usage"]
            and b[i]["calls_with_usage"]
            and a[i]["seconds"] > 0
        ]
        pairs.append(
            {
                "first": first,
                "second": second,
                "first_pass_only": [
                    i for i in cases if a[i]["grade"] == "PASSED" and b[i]["grade"] != "PASSED"
                ],
                "second_pass_only": [
                    i for i in cases if b[i]["grade"] == "PASSED" and a[i]["grade"] != "PASSED"
                ],
                "both_pass_with_usage_n": len(both),
                "second_over_first_latency_ratio_median": statistics.median(
                    b[i]["seconds"] / a[i]["seconds"] for i in both
                )
                if both
                else None,
            }
        )
    return {
        "schema_version": 1,
        "status": "ALL_500_PRIMARY_OUTCOMES_PRESENT",
        "total": 500,
        "summary": summaries,
        "outcomes": outcomes,
        "provenance": provenance,
        "identities": identities,
        "configuration": budgets[0],
        "pairs": pairs,
        "restoration": queue.get("restore"),
        "current_source_differences": [
            p
            for p, h in manifest["source_hashes"].items()
            if not (root / p).exists() or hashlib.sha256((root / p).read_bytes()).hexdigest() != h
        ],
        "narrative_review": "EXTERNAL_TO_AUTOMATED_REPORT; see docs/MULTIMODEL_100_RESULTS_RU.md and artifacts/multimodel-narrative-review-20261017.json for the explicit manual review scope",
        "latency_scope": "Case wall time includes local setup, graph, model and errors. Successful-case and both-PASS paired views are separate; no pure decoding tokens/s claimed.",
    }


def render(report: dict) -> tuple[str, str]:
    lines = [
        "# Пять моделей × 100 сценариев: измеренные результаты",
        "",
        "Производная сводка 500 уникальных первичных исходов. Ошибки и транспортные сбои сохранены; успешные повторы не подставляются. PASS — строгий автоматический критерий, не независимая оценка всего текста.",
        "",
        "| Модель | PASS / 100 | Непустой ответ | p50 всех, с | p95 всех, с | p50 успешных с вызовом модели, с | Таких успешных случаев |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, s in report["summary"].items():
        lines.append(
            f"| {model} | {s['grades'].get('PASSED', 0)} | {s['answered']} | {s['all_p50_seconds']} | {s['all_p95_seconds']} | {s['passed_p50_seconds']} | {s['passed_attempted_case_count']} |"
        )
    lines += [
        "",
        "Время — полная задержка сценария, включая локальную подготовку и ошибочные исходы. Быстрый отказ не означает быстрый полезный ответ. Чистая скорость декодирования здесь не измерена.",
        "У Occamy и Qwen3.8-27B нет ни одного ответа с подтверждённым usage: их задержки — время отказа, а не скорость генерации. Непустой ответ включает стандартный отказ проверки ссылок и не означает выполненную задачу. Смысловой разбор: [MULTIMODEL_100_RESULTS_RU.md](MULTIMODEL_100_RESULTS_RU.md).",
        "",
        "## Языки",
        "",
        "| Модель | Язык | PASS | Всего |",
        "|---|---|---:|---:|",
    ]
    for model, s in report["summary"].items():
        for lang, g in s["groups"]["language"].items():
            lines.append(f"| {model} | {lang} | {g['passed']} | {g['n']} |")
    lines += [
        "",
        "## Покрытие",
        "",
        "| Модель | Успешно вызванные tools | Прочитанные datasets | Случаи с usage от модели | Попытки вызовов / с usage |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, s in report["summary"].items():
        c = s["coverage"]
        lines.append(
            f"| {model} | {len(c['tools'])} | {len(c['datasets'])} | {s['usage_confirmed_case_count']} | {s['calls_attempted']} / {s['calls_with_usage']} |"
        )
    lines += ["", "## Автоматические ошибки", ""]
    for model, s in report["summary"].items():
        lines += [
            f"### {model}",
            "",
            "Ошибки модельных вызовов: `" + json.dumps(s["call_errors"], ensure_ascii=False) + "`.",
            "",
            "Не пройденные проверки: `" + json.dumps(s["failed_checks"], ensure_ascii=False) + "`.",
            "",
            "Нарушенные safety assertions: `"
            + json.dumps(s["safety_failures"], ensure_ascii=False)
            + "`.",
            "",
        ]
    lines += [
        "## Все случаи",
        "",
        "| Модель | Сценарий | Язык | Оценка | Секунды | Ошибки / проверки |",
        "|---|---|---|---|---:|---|",
    ]
    answers = [
        "# Сохранённые ответы пяти моделей на 100 сценариев",
        "",
        "Синтетические данные; исходный текст, включая ошибки. Пустой ответ обозначен явно. Ручная семантическая проверка этим экспортом не выполняется.",
    ]
    for model, rows in report["outcomes"].items():
        for r in rows:
            failed = ", ".join(r["failed_checks"] + r["failed_safety"] + r["call_errors"])
            lines.append(
                f"| {model} | {r['case_id']} | {r['language']} | {r['grade']} | {r['seconds']:.3f} | {failed or '—'} |"
            )
            answers += [
                "",
                f"## {model} / {r['case_id']}",
                "",
                f"{r['grade']}; {r['seconds']:.3f} s; phase={r['phase']}. Источник: `{r['source_report']}`.",
                "",
                "Запрос:",
                "```text",
                r["task"],
                "```",
                "",
                "Ответ:",
                "```text",
                r["answer"] or "[NO_FINAL_MODEL_TEXT]",
                "```",
            ]
    lines += [
        "",
        "## Ограничения",
        "",
        "Одна синтетическая development-выборка, один первичный исход на пару модель/сценарий. Повторы для статистической устойчивости не проводились. Квантизации и архитектуры различаются; сравниваются развёрнутые GGUF в одном бюджете. Аварийные сегменты сохранены. Gemma дозапускалась после восстановления серверной среды. Исходная Strata — отдельный runtime; её прежние результаты не являются идентичным экспериментом. Окончательный статус восстановления: `"
        + str(report["restoration"])
        + "`. Отдельный семантический разбор требуется даже для PASS.",
    ]
    return "\n".join(lines) + "\n", "\n".join(answers) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    queue = load(root / "artifacts/multimodel-100-queue-20261017.json")
    manifest = load(root / "artifacts/multimodel-100-manifest-20261017.json")
    report = collect(root, queue, manifest, load(root / manifest["frozen_case_artifact"]))
    report["generator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result, answers = render(report)
    (root / "artifacts/multimodel-500-summary-20261017.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "docs/MULTIMODEL_100_MEASURED_RU.md").write_text(result, encoding="utf-8")
    (root / "docs/MULTIMODEL_100_ANSWERS_RU.md").write_text(answers, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "total": report["total"],
                "restoration": report["restoration"],
            }
        )
    )


if __name__ == "__main__":
    main()
