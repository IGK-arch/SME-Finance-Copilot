"""Deterministic calculations, DEMO scenarios and bounded integer planning."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from finance.domain import (
    MAX_ANNUALIZED_COST_BPS,
    Json,
    annualized_cost_bps,
    digest,
    minor,
    rate_charge,
    require,
    utc,
)

CALCULATION_VERSION = "compute-v2"


def shift(timestamp: str, days: int) -> str:
    return utc((datetime.fromisoformat(utc(timestamp)) + timedelta(days=days)).isoformat())


def metrics(snap: Json) -> Json:
    obligations = snap["obligations"]
    values = {
        "confirmed_cash_minor": snap["confirmed_cash_minor"],
        "receivables_minor": sum(
            o["outstanding_minor"] for o in obligations if o["kind"] == "RECEIVABLE"
        ),
        "payables_minor": sum(
            o["outstanding_minor"] for o in obligations if o["kind"] == "PAYABLE"
        ),
        "overdue_minor": sum(
            o["outstanding_minor"] for o in obligations if o["due_at"] < snap["as_of"]
        ),
        "reserve_minor": snap["policy"]["reserve_minor"],
    }
    return {
        "metrics": {
            name: {
                "metric_id": digest([snap["snapshot_id"], name])[:32],
                "value": minor(amount),
                "unit": "minor_units",
                "currency": "CNY",
                "snapshot_id": snap["snapshot_id"],
                "calculation_version": CALCULATION_VERSION,
                "evidence_refs": snap["evidence_refs"],
            }
            for name, amount in values.items()
        },
        "pnl": {"status": "INSUFFICIENT_DATA", "reason": "A bank statement is not a P&L"},
    }


def scenarios() -> list[Json]:
    return [
        {
            "scenario_id": "f0",
            "delay_days": 0,
            "provenance": "DEMO",
            "calibration_status": "UNCALIBRATED",
        },
        {
            "scenario_id": "delay_5",
            "delay_days": 5,
            "provenance": "DEMO",
            "calibration_status": "UNCALIBRATED",
        },
        {
            "scenario_id": "delay_25",
            "delay_days": 25,
            "provenance": "DEMO_STRESS",
            "calibration_status": "UNCALIBRATED",
        },
    ]


def obligation_flows(
    snap: Json,
    scenario: Json,
    include_payables: bool = True,
    assigned_receivables: Iterable[str] = (),
) -> list[Json]:
    assigned = set(assigned_receivables)
    require(
        type(scenario.get("delay_days")) is int and 0 <= scenario["delay_days"] <= 365,
        "INVALID_SCENARIO",
        "Scenario delay must be 0–365 days",
    )
    for key in ("receipt_bps",):
        require(
            type(scenario.get(key, 10000)) is int and 0 <= scenario.get(key, 10000) <= 10000,
            "INVALID_SCENARIO",
            "Receipt fraction must be integer basis points",
        )
    require(
        isinstance(scenario.get("customer_shocks", {}), dict),
        "INVALID_SCENARIO",
        "Customer shocks must be an object",
    )
    require(
        isinstance(scenario.get("obligation_shocks", {}), dict),
        "INVALID_SCENARIO",
        "Obligation shocks must be an object keyed by obligation reference",
    )
    flows: list[Json] = []
    for o in snap["obligations"]:
        if not o["outstanding_minor"] or o["external_id"] in assigned:
            continue
        when = (
            max(o["due_at"], shift(snap["as_of"], 1))
            if o["due_at"] <= snap["as_of"]
            else o["due_at"]
        )
        if o["kind"] == "RECEIVABLE":
            # A per-obligation shock (one invoice) takes precedence over a per-customer one.
            shock = scenario.get("obligation_shocks", {}).get(o["external_id"]) or scenario.get(
                "customer_shocks", {}
            ).get(o["counterparty"], {})
            delay = shock.get("delay_days", scenario["delay_days"])
            bps = shock.get("receipt_bps", scenario.get("receipt_bps", 10000))
            require(
                type(delay) is int and 0 <= delay <= 365 and type(bps) is int and 0 <= bps <= 10000,
                "INVALID_SCENARIO",
                "Invalid customer shock",
            )
            when = shift(when, delay)
            amount = o["outstanding_minor"] * bps // 10000
            remainder = o["outstanding_minor"] - amount
            tail_days = scenario.get("remainder_delay_days")
            if remainder and tail_days is not None:
                require(
                    type(tail_days) is int and 1 <= tail_days <= 365,
                    "INVALID_SCENARIO",
                    "Remainder delay must be 1–365 days",
                )
                flows.append(
                    {
                        "at": shift(when, tail_days),
                        "amount_minor": remainder,
                        "reference": o["external_id"] + "_remainder",
                        "counterparty": o["counterparty"],
                        "kind": "EXPECTED_RECEIPT",
                        "source_id": o["source_id"],
                    }
                )
        elif include_payables:
            amount = -o["outstanding_minor"]
        else:
            continue
        flows.append(
            {
                "at": when,
                "amount_minor": amount,
                "reference": o["external_id"],
                "counterparty": o["counterparty"],
                "kind": "EXPECTED_RECEIPT" if o["kind"] == "RECEIVABLE" else "PAYABLE",
                "source_id": o["source_id"],
            }
        )
    return flows


def trajectory(cash: int, flows: list[Json], reserve: int, *, as_of: str | None = None) -> Json:
    # Conservative tie ordering. Earlier times can never borrow later receipts.
    balance = minimum = minor(cash)
    points: list[Json] = []
    first_gap = utc(as_of) if as_of is not None and balance < reserve else None
    for f in sorted(flows, key=lambda f: (f["at"], f["amount_minor"] >= 0, f["reference"])):
        balance = minor(balance + f["amount_minor"])
        minimum = min(minimum, balance)
        if balance < reserve and first_gap is None:
            first_gap = f["at"]
        points.append(f | {"balance_minor": balance})
    return {
        "points": points,
        "minimum_balance_minor": minimum,
        "final_balance_minor": balance,
        "first_gap_at": first_gap,
        "net_need_minor": max(0, reserve - minimum),
    }


def forecast(
    snap: Json,
    scenario_set: list[Json] | None = None,
    additional_flows: list[Json] | None = None,
    residual_flows: list[Json] | None = None,
) -> Json:
    require(
        scenario_set is None
        or (
            isinstance(scenario_set, list)
            and 0 < len(scenario_set) <= 10
            and all(isinstance(s, dict) for s in scenario_set)
        ),
        "INVALID_SCENARIO",
        "Use one to ten scenario objects",
    )
    result = []
    for scenario in scenario_set or scenarios():
        known_instances = {o["external_id"] for o in snap["obligations"]}
        residual = [f for f in residual_flows or [] if f["reference"] not in known_instances]
        flows = obligation_flows(snap, scenario) + (additional_flows or []) + residual
        result.append(
            scenario
            | trajectory(
                snap["confirmed_cash_minor"],
                flows,
                snap["policy"]["reserve_minor"],
                as_of=snap["as_of"],
            )
        )
    return {
        "snapshot_id": snap["snapshot_id"],
        "calculation_version": CALCULATION_VERSION,
        "forecast_id": "forecast_"
        + digest([CALCULATION_VERSION, snap["snapshot_id"], scenario_set, additional_flows])[:24],
        "ui_horizon_days": 30,
        "computed_through": max(
            (p["at"] for r in result for p in r["points"]), default=snap["as_of"]
        ),
        "scenarios": result,
        "label": "DEMO scenario outcomes; not bankruptcy probabilities",
        "assumptions": [
            "No residual cashflow without supplied evidence",
            "Sparse history: calendar fallback",
        ],
        "evidence_refs": snap["evidence_refs"],
    }


def merchant_bridge(
    sales_minor: int, refunds_minor: int, fee_minor: int, bank_settlement_minor: int
) -> Json:
    for value in (sales_minor, refunds_minor, fee_minor, bank_settlement_minor):
        minor(value)
        require(value >= 0, "INVALID_MONEY", "Merchant bridge values must be nonnegative")
    expected = sales_minor - refunds_minor - fee_minor
    return {
        "sales_net_of_refunds_minor": sales_minor - refunds_minor,
        "fee_minor": fee_minor,
        "bank_cash_minor": bank_settlement_minor,
        "bridge_difference_minor": expected - bank_settlement_minor,
        "revenue_minor": sales_minor - refunds_minor,
        "settlement_is_sale": False,
        "provenance": "DEMO bridge arithmetic, no merchant provider integration",
    }


def catalog(origin: str) -> list[Json]:
    base: Json = {
        "schema_version": 1,
        "currency": "CNY",
        "min_minor": 100000,
        "max_minor": 12000000,
        "grid_minor": 100000,
        "legal_forms": ["LIMITED_COMPANY"],
        "jurisdiction": "CN",
        "required_documents": ["synthetic_statement"],
        "review_status": "PUBLISHED_DEMO",
        "source": "DEMO product specification v1",
        "rate": "0",
        "day_count": "ACT/365",
        "rounding": "ROUND_HALF_UP",
        "repayment_fee_minor": 100000,
        "expires_at": shift(origin, 3),
        "repay_at": shift(origin, 30),
        "disburse_at": shift(origin, 1),
    }
    return [
        base
        | {
            "product_id": "demo_bridge_v1",
            "name": "DEMO bridge",
            "upfront_fee_minor": 100000,
            "repayment_fee_minor": 0,
        },
        base
        | {
            "product_id": "demo_late_v1",
            "name": "DEMO late low-fee",
            "upfront_fee_minor": 0,
            "repayment_fee_minor": 0,
            "disburse_at": shift(origin, 9),
        },
    ]


def eligibility(profile: Json, item: Json) -> Json:
    conditions: list[Json] = []
    for field, expected in (
        ("legal_form", item["legal_forms"]),
        ("jurisdiction", [item["jurisdiction"]]),
    ):
        actual = profile.get(field)
        conditions.append(
            {
                "field": field,
                "status": "UNKNOWN" if actual is None else "PASS" if actual in expected else "FAIL",
                "source": item["source"],
            }
        )
    documents = profile.get("documents")
    conditions.append(
        {
            "field": "documents",
            "status": "UNKNOWN"
            if documents is None
            else "PASS"
            if set(item["required_documents"]) <= set(documents)
            else "FAIL",
            "source": item["source"],
        }
    )
    status = (
        "FAIL"
        if any(c["status"] == "FAIL" for c in conditions)
        else "UNKNOWN"
        if any(c["status"] == "UNKNOWN" for c in conditions)
        else "PASS"
    )
    return {
        "product_id": item["product_id"],
        "status": status,
        "conditions": conditions,
        "missing_fields": [c["field"] for c in conditions if c["status"] == "UNKNOWN"],
        "meaning": "Known DEMO conditions only; not lender approval",
    }


def financing(item: Json, principal: int) -> Json:
    require(
        item.get("review_status") == "PUBLISHED_DEMO",
        "UNSUPPORTED_PRODUCT_TERMS",
        "Reviewed DEMO terms required",
    )
    required = {
        "rate",
        "day_count",
        "rounding",
        "upfront_fee_minor",
        "repayment_fee_minor",
        "repay_at",
        "disburse_at",
    }
    require(
        required <= item.keys()
        and item["day_count"] == "ACT/365"
        and item["rounding"] == "ROUND_HALF_UP",
        "UNSUPPORTED_PRODUCT_TERMS",
        "Complete supported terms required",
    )
    minor(principal, positive=True)
    require(
        item["min_minor"] <= principal <= item["max_minor"],
        "INVALID_AMOUNT",
        "Amount outside product range",
    )
    days = (
        datetime.fromisoformat(item["repay_at"]) - datetime.fromisoformat(item["disburse_at"])
    ).days
    interest = rate_charge(principal, item["rate"], days)
    net = minor(principal - item["upfront_fee_minor"])
    require(net > 0 and days > 0, "UNSUPPORTED_PRODUCT_TERMS", "Invalid timing/net proceeds")
    repayment = minor(principal + interest + item["repayment_fee_minor"])
    annual_bps = annualized_cost_bps(repayment - net, net, days)
    return {
        "quote_id": "quote_" + digest([item, principal])[:24],
        "product_version": item["product_id"],
        "principal_minor": principal,
        "net_minor": net,
        "interest_minor": interest,
        "upfront_fee_minor": item["upfront_fee_minor"],
        "repayment_fee_minor": item["repayment_fee_minor"],
        "repayment_minor": repayment,
        "total_cost_minor": repayment - net,
        "term_days": days,
        "annualized_cost_bps": annual_bps,
        "within_cost_cap": annual_bps <= MAX_ANNUALIZED_COST_BPS,
        "disburse_at": item["disburse_at"],
        "repay_at": item["repay_at"],
        "expires_at": item["expires_at"],
        "binding_status": "SYNTHETIC_QUOTE",
        "residual_principal_minor": 0,
        "terms": item,
    }


def factoring_flows(receivable: Json, advance_minor: int, fee_minor: int, at: str) -> Json:
    """One fully specified DEMO non-recourse assignment; other terms unsupported."""
    require(
        0 < advance_minor <= receivable["outstanding_minor"] and 0 <= fee_minor < advance_minor,
        "UNSUPPORTED_PRODUCT_TERMS",
        "Invalid assignment terms",
    )
    return {
        "assigned_receivables": [receivable["external_id"]],
        "flows": [
            {"at": at, "amount_minor": advance_minor - fee_minor, "reference": "factoring_advance"},
            {
                "at": receivable["due_at"],
                "amount_minor": receivable["outstanding_minor"] - advance_minor,
                "reference": "factoring_final",
            },
        ],
        "fee_minor": fee_minor,
        "provenance": "DEMO",
    }


def dag_valid(actions: list[Json]) -> bool:
    refs = {a["action_id"]: set(a["dependencies"]) for a in actions}
    if len(refs) != len(actions) or any(not deps <= refs.keys() for deps in refs.values()):
        return False
    done: set[str] = set()
    while len(done) < len(refs):
        ready = {a for a, deps in refs.items() if a not in done and deps <= done}
        if not ready:
            return False
        done |= ready
    return True


def candidate(snap: Json, quote: Json | None, objective: str) -> Json:
    identifier = "plan_" + digest([snap["snapshot_id"], quote, objective])[:24]
    actions: list[Json] = []
    fund_id = identifier + "_fund"
    if quote:
        actions.append(
            {
                "action_id": fund_id,
                "kind": "DRAW_LOAN",
                "at": quote["disburse_at"],
                "amount_minor": quote["principal_minor"],
                "cash_delta_minor": quote["net_minor"],
                "beneficiary_version_id": "lender_v1",
                "obligation_id": None,
                "quote": quote,
                "dependencies": [],
                "completion_predicate": "SETTLED_AND_RECONCILED",
            }
        )
    for o in snap["obligations"]:
        if o["kind"] != "PAYABLE" or o["outstanding_minor"] == 0:
            continue
        is_debt = o["provider"] == "sandbox" and "loan_quote" in o
        action = {
            "action_id": identifier + "_" + digest([o["provider"], o["external_id"]])[:12],
            "kind": "REPAY_LOAN" if is_debt else "PAY_OBLIGATION",
            "at": o["due_at"],
            "amount_minor": o["outstanding_minor"],
            "cash_delta_minor": -o["outstanding_minor"],
            "obligation_id": o["external_id"],
            "obligation_provider": o["provider"],
            "beneficiary_version_id": o["beneficiary_version"],
            "dependencies": [fund_id] if quote and o["due_at"] >= quote["disburse_at"] else [],
            "completion_predicate": "SETTLED_AND_RECONCILED",
        }
        if is_debt:
            action["quote"] = o["loan_quote"]
        actions.append(action)
    if quote:
        actions.append(
            {
                "action_id": identifier + "_repay",
                "kind": "REPAY_LOAN",
                "at": quote["repay_at"],
                "amount_minor": quote["repayment_minor"],
                "cash_delta_minor": -quote["repayment_minor"],
                "beneficiary_version_id": "lender_v1",
                "obligation_id": fund_id + "_debt",
                "quote": quote,
                "dependencies": [fund_id],
                "completion_predicate": "SETTLED_AND_RECONCILED",
            }
        )
    return {
        "schema_version": 1,
        "plan_id": identifier,
        "plan_version": 1,
        "snapshot_id": snap["snapshot_id"],
        "policy_version": snap["policy"]["version"],
        "objective": objective,
        "status": "DRAFT",
        "solver_status": "NOT_RUN",
        "quote": quote,
        "actions": sorted(actions, key=lambda a: (a["at"], a["kind"])),
        "total_cost_minor": quote["total_cost_minor"] if quote else 0,
        "data_mode": "synthetic",
        "expires_at": shift(snap["as_of"], 3),
        "constraints_digest": digest([snap["policy"], snap["obligations"]]),
        "evidence_refs": snap["evidence_refs"],
    }


def plan_trajectories(snap: Json, plan: Json, scenario_set: list[Json]) -> list[Json]:
    flows = [
        {"at": a["at"], "amount_minor": a["cash_delta_minor"], "reference": a["action_id"]}
        for a in plan["actions"]
    ]
    return [
        s
        | trajectory(
            snap["confirmed_cash_minor"],
            obligation_flows(snap, s, False) + flows,
            snap["policy"]["reserve_minor"],
            as_of=snap["as_of"],
        )
        for s in scenario_set
    ]


def optimize(
    snap: Json,
    objective: str = "MIN_COST",
    items: list[Json] | None = None,
    scenario_set: list[Json] | None = None,
    search_budget: int = 10000,
    reserve_target_minor: int | None = None,
) -> Json:
    from finance.planner import OBJECTIVES, objective_scope

    require(objective in OBJECTIVES, "INVALID_OBJECTIVE", "Unsupported planning objective")
    require(
        type(search_budget) is int and 0 <= search_budget <= 100000,
        "INVALID_ARGUMENTS",
        "Invalid search budget",
    )
    scenario_set, floor = objective_scope(snap, objective, scenario_set, reserve_target_minor)
    options: list[Json | None] = [None]
    screens = []
    for item in items if items is not None else catalog(snap["as_of"]):
        screen = eligibility(snap["profile"], item)
        screens.append(screen)
        if screen["status"] == "PASS" and objective != "NO_NEW_DEBT":
            for principal in range(item["min_minor"], item["max_minor"] + 1, item["grid_minor"]):
                if principal > item["upfront_fee_minor"]:
                    offer = financing(item, principal)
                    if offer["within_cost_cap"]:
                        options.append(offer)
    best: Json | None = None
    best_key: tuple[int, ...] | None = None
    checked = 0
    for quote in options:
        if checked >= search_budget:
            break
        checked += 1
        plan = candidate(snap, quote, objective)
        paths = plan_trajectories(snap, plan, scenario_set)
        low = min(p["minimum_balance_minor"] for p in paths)
        if low < floor or snap["quality_flags"]:
            continue
        principal = quote["principal_minor"] if quote else 0
        key = (plan["total_cost_minor"], principal)
        if best_key is None or key < best_key:
            best, best_key = plan, key
            best["paths"] = paths
    exhausted = checked == len(options)
    status = (
        "OPTIMAL"
        if best and exhausted
        else "FEASIBLE"
        if best
        else "INFEASIBLE"
        if exhausted
        else "UNKNOWN"
    )
    result: Json = {
        "solver_status": status,
        "plan": best,
        "candidates_checked": checked,
        "candidate_count": len(options),
        "search_budget": search_budget,
        "solver_version": "exact-enumeration-v1",
        "amount_grid_minor": 100000,
        "scenario_set": scenario_set,
        "screens": screens,
        "reason": None
        if best
        else "No plan proven within supplied cash, timing, reserve, quality and product grid",
        "scope": "Finite DEMO candidate set; no claim of real-world optimality",
    }
    if best:
        from finance.validation import validate_plan

        validation = validate_plan(snap, best, scenario_set)
        require(validation["valid"], "MODEL_INVALID", "Independent plan validation failed")
        best.update(
            {
                "status": "VALIDATED",
                "solver_status": status,
                "validation": validation,
                "stress_paths": plan_trajectories(snap, best, scenarios()),
            }
        )
    return result
