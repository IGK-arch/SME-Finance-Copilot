"""Completion evidence for bounded mixed health requests, never an execution authority.

Only the original user request defines obligations. Retrieved documents cannot add tasks.
Suggestions are tools for the model to call, not calls performed by the renderer.
"""

from __future__ import annotations

import re
from typing import Callable

from finance.domain import Json


def requirements(task: str) -> Json:
    ids = list(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", task)))
    dataset = (
        "transactions" if re.search(r"transaction|交易\s+[a-z]", task, re.I) else "obligations"
    )
    details = [{"dataset": dataset, "external_id": key} for key in ids]
    titles = list(dict.fromkeys(re.findall(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b", task)))
    # Only the explicitly supported bounded presentation objective. Other planner
    # objectives retain the general workflow and their own required parameters.
    objectives = re.findall(r"\bMIN_COST\b", task)
    scenario_count = 1
    count = re.search(
        r"\b(two|three|four|[2-9])\s+(?:separate\s+)?(?:hypothetical|alternatives|scenarios)|([两二三四])个?(?:独立)?假设",
        task,
        re.I,
    )
    if count:
        word = next(v for v in count.groups() if v)
        scenario_count = {"two": 2, "three": 3, "four": 4, "两": 2, "二": 2, "三": 3, "四": 4}.get(
            word.lower(), int(word) if word.isdigit() else 1
        )
    return {
        "details": details,
        "document_titles": titles,
        "search": bool(
            re.search(r"search|搜索|conflicting.*documents|文档.*冲突", task, re.I) or titles
        ),
        "capabilities": bool(
            re.search(
                r"platform controls|my authority|我的权限|平台控制|approve every payment|批准全部",
                task,
                re.I,
            )
        ),
        "scenario_count": scenario_count,
        "objective": objectives[0] if objectives and re.search(r"plan|计划", task, re.I) else None,
        "calculation_detail": bool(re.search(r"calculation detail|计算明细", task, re.I)),
    }


def supplemental(outputs: list[Json], full_records: Callable) -> Json:
    good = [o for o in outputs if o["output"].get("status") == "OK"]
    return {
        "outputs": good,
        "details": {d: full_records(outputs, d) for d in ("obligations", "transactions")},
        "calculations": full_records(outputs, "calculations"),
        "capabilities": next(
            (o["output"] for o in reversed(good) if o["name"] == "get_platform_capabilities"), None
        ),
        "plans": [o["output"] for o in good if o["name"] == "optimize_plan"],
    }


def record_steps(data: Json, dataset: str, query: str, predicate: Callable) -> list[Json]:
    """Use only returned IDs/pages; no guessing, bypassing ID gates or replacing a failed read."""
    rows = []
    for o in data["outputs"]:
        v = o["output"]["result"]
        if o["name"] == "list_business_records" and v.get("dataset") == dataset:
            rows.extend(v.get("records", []))
        if o["name"] == "search_documents" and dataset == "documents":
            rows.extend(v.get("hits", []))
    matches = {r["record_id"]: r for r in rows if predicate(r)}
    if not matches:
        return [{"tool": "list_business_records", "dataset": dataset, "query": query, "offset": 0}]
    result = []
    for key in matches:
        pages = [
            o["output"]["result"]
            for o in data["outputs"]
            if o["name"] == "read_business_record"
            and o["output"]["result"].get("dataset") == dataset
            and o["output"]["result"].get("record_id") == key
        ]
        last = pages[-1] if pages else {}
        result.append(
            {
                "tool": "read_business_record",
                "dataset": dataset,
                "record_id": key,
                "offset": last.get("next_offset") or 0,
            }
        )
    return result


def missing(requested: Json, data: Json) -> list[Json]:
    req, sections = requested["tasks"], requested["required_sections"]
    pending: list[Json] = []
    snap = data["snapshot"]
    if not snap:
        pending.append({"tool": "get_financial_snapshot"})
    elif not data["current"]:
        pending.append({"tool": "calculate_business_metrics", "snapshot_id": snap["snapshot_id"]})
    for target in req["details"]:
        dataset, key = target["dataset"], target["external_id"]
        if not any(r.get("external_id") == key for r in data["details"][dataset]):
            pending.extend(record_steps(data, dataset, key, lambda r: r.get("external_id") == key))
    if "history" in sections and not data["history"]:
        pending.extend(
            record_steps(
                data,
                "calculations",
                "calculate_business_metrics",
                lambda r: r.get("tool") == "calculate_business_metrics"
                and snap
                and (not data["current"] or r.get("record_id") != data["current"]["result_id"])
                and r.get("snapshot_id") != snap["snapshot_id"],
            )
        )
    if (
        req["calculation_detail"]
        and data["current"]
        and not any(
            r.get("record_id") == data["current"]["result_id"] for r in data["calculations"]
        )
    ):
        key = data["current"]["result_id"]
        pages = [
            o["output"]["result"]
            for o in data["outputs"]
            if o["name"] == "read_business_record" and o["output"]["result"].get("record_id") == key
        ]
        pending.append(
            {
                "tool": "read_business_record",
                "dataset": "calculations",
                "record_id": key,
                "offset": (pages[-1].get("next_offset") or 0) if pages else 0,
            }
        )
    if "scenario" in sections:
        distinct = {
            (
                s["result"]["forecast"]["business_health"]["forecast_scope"]["delay_days"],
                s["result"]["forecast"]["business_health"]["forecast_scope"]["receipt_bps"],
            )
            for s in data["scenarios"].values()
        }
        if len(distinct) < req["scenario_count"]:
            pending.append(
                {
                    "tool": "what_if_cashflow",
                    "remaining_alternatives": req["scenario_count"] - len(distinct),
                    "instruction": "Compute each remaining alternative with its own user-requested delay_days and receipt_bps. Do not repeat an already computed alternative.",
                }
            )
    searches = [o for o in data["outputs"] if o["name"] == "search_documents"]
    if req["search"]:
        for title in req["document_titles"] or [""]:
            seen = [
                o
                for o in searches
                if not title
                or title.casefold() in o.get("arguments", {}).get("query", "").casefold()
                or any(h.get("title") == title for h in o["output"]["result"].get("hits", []))
            ]
            if not seen:
                pending.append(
                    {
                        "tool": "search_documents",
                        "query": title or "Use the user's requested subject",
                        "offset": 0,
                    }
                )
            elif seen[-1]["output"]["result"].get("next_offset") is not None:
                pending.append(
                    {
                        "tool": "search_documents",
                        "query": seen[-1].get("arguments", {}).get("query", title),
                        "offset": seen[-1]["output"]["result"]["next_offset"],
                    }
                )
    if "documents" in sections:
        for title in req["document_titles"] or [""]:
            if not any(not title or d.get("title") == title for d in data["documents"].values()):
                pending.extend(
                    record_steps(
                        data, "documents", title, lambda r: not title or r.get("title") == title
                    )
                )
    if req["capabilities"] and not data["capabilities"]:
        pending.append({"tool": "get_platform_capabilities"})
    if req["objective"] and data["current"] and not selected_plan(requested, data):
        pending.append(
            {
                "tool": "optimize_plan",
                "objective": req["objective"],
                "instruction": "Only propose, using the observed snapshot. Never prepare_action, approve, reserve or send.",
            }
        )
    return pending


def selected_plan(requested: Json, data: Json) -> Json | None:
    snap = data["snapshot"]
    for out in reversed(data["plans"]):
        plan = out["result"].get("plan")
        if (
            plan
            and snap
            and plan.get("snapshot_id") == snap["snapshot_id"]
            and plan.get("objective") == requested["tasks"]["objective"]
            and plan.get("status") == "VALIDATED"
        ):
            return out
    return None


def report_parts(
    selection: Json, data: Json, bind: Callable, amount: Callable, tr: Callable
) -> list[str]:
    """Field identity stays attached to its label, including fully read entity details."""
    lines: list[str] = []
    sections, req = selection["sections"], data["requested"]["tasks"]
    if "details" in sections:
        for target in req["details"]:
            record = next(
                r
                for r in data["details"][target["dataset"]]
                if r.get("external_id") == target["external_id"]
            )
            key = record["record_id"]
            lines.append(
                tr("Fully read record: ", "已完整读取记录：")
                + bind(key, "record_id", key, "identifier")
            )
            for field, en, zh in (
                ("external_id", "External ID", "外部 ID"),
                ("kind", "Record kind", "记录类别"),
                ("status", "Recorded status", "记录状态"),
                ("counterparty", "Counterparty", "交易对手"),
                ("due_at", "Contractual due date", "合同到期日"),
            ):
                if field in record:
                    lines.append(tr(en, zh) + ": " + bind(record[field], field, key))
            for field, en, zh in (
                ("outstanding_minor", "Outstanding balance", "未结余额"),
                ("amount_minor", "Record amount", "记录金额"),
            ):
                if field in record:
                    lines.append(tr(en, zh) + ": " + amount(record[field], field, key))
            lines.append(
                tr(
                    "An obligation or submitted transaction is not proof of settlement. Only matched settled events can establish receipt/payment; an aggregate window cannot prove an individual bill was paid.",
                    "债权、债务或已提交交易不是结算证明。只有匹配的已结算事件才能证明收付，汇总窗口不能证明单笔账单已付款。",
                )
            )
    if "search" in sections:
        for o in data["outputs"]:
            if o["name"] != "search_documents":
                continue
            out = o["output"]
            v, key = out["result"], out["result_id"]
            lines.append(
                tr("Document search in authorized scope: ", "权限范围内的文档搜索：")
                + bind(v["total_hits"], "total_hits", key, "number")
                + tr(
                    " matching hits. This only describes this user's visible lexical search scope; zero hits cannot establish global non-existence or the content of inaccessible records.",
                    " 条匹配。结果仅描述当前用户可见的词法搜索范围；零结果不能证明全局不存在，也不能确定不可访问记录的内容。",
                )
            )
    if "capabilities" in sections:
        out = data["capabilities"]
        key = out["result_id"]
        lines.append(
            tr("Observed platform controls: ", "已读取平台控制信息：")
            + bind(key, "result_id", key, "identifier")
        )
        # This explanation reflects the actual returned capability contract, never document text.
        for control in out["result"]["human_controls"]:
            lines.append(
                bind(control["operation"], "human_controls.operation", key)
                + ": "
                + bind(control["authority"], "human_controls.authority", key)
            )
        lines.append(
            tr(
                "An ACCOUNTANT message cannot approve payments or lower the mandatory reserve. Changing reserve requires OWNER through settings. Each exact payment needs OWNER confirmation; no blanket approval is available. No change is made by this explanation.",
                "会计消息不能批准付款或降低强制准备金。准备金调整须由 OWNER 在设置中操作；每笔精确付款均需 OWNER 确认，不支持批量概括授权。本说明不会修改任何内容。",
            )
        )
    if "plan" in sections:
        out = selected_plan(data["requested"], data)
        assert out is not None
        plan, key = out["result"]["plan"], out["result_id"]
        lines.append(
            tr("Independently validated candidate for review: ", "经独立验证、待审核的候选计划：")
            + bind(plan["plan_id"], "plan.plan_id", key, "identifier")
            + "; "
            + bind(plan["objective"], "plan.objective", key)
        )
        lines.append(
            tr("Total financing cost: ", "融资总成本：")
            + amount(plan["total_cost_minor"], "plan.total_cost_minor", key)
        )
        for i, path in enumerate(plan["paths"]):
            lines.append(
                tr("Candidate forecast minimum cash: ", "候选计划预测最低现金：")
                + amount(
                    path["minimum_balance_minor"], f"plan.paths.{i}.minimum_balance_minor", key
                )
            )
            lines.append(
                tr("Candidate reserve gap: ", "候选计划准备金缺口：")
                + (
                    tr(
                        "none in this computed scenario; not a guarantee for other scenarios",
                        "该计算场景内无缺口，不保证其他场景",
                    )
                    if path["first_gap_at"] is None
                    else bind(path["first_gap_at"], f"plan.paths.{i}.first_gap_at", key)
                )
            )
        for i, action in enumerate(plan["actions"]):
            if action["kind"] != "DRAW_LOAN":
                continue
            lines.append(
                tr("Proposed loan principal: ", "拟借款本金：")
                + amount(action["amount_minor"], f"plan.actions.{i}.amount_minor", key)
                + tr("; net cash addition after fees: ", "；费用后的现金净增加：")
                + amount(action["cash_delta_minor"], f"plan.actions.{i}.cash_delta_minor", key)
            )
        lines.append(
            tr(
                "This is a candidate, not received cash or settlement. Each action still requires exact OWNER approval bound to its payload, fresh preconditions and reserves before dispatch. The report neither approves nor reserves nor sends anything.",
                "这是候选计划，不是已到账现金或已结算结果。每项操作仍需与载荷绑定的 OWNER 精确确认，发送前须重新检查前置条件及准备金。本报告不会批准、预留资金或发送操作。",
            )
        )
    return lines
