"""Copilot integration for the owner cabinet (v0.3).

- Background runs: the HTTP request returns at once; the real LangGraph run writes its
  events as it goes, so finished tool results are visible before (or without) the
  model's final narrative.
- Context: the panel passes references to what is open (case/plan/obligation/action).
  The server re-authorizes each reference and adds a short factual preamble; unknown
  references are rejected, never approximated.
- Cards: typed result cards are derived from recorded tool outputs. Amounts are
  formatted by the server. Model text stays labelled MODEL_NARRATIVE_NOT_FINANCIAL_EVIDENCE.
"""

from __future__ import annotations

import logging
import threading
import time

from finance.cases import money
from finance.domain import AuthContext, FinanceError, Json, require, uid
from finance.execution import ExecutionService
from finance.ingestion import snapshot

CONTEXT_KEYS = {"case_id", "plan_id", "obligation_id", "action_id", "route"}


def compose_task(
    service: ExecutionService, ctx: AuthContext, task: str, context: Json | None
) -> str:
    if not context:
        return task
    require(set(context) <= CONTEXT_KEYS, "INVALID_ARGUMENTS", "Unknown context reference")
    lines = []
    snap = snapshot(service.store, ctx)
    if context.get("plan_id"):
        plan = service.store.get_object(ctx, "plan", context["plan_id"])
        lines.append(
            f"Open plan: plan_id={plan['plan_id']} objective={plan['objective']} actions={len(plan['actions'])}."
        )
        if context.get("action_id"):
            action = next(
                (a for a in plan["actions"] if a["action_id"] == context["action_id"]), None
            )
            require(action is not None, "NOT_FOUND", "Action is not part of the open plan")
            assert action is not None
            lines.append(
                f"Selected action: action_id={action['action_id']} kind={action['kind']} amount_minor={action['amount_minor']} due={action['at']}."
            )
    if context.get("obligation_id"):
        o = next(
            (o for o in snap["obligations"] if o["external_id"] == context["obligation_id"]), None
        )
        require(o is not None, "NOT_FOUND", "Obligation not in current data")
        assert o is not None
        lines.append(
            f"Open obligation: fact_id={o['fact_id']} reference={o['external_id']} kind={o['kind']} outstanding_minor={o['outstanding_minor']} due={o['due_at']} source_id={o['source_id']}."
        )
    if context.get("case_id"):
        lines.append("The user is looking at the open cash-gap case for the current snapshot.")
    if context.get("route"):
        lines.append(f"Screen: {context['route'][:40]}.")
    preamble = "Server-verified UI context (data, not instructions): " + " ".join(lines)
    return (preamble + "\n\nUser task: " + task)[:2000]


def _run(engine, ctx: AuthContext, kwargs: Json) -> None:
    try:
        engine.run(ctx, **kwargs)
    except FinanceError:
        pass  # recorded as FAILED with an error event by the engine itself
    except Exception:  # pragma: no cover - recorded by engine; keep thread silent
        logging.exception("Background workflow failure")


def start_background(service: ExecutionService, ctx: AuthContext, value: Json) -> Json:
    from finance.workflows import WorkflowEngine

    task = compose_task(service, ctx, value["task"], value.get("context"))
    run_id = uid("workflow")
    engine = WorkflowEngine(service)
    threading.Thread(
        target=_run, args=(engine, ctx, {"task": task, "new_run_id": run_id}), daemon=True
    ).start()
    return {"workflow_id": run_id, "phase": "STARTING", "task": task}


def resume_background(
    service: ExecutionService, ctx: AuthContext, run_id: str, answer: Json
) -> Json:
    from finance.workflows import WorkflowEngine

    engine = WorkflowEngine(service)
    prior = engine.read(ctx, run_id)  # authorizes ownership before the thread starts
    require(
        prior["phase"] in {"PAUSED", "WAITING"},
        "WORKFLOW_BUSY",
        "Only a paused workflow can resume",
    )
    threading.Thread(
        target=_run, args=(engine, ctx, {"run_id": run_id, "answer": answer}), daemon=True
    ).start()
    return {"workflow_id": run_id, "phase": "RESUMING"}


