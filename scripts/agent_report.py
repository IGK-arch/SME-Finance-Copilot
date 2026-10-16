"""Derive challenge coverage and comparisons only from saved LIVE evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from finance.agent_data import DATASETS
from finance.workflows import tool_schemas


def safety_checks(run: dict) -> dict:
    grade = run["grade"]
    if "safety" in grade:
        return grade["safety"]
    names = (
        "injection_marker_absent",
        "private_marker_absent",
        "no_disallowed_tool_attempt",
        "no_action_or_approval_or_job",
        "policy_unchanged",
        "world_unchanged",
        "facts_unchanged",
        "no_membership_secret_exposed",
    )
    checks = grade.get("checks", {})
    return {name: checks.get(name, False) for name in names}


def coverage(runs: list[dict]) -> dict:
    tools: dict[str, list[str]] = {}
    datasets: dict[str, list[str]] = {}
    for run in runs:
        outputs = (run.get("workflow") or {}).get("state", {}).get("outputs", [])
        good = [o for o in outputs if o["output"].get("status") == "OK"]
        used_tools = {o["name"] for o in good}
        if "ask_user" in run["grade"].get("tools_succeeded", []):
            used_tools.add("ask_user")
        used_datasets = {
            o["output"]["result"]["dataset"] for o in good if o["name"] == "list_business_records"
        }
        for names, target in ((used_tools, tools), (used_datasets, datasets)):
            for name in names:
                target.setdefault(name, []).append(run["case_id"])
    return {
        "tools": tools,
        "datasets": datasets,
        "missing_tools": sorted({s["function"]["name"] for s in tool_schemas()} - tools.keys()),
        "missing_datasets": sorted(set(DATASETS) - datasets.keys()),
        "scope": "Successful tool calls and list reads; not proof of every branch or semantic correctness",
    }


def summarize(before: dict, after: dict) -> dict:
    b = {r["case_id"]: r for r in before["runs"]}
    a = {r["case_id"]: r for r in after["runs"]}
    common = sorted(b.keys() & a.keys())
    definitions = {c["id"]: c for c in before["cases"]}
    final_definitions = {c["id"]: c for c in after["cases"]}
    comparisons = []
    for identifier in common:
        comparisons.append(
            {
                "case_id": identifier,
                "before": b[identifier]["grade"]["status"],
                "after": a[identifier]["grade"]["status"],
                "same_case_definition": definitions[identifier] == final_definitions[identifier],
                "same_user_request": definitions[identifier]["task"]
                == final_definitions[identifier]["task"],
            }
        )
    return {
        "before_status": before["status"],
        "after_status": after["status"],
        "same_model_identity": before["model_identity"] == after["model_identity"],
        "same_configuration": before["configuration"] == after["configuration"],
        "counts_after_all": dict(Counter(r["grade"]["status"] for r in after["runs"])),
        "comparable_cases": comparisons,
        "counts_common_before": dict(Counter(b[i]["grade"]["status"] for i in common)),
        "counts_common_after": dict(Counter(a[i]["grade"]["status"] for i in common)),
        "additional_after_cases": sorted(a.keys() - b.keys()),
        "not_rerun": sorted(b.keys() - a.keys()),
        "coverage": coverage(after["runs"]),
        "safety_failures": {
            r["case_id"]: [k for k, v in safety_checks(r).items() if not v]
            for r in after["runs"]
            if not all(safety_checks(r).values())
        },
        "safety_scope": "New cases compare complete financial rows; original cases retain their original narrower guards. No universal safety guarantee.",
        "current_source_mismatches": [
            name
            for name, expected in after["source_hashes"].items()
            if not Path(name).exists()
            or hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected
        ],
        "narrative_semantics": "NOT_PROVEN; separate review is required even for strict PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--review")
    parser.add_argument("--answers")
    args = parser.parse_args()
    before, after = [
        json.loads(Path(p).read_text(encoding="utf-8")) for p in (args.before, args.after)
    ]
    report = summarize(before, after)
    review = (
        json.loads(Path(args.review).read_text(encoding="utf-8"))
        if args.review
        else {"records": []}
    )
    reviewed = {r["case_id"]: r for r in review["records"]}
    report["narrative_review"] = {
        "source": args.review,
        "reviewer": review.get("reviewer"),
        "counts": dict(
            Counter(
                reviewed.get(r["case_id"], {}).get("status", "NOT_REVIEWED") for r in after["runs"]
            )
        ),
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Расширенная проверка агента: измеренные результаты",
        "",
        f"Исходный прогон: `{args.before}` ({before['status']}); повтор: `{args.after}` ({after['status']}).",
        f"Повтор выбранного набора ({len(after['runs'])} сценариев): {report['counts_after_all']}. Проверка финансовых ссылок: {after['summary']['answer_reference_counts']}.",
        "",
        f"На общих сценариях: до — {report['counts_common_before']}; после — {report['counts_common_after']}.",
        f"Изменения определения/критериев общих сценариев: {[c['case_id'] for c in report['comparable_cases'] if not c['same_case_definition']]}. Детали и неизменность запроса — в comparison JSON.",
        f"Дополнительных сценариев в повторе: {len(report['additional_after_cases'])}; для них этот исходный прогон не является baseline.",
        "",
        "Это синтетические development-сценарии, не независимый holdout. PASS означает прохождение заданных проверок, а не доказательство правильности всего текста.",
        "Состояния операций подготовлены настоящими скриптовыми synthetic OWNER approvals до запуска агента. Сам агент не утверждает и не отправляет операции.",
        "",
        "## Каждый сценарий",
        "",
        "| Сценарий | Категория | Строгая оценка | Просмотр текста ассистентом | Секунды всего | Не прошедшие проверки |",
        "|---|---|---|---|---:|---|",
    ]
    for run in after["runs"]:
        failed = [
            k
            for section in ("checks", "safety")
            for k, v in run["grade"].get(section, {}).items()
            if not v
        ]
        lines.append(
            f"| {run['case_id']} | {run.get('category', 'original suite')} | {run['grade']['status']} | {reviewed.get(run['case_id'], {}).get('status', 'NOT_REVIEWED')} | {run['elapsed_seconds']:.1f} | {', '.join(failed) or '—'} |"
        )
    for title, key in (
        ("Инструменты: успешные вызовы", "tools"),
        ("Наборы данных: прочитанные списки", "datasets"),
    ):
        lines += ["", "## " + title, "", "| Имя | Сценарии |", "|---|---|"]
        for name, cases in sorted(report["coverage"][key].items()):
            lines.append(f"| {name} | {', '.join(cases)} |")
    lines += [
        "",
        "## Ограничения доказательств",
        "",
        "- Проверены зарегистрированные инструменты и наборы данных, не все их комбинации и объёмы.",
        "- Совпадение значения/источника не проверяет все смысловые связи и рекомендации в ответе.",
        "- Исходный doc_injection_ru не предъявил модели вредоносную строку; он не доказывает устойчивость к этой атаке. Отдельный doc_injection_inline требует фактического предъявления атаки.",
        "- Поиск лексический, без embeddings и OCR. Текстовые PDF используют существующий ограниченный parser; новый корпус PDF этим прогоном не проверен.",
        "- Время включает локальную подготовку/граф/модель; это не чистая скорость генерации и не SLA.",
        "- Точный весовой hash сервера не измерен. Identity — fingerprint метаданных сервиса.",
        f"- Несовпадения текущих файлов с повторным прогоном: {report['current_source_mismatches']}.",
    ]
    Path(args.markdown).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    if args.answers:
        answers = [
            "# Все ответы расширенного прогона Strata",
            "",
            f"Источник: `{args.after}`.",
            "",
            "Тексты ниже сохранены как выданы агентом, включая ошибки. Строгая оценка не доказывает смысловую корректность. Комментарии — просмотр coding assistant, не независимая экспертиза.",
        ]
        for run in after["runs"]:
            assessment = reviewed.get(run["case_id"], {})
            state = (run.get("workflow") or {}).get("state", {})
            answer = (state.get("summary") or {}).get(
                "model_text"
            ) or "Завершённый текст отсутствует. См. trace и error в исходном JSON."
            answers += [
                "",
                "## " + run["case_id"],
                "",
                "Запрос: " + run["task"],
                "",
                "Строгая оценка: **"
                + run["grade"]["status"]
                + "**. Просмотр текста: **"
                + assessment.get("status", "NOT_REVIEWED")
                + "**.",
                "",
                assessment.get("note", "Отдельный просмотр не выполнен."),
                "",
                "### Сохранённый ответ",
                "",
                answer,
            ]
        Path(args.answers).write_bytes(("\n".join(answers) + "\n").encode("utf-8"))
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "counts_common_before",
                    "counts_common_after",
                    "not_rerun",
                    "current_source_mismatches",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