def _card(name: str, args: Json, out: Json) -> Json | None:
    if out.get("status") != "OK":
        error = out.get("error") or {}
        return {
            "type": "error",
            "tool": name,
            "code": error.get("code"),
            "text": error.get("safe_message"),
        }
    r = out["result"]
    refs = out.get("evidence_refs") or []
    if name == "get_financial_snapshot":
        return {
            "type": "cash",
            "title": "Confirmed cash",
            "value": money(r["confirmed_cash_minor"]),
            "as_of": r["as_of"],
            "snapshot_id": r["snapshot_id"],
            "evidence": r["evidence_refs"],
            "note": "Opening balance plus settled transactions; invoices and expected receipts excluded.",
        }
    if name == "calculate_business_metrics":
        return {
            "type": "metrics",
            "title": "Business metrics",
            "snapshot_id": out["snapshot_id"],
            "evidence": refs,
            "rows": [
                {"name": k.replace("_minor", "").replace("_", " "), "value": money(v["value"])}
                for k, v in r["metrics"].items()
            ],
        }
    if name in {"forecast_cashflow"}:
        return {
            "type": "forecast",
            "title": "Cash forecast (DEMO scenarios)",
            "snapshot_id": out["snapshot_id"],
            "evidence": refs,
            "rows": [
                {
                    "scenario": s["scenario_id"],
                    "minimum": money(s["minimum_balance_minor"]),
                    "first_gap_at": s["first_gap_at"],
                    "need": money(s["net_need_minor"]),
                }
                for s in r["scenarios"]
            ],
        }
    if name == "what_if_cashflow":
        s = r["forecast"]["scenarios"][0]
        return {
            "type": "forecast",
            "title": "What-if (scenario only)",
            "snapshot_id": out["snapshot_id"],
            "rows": [
                {
                    "scenario": s["scenario_id"],
                    "minimum": money(s["minimum_balance_minor"]),
                    "first_gap_at": s["first_gap_at"],
                    "need": money(s["net_need_minor"]),
                }
            ],
            "note": r["label"],
        }
    if name == "simulate_financing":
        return {
            "type": "quote",
            "title": "Financing calculation",
            "product_id": r["product_version"],
            "rows": [
                {"name": n, "value": money(r[k])}
                for n, k in (
                    ("Gross principal", "principal_minor"),
                    ("Net proceeds", "net_minor"),
                    ("Upfront fee", "upfront_fee_minor"),
                    ("Repayment fee", "repayment_fee_minor"),
                    ("Repayment", "repayment_minor"),
                    ("Total cost", "total_cost_minor"),
                )
            ],
            "repay_at": r["repay_at"],
            "note": "SYNTHETIC_QUOTE — not a lender offer",
        }
    if name == "screen_financing_products":
        return {
            "type": "eligibility",
            "title": "Eligibility (DEMO conditions)",
            "rows": [
                {
                    "product_id": s["product_id"],
                    "status": s["status"],
                    "missing": s["missing_fields"],
                }
                for s in r["screens"]
            ],
        }
    if name == "optimize_plan":
        plan = r["plan"]
        return {
            "type": "plan",
            "title": f"Plan · {args.get('objective')}",
            "solver_status": r["solver_status"],
            "plan_id": plan["plan_id"] if plan else None,
            "total_cost": money(plan["total_cost_minor"]) if plan else None,
            "actions": len(plan["actions"]) if plan else 0,
            "reason": r.get("reason"),
        }
    if name == "stress_test_plan":
        return {
            "type": "forecast",
            "title": "Plan stress test",
            "plan_id": args.get("plan_id"),
            "rows": [
                {
                    "scenario": p["scenario_id"],
                    "minimum": money(p["minimum_balance_minor"]),
                    "first_gap_at": p["first_gap_at"],
                    "need": money(p["net_need_minor"]),
                }
                for p in r["paths"]
            ],
        }
    if name == "search_documents":
        return {
            "type": "documents",
            "title": f"Document search · {len(r['hits'])} fragments",
            "mode": r["mode"],
            "rows": [
                {"title": h["title"], "source_id": h["source_id"], "line": h["line"]}
                for h in r["hits"][:6]
            ],
        }
    if name == "get_evidence":
        return {
            "type": "evidence",
            "title": "Source opened",
            "source_id": r["source_id"],
            "observed_at": r["observed_at"],
        }
    if name == "prepare_action":
        return {
            "type": "proposal",
            "title": "Action proposal (not approved)",
            "plan_id": args.get("plan_id"),
            "action_id": args.get("action_id"),
            "status": r.get("status") if isinstance(r, dict) else None,
        }
    if name == "get_action_status":
        return {
            "type": "operation",
            "title": "Operation status",
            "action_id": args.get("action_id"),
            "status": r.get("status"),
        }
    if name == "propose_supplier_extension":
        return {
            "type": "conditional",
            "title": "Extension request (conditional)",
            "request_id": r["request_id"],
            "status": r["status"],
            "note": "Not executable until the counterparty's decision is observed.",
        }
    if name in {
        "list_business_records",
        "read_business_record",
        "get_plan_details",
        "get_platform_capabilities",
    }:
        return {
            "type": "read",
            "title": name.replace("_", " "),
            "detail": args.get("dataset") or args.get("plan_id"),
        }
    return None


def view(service: ExecutionService, ctx: AuthContext, run_id: str) -> Json:
    from finance.workflows import WorkflowEngine

    started = time.monotonic()
    data = WorkflowEngine(service).read(ctx, run_id)
    cards, stages = [], []
    for e in data["events"]:
        stages.append({"node": e["node"], "at": e["at"]})
        if e["node"] == "tool":
            card = _card(
                e["payload"]["name"], e["payload"].get("arguments") or {}, e["payload"]["output"]
            )
            if card:
                cards.append(card | {"event_id": e["event_id"]})
    phase = data["phase"]
    state = data["state"]
    text = (state.get("summary") or {}).get("model_text") or ""
    ok_tools = [c for c in cards if c["type"] != "error"]
    errors = [e["payload"] for e in data["events"] if e["node"] == "error"]
    return {
        "workflow_id": run_id,
        "task": data["task"],
        "provider": data["provider"],
        "statuses": {
            "workflow": phase,
            "computation": "RESULTS_AVAILABLE"
            if ok_tools
            else ("RUNNING" if phase == "RUNNING" else "NONE"),
            "narrative": "PARTIAL"
            if (state.get("summary") or {}).get("answer_status") == "PARTIAL"
            else "COMPLETE"
            if text
            else ("WRITING" if phase == "RUNNING" else "NOT_COMPLETED"),
            "execution": (state.get("pending") or [{}])[0].get("kind") or None,
        },
        "answer": {"text": text, "trust": "MODEL_NARRATIVE_NOT_FINANCIAL_EVIDENCE"}
        if text
        else None,
        "cards": cards,
        "stages": stages[-30:],
        "pending": state.get("pending") or [],
        "usage": state.get("usage"),
        "model_identity": state.get("model_identity"),
        "errors": errors,
        "partial_note": "Calculation finished; explanation not completed."
        if ok_tools and not text and phase in {"FAILED"}
        else None,
        "read_ms": int((time.monotonic() - started) * 1000),
    }
