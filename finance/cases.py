"""Owner-facing read models for the main path (v0.3).

problem -> cause -> options -> selection -> exact review -> execution -> reconciled result.

These are projections over the existing kernel. They never compute balances, approve,
reserve or send on their own: snapshot/forecast/planner/validator/ExecutionService stay
the only financial authorities. Case history is an append-only event log in `objects`
(kind='case_event'), so no migration or second ledger is introduced.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from finance.compute import forecast, plan_trajectories, scenarios, trajectory, obligation_flows
from finance.domain import (
    MAX_ANNUALIZED_COST_BPS,
    AuthContext,
    FinanceError,
    Json,
    annualized_cost_bps,
    digest,
    now,
    require,
    uid,
)
from finance.execution import ExecutionService
from finance.ingestion import snapshot

RULE_VERSION = "alerts-v1"
WRITE_ROLES = {"OWNER", "ACCOUNTANT"}
ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,160}$")


def annual_cost(q: Json) -> Json:
    """Effective yearly cost on net proceeds, shown next to flat-fee amounts.
    Recomputed for quotes stored before the cost cap existed.
    """
    bps = q.get("annualized_cost_bps")
    if bps is None:
        days = (
            datetime.fromisoformat(q["repay_at"]) - datetime.fromisoformat(q["disburse_at"])
        ).days
        bps = annualized_cost_bps(q["total_cost_minor"], q["net_minor"], days)
    return {
        "bps": bps,
        "display": f"{bps // 100}.{bps % 100:02d}% per year",
        "within_cap": bps <= MAX_ANNUALIZED_COST_BPS,
        "cap_display": f"{MAX_ANNUALIZED_COST_BPS // 100}% per year",
    }


def cny(amount: int) -> str:
    """Exact server-side display; integers only, never float arithmetic."""
    sign = "\u2212" if amount < 0 else ""  # true minus: no line break inside the amount
    value = abs(int(amount))
    return f"{sign}CNY {value // 100:,}.{value % 100:02d}"


def money(amount: int) -> Json:
    # The string keeps exactness for clients that cannot hold int64 safely.
    return {"minor": int(amount), "minor_str": str(int(amount)), "display": cny(amount)}


def _labels(db, tenant: str) -> dict[str, str]:
    names = {}
    for row in db.execute(
        "SELECT logical_id,payload FROM beneficiaries WHERE tenant_id=?", (tenant,)
    ):
        names[row["logical_id"]] = json.loads(row["payload"]).get("name", row["logical_id"])
    return names


def party(names: dict[str, str], counterparty: str) -> str:
    return names.get(counterparty) or counterparty.replace("_", " ").title()


def _actions(db, tenant: str) -> list[Json]:
    rows = []
    for r in db.execute(
        "SELECT action_id,status,provider_ref,payload FROM actions WHERE tenant_id=?", (tenant,)
    ):
        item = dict(r)
        item["payload"] = json.loads(item["payload"])
        rows.append(item)
    return rows


def _objects(db, tenant: str, kind: str) -> list[Json]:
    return [
        json.loads(r[0])
        for r in db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind=? ORDER BY created_at",
            (tenant, kind),
        )
    ]


# ---------------------------------------------------------------- cause / drivers


def drivers(snap: Json, scenario: Json, names: dict[str, str]) -> Json:
    """Which observed flows produce the first breach of the hard reserve (evidence-linked)."""
    flows = obligation_flows(snap, scenario)
    path = trajectory(snap["confirmed_cash_minor"], flows, snap["policy"]["reserve_minor"])
    gap = path["first_gap_at"]
    if gap is None:
        return {"first_gap_at": None, "outflows": [], "late_inflows": [], "path": path}
    before = [p for p in path["points"] if p["at"] <= gap]
    outflows = [
        {
            "reference": p["reference"],
            "party": party(names, p["counterparty"]),
            "at": p["at"],
            "amount": money(-p["amount_minor"]),
            "source_id": p["source_id"],
            "protected": any(
                o["external_id"] == p["reference"] and o["protected"] for o in snap["obligations"]
            ),
        }
        for p in before
        if p["amount_minor"] < 0
    ]
    late = [
        {
            "reference": p["reference"],
            "party": party(names, p["counterparty"]),
            "expected_at": p["at"],
            "amount": money(p["amount_minor"]),
            "source_id": p["source_id"],
            "status": "EXPECTED_NOT_SETTLED",
        }
        for p in path["points"]
        if p["amount_minor"] > 0 and p["at"] > gap
    ]
    return {"first_gap_at": gap, "outflows": outflows, "late_inflows": late, "path": path}


def explain_infeasible(snap: Json, objective: str, result: Json) -> list[Json]:
    """Deterministic diagnostic checks; explicitly NOT a minimal infeasibility proof."""
    reasons: list[Json] = []
    if snap["quality_flags"]:
        return [
            {
                "code": "DATA_REVIEW_REQUIRED",
                "text": "Imported data needs review before any plan can be executed.",
                "detail": snap["quality_flags"],
            }
        ]
    floor = result.get("liquidity_floor_minor", snap["policy"]["reserve_minor"])
    scope = result.get("scenario_set") or [scenarios()[0]]
    shortfalls: dict[tuple[int, str], list[str]] = {}
    for scenario in scope:
        flows = obligation_flows(snap, scenario)
        path = trajectory(snap["confirmed_cash_minor"], flows, floor)
        if path["first_gap_at"]:
            shortfalls.setdefault((path["minimum_balance_minor"], path["first_gap_at"]), []).append(
                scenario["scenario_id"]
            )
    for (low, at), ids in shortfalls.items():
        reasons.append(
            {
                "code": "SHORTFALL_WITHOUT_FINANCING",
                "scenario_ids": ids,
                "text": f"Without new money cash falls to {cny(low)} (floor {cny(floor)}) on {_day(at)} "
                f"in {', '.join(ids)}.",
                "at": at,
                "shortfall": money(floor - low),
            }
        )
    if objective == "NO_NEW_DEBT":
        return reasons
    first_gap = min((r["at"] for r in reasons if r.get("at")), default=None)
    for screen in result.get("screens", []):
        product = next(
            (
                p
                for p in snap.get("financing_products") or []
                if p["product_id"] == screen["product_id"]
            ),
            None,
        )
        if product is None:
            from finance.compute import catalog

            product = next(
                (p for p in catalog(snap["as_of"]) if p["product_id"] == screen["product_id"]), None
            )
        name = product["name"] if product else screen["product_id"]
        if screen["status"] != "PASS":
            reasons.append(
                {
                    "code": "ELIGIBILITY_" + screen["status"],
                    "product_id": screen["product_id"],
                    "text": f"{name}: eligibility {screen['status']}"
                    + (
                        f" (missing {', '.join(screen['missing_fields'])})"
                        if screen["missing_fields"]
                        else ""
                    ),
                }
            )
            continue
        if product is None:
            continue
        if product["expires_at"] < snap["as_of"]:
            reasons.append(
                {
                    "code": "QUOTE_EXPIRED",
                    "product_id": product["product_id"],
                    "text": f"{name}: offer expired.",
                }
            )
            continue
        if first_gap and product["disburse_at"] > first_gap:
            reasons.append(
                {
                    "code": "FUNDING_ARRIVES_LATE",
                    "product_id": product["product_id"],
                    "text": f"{name}: money arrives after the first gap.",
                    "disburse_at": product["disburse_at"],
                    "gap_at": first_gap,
                }
            )
            continue
        from finance.compute import candidate, financing

        quote = financing(product, product["max_minor"])
        plan = candidate(snap, quote, objective)
        for path in plan_trajectories(snap, plan, scope):
            if path["minimum_balance_minor"] < floor:
                after_repay = path["first_gap_at"] and path["first_gap_at"] >= quote["repay_at"]
                reasons.append(
                    {
                        "code": "REPAYMENT_CREATES_GAP" if after_repay else "AMOUNT_INSUFFICIENT",
                        "product_id": product["product_id"],
                        "scenario_id": path["scenario_id"],
                        "text": (
                            f"{name}: repayment on the due date pushes cash to "
                            f"{cny(path['minimum_balance_minor'])} in {path['scenario_id']}."
                        )
                        if after_repay
                        else f"{name}: even the maximum {cny(product['max_minor'])} leaves cash at "
                        f"{cny(path['minimum_balance_minor'])} in {path['scenario_id']}.",
                        "at": path["first_gap_at"],
                    }
                )
                break
    return reasons


# ---------------------------------------------------------------- alerts


def alerts(
    snap: Json,
    fc: Json,
    actions: list[Json],
    approvals: list[Json],
    company: Json,
    recon: Json | None,
    names: dict[str, str],
) -> list[Json]:
    items: list[Json] = []

    def add(
        kind: str,
        subject: str,
        severity: str,
        title: str,
        detail: str,
        route: str,
        evidence: list[str] | None = None,
    ) -> None:
        items.append(
            {
                "alert_id": "alert_"
                + digest([company["tenant_id"], kind, subject, RULE_VERSION])[:24],
                "type": kind,
                "subject": subject,
                "severity": severity,
                "title": title,
                "detail": detail,
                "route": route,
                "evidence": evidence or [],
                "business_as_of": snap["as_of"],
                "rule_version": RULE_VERSION,
            }
        )

    for a in actions:
        if a["status"] == "UNKNOWN":
            add(
                "UNKNOWN_PAYMENT",
                a["action_id"],
                "critical",
                "Checking payment status — do not send again",
                f"{a['payload']['kind']} {cny(a['payload']['amount_minor'])}: the response was lost. Funds stay reserved until the original operation is found.",
                f"#activity/{a['action_id']}",
            )
        elif a["status"] in {"RESERVED", "SUBMITTED"}:
            add(
                "IN_FLIGHT",
                a["action_id"],
                "info",
                "Operation in progress",
                f"{a['payload']['kind']} {cny(a['payload']['amount_minor'])} is {a['status'].lower()}; waiting for the sandbox to confirm.",
                f"#activity/{a['action_id']}",
            )
    if company["stopped"]:
        add(
            "SENDS_STOPPED",
            "kill_switch",
            "warning",
            "New sends are stopped",
            "Status checks and reconciliation still run. Resume only after reviewing the reason.",
            "#settings",
        )
    if recon and not recon.get("matched", True):
        add(
            "RECONCILIATION_MISMATCH",
            recon["reconciliation_id"],
            "critical",
            "Cash does not reconcile",
            f"Local {cny(recon['local_cash_minor'])} vs sandbox {cny(recon['provider_cash_minor'])}. New sends were stopped.",
            "#activity",
        )
    if snap["quality_flags"]:
        add(
            "DATA_REVIEW",
            ",".join(sorted(snap["quality_flags"])),
            "warning",
            "Forecast needs data review",
            "Some imported rows are unresolved, so plans and payments are blocked.",
            "#documents",
        )
    for o in snap["obligations"]:
        if o["outstanding_minor"] and o["due_at"] < snap["as_of"]:
            payable = o["kind"] == "PAYABLE"
            add(
                "OVERDUE_" + o["kind"],
                o["fact_id"],
                "critical" if payable and o["protected"] else "warning",
                ("Overdue payment: " if payable else "Overdue receipt: ")
                + party(names, o["counterparty"]),
                f"{cny(o['outstanding_minor'])} was due {_day(o['due_at'])}"
                + (" (protected obligation)." if o["protected"] else "."),
                "#money",
                [o["source_id"]],
            )
    base = fc["scenarios"][0]
    if base["first_gap_at"]:
        add(
            "CASH_GAP",
            base["first_gap_at"][:10],
            "critical",
            "Cash falls below your reserve",
            f"Need {cny(base['net_need_minor'])} by {_day(base['first_gap_at'])} to keep the {cny(snap['policy']['reserve_minor'])} reserve.",
            "#case",
            snap["evidence_refs"],
        )
    else:
        stressed = [s for s in fc["scenarios"][1:] if s["first_gap_at"]]
        if stressed:
            s = stressed[0]
            add(
                "STRESS_GAP",
                s["scenario_id"],
                "warning",
                "Gap if a customer pays late",
                f"In scenario {s['scenario_id']} cash falls to {cny(s['minimum_balance_minor'])} on {_day(s['first_gap_at'])}.",
                "#case",
            )
    for p in snap.get("financing_products") or []:
        if snap["as_of"] < p["expires_at"] <= _plus_day(snap["as_of"]):
            add(
                "OFFER_EXPIRING",
                p["product_id"],
                "info",
                f"{p['name']} offer expires soon",
                f"Offer valid until {p['expires_at'][:16].replace('T', ' ')} UTC.",
                "#plans",
            )
    for ap in approvals:
        if not ap["revoked"] and snap["as_of"] < ap["expires_at"] <= _plus_day(snap["as_of"]):
            if not any(
                a["payload"].get("required_approval_id") == ap["approval_id"] for a in actions
            ):
                add(
                    "APPROVAL_EXPIRING",
                    ap["approval_id"],
                    "info",
                    "An approval expires soon",
                    "Approved but not sent; it must be re-approved after expiry.",
                    "#activity",
                )
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(items, key=lambda i: (order[i["severity"]], i["type"]))


def _day(at: str) -> str:
    """Owner-facing business day, e.g. 'Thu 8 Oct' (Asia/Shanghai, like the UI)."""
    d = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=8)))
    return f"{d:%a} {d.day} {d:%b}"


def _plus_day(at: str) -> str:
    from finance.compute import shift

    return shift(at, 1)


def _remember_alerts(service: ExecutionService, ctx: AuthContext, items: list[Json]) -> list[Json]:
    """Idempotent first-seen record: the same condition never creates a second alert."""
    store = service.store
    with store.transaction() as db:
        seen = {
            r[0]: r[1]
            for r in db.execute(
                "SELECT object_id,created_at FROM objects WHERE tenant_id=? AND kind='alert_seen'",
                (ctx.tenant_id,),
            )
        }
        if ctx.role in WRITE_ROLES:
            for item in items:
                if item["alert_id"] not in seen:
                    store.put_object(db, ctx.tenant_id, "alert_seen", item["alert_id"], item)
                    seen[item["alert_id"]] = now()
    return [i | {"detected_at": seen.get(i["alert_id"]), "status": "ACTIVE"} for i in items]


# ---------------------------------------------------------------- case events


def case_events(db, tenant: str) -> list[Json]:
    events = _objects(db, tenant, "case_event")
    return sorted(events, key=lambda e: (e["at"], e["seq"]))


def _append(
    service: ExecutionService, ctx: AuthContext, case_id: str, kind: str, data: Json
) -> Json | None:
    with service.store.transaction() as db:
        service.store.authorize(db, ctx, WRITE_ROLES)
        current = fold(case_events(db, ctx.tenant_id))
        if kind == "OPENED":
            if any(not c["closed"] for c in current.values()):
                return None
        elif case_id not in current or current[case_id]["closed"]:
            return None
        seq = (
            db.execute(
                "SELECT COUNT(*) FROM objects WHERE tenant_id=? AND kind='case_event'",
                (ctx.tenant_id,),
            ).fetchone()[0]
            + 1
        )
        event = {
            "case_id": case_id,
            "seq": seq,
            "type": kind,
            "at": now(),
            "actor": ctx.user_id,
            "data": data,
        }
        service.store.put_object(db, ctx.tenant_id, "case_event", uid("case_event"), event)
        service.store.audit(db, ctx, "case." + kind.lower(), {"case_id": case_id, "seq": seq})
    return event


def fold(events: list[Json]) -> dict[str, Json]:
    cases: dict[str, Json] = {}
    for e in events:
        c = cases.setdefault(
            e["case_id"],
            {
                "case_id": e["case_id"],
                "history": [],
                "options": None,
                "selected": None,
                "closed": False,
                "problem": None,
            },
        )
        c["history"].append(
            {
                "seq": e["seq"],
                "type": e["type"],
                "at": e["at"],
                "actor": e["actor"],
                "summary": e["data"].get("summary"),
            }
        )
        if e["type"] == "OPENED":
            c["opened_at"], c["problem"] = e["at"], e["data"]["problem"]
        elif e["type"] == "PROBLEM_CHANGED":
            c["problem"] = e["data"]["problem"]
        elif e["type"] == "OPTIONS_COMPUTED":
            c["options"] = e["data"]
        elif e["type"] == "OPTION_SELECTED":
            c["selected"] = e["data"]
        elif e["type"] == "CLOSED":
            c["closed"], c["closed_reason"] = True, e["data"].get("reason")
    return cases


def _problem(snap: Json, fc: Json) -> Json | None:
    gaps = [s for s in fc["scenarios"] if s["first_gap_at"]]
    overdue = [
        o
        for o in snap["obligations"]
        if o["kind"] == "PAYABLE" and o["outstanding_minor"] and o["due_at"] < snap["as_of"]
    ]
    if not gaps and not overdue:
        return None
    base = fc["scenarios"][0]
    target = base if base["first_gap_at"] else (gaps[0] if gaps else base)
    return {
        "kind": "CASH_GAP" if base["first_gap_at"] else "STRESS_GAP" if gaps else "OVERDUE_PAYABLE",
        "scenario_id": target["scenario_id"],
        "first_gap_at": target["first_gap_at"],
        "net_need_minor": target["net_need_minor"],
        "minimum_balance_minor": target["minimum_balance_minor"],
        "overdue": [o["external_id"] for o in overdue],
        "snapshot_id": snap["snapshot_id"],
    }


def current_case(service: ExecutionService, ctx: AuthContext, snap: Json, fc: Json) -> Json | None:
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        cases = fold(case_events(db, ctx.tenant_id))
    open_cases = [c for c in cases.values() if not c["closed"]]
    problem = _problem(snap, fc)
    case = open_cases[-1] if open_cases else None
    if ctx.role not in WRITE_ROLES:
        return case
    if case is None and problem:
        case_id = (
            "case_" + digest([ctx.tenant_id, problem["kind"], problem["first_gap_at"], now()])[:20]
        )
        _append(
            service, ctx, case_id, "OPENED", {"problem": problem, "summary": _problem_text(problem)}
        )
        return current_case(service, ctx, snap, fc)
    if case and problem is None:
        selected = case.get("selected") or {}
        if selected.get("plan_id"):
            progress = plan_progress(service, ctx, selected["plan_id"])
            if progress["status"] == "COMPLETED":
                recon = service.refresh(ctx)
                if recon["matched"]:
                    _append(
                        service,
                        ctx,
                        case["case_id"],
                        "CLOSED",
                        {
                            "reason": "RESOLVED_SETTLED_AND_RECONCILED",
                            "reconciliation_id": recon["reconciliation_id"],
                            "summary": f"All {progress['total']} actions settled; reconciliation matched",
                        },
                    )
                    return None
            return case  # a plan is in progress: the risk is managed, not resolved
        _append(
            service,
            ctx,
            case["case_id"],
            "CLOSED",
            {
                "reason": "NO_LONGER_DETECTED_IN_DATA",
                "summary": "The gap is no longer detected in current data (not a payment result)",
            },
        )
        return None
    if case and problem:
        old = {
            k: case["problem"].get(k) for k in ("kind", "first_gap_at", "net_need_minor", "overdue")
        }
        new = {k: problem.get(k) for k in old}
        if old != new:
            _append(
                service,
                ctx,
                case["case_id"],
                "PROBLEM_CHANGED",
                {
                    "problem": problem,
                    "previous": case["problem"],
                    "summary": _diff_text(case["problem"], problem),
                },
            )
            return current_case(service, ctx, snap, fc)
    return case


def _problem_text(p: Json) -> str:
    if p["kind"] == "OVERDUE_PAYABLE":
        return "Overdue payments: " + ", ".join(p["overdue"])
    return f"{p['kind']}: need {cny(p['net_need_minor'])} by {_day(p['first_gap_at']) if p['first_gap_at'] else '—'} ({p['scenario_id']})"


def _diff_text(old: Json, new: Json) -> str:
    parts = []
    if old.get("net_need_minor") != new.get("net_need_minor"):
        parts.append(
            f"need {cny(old.get('net_need_minor') or 0)} → {cny(new.get('net_need_minor') or 0)}"
        )
    if old.get("first_gap_at") != new.get("first_gap_at"):
        parts.append(
            f"gap date {_day(old['first_gap_at']) if old.get('first_gap_at') else 'none'} → {_day(new['first_gap_at']) if new.get('first_gap_at') else 'none'}"
        )
    if old.get("kind") != new.get("kind"):
        parts.append(f"{old.get('kind')} → {new.get('kind')}")
    if old.get("overdue") != new.get("overdue"):
        parts.append("overdue list changed")
    return "Data changed: " + "; ".join(parts or ["details"])


# ---------------------------------------------------------------- home


def home(service: ExecutionService, ctx: AuthContext) -> Json:
    store = service.store
    snap = snapshot(store, ctx)
    fc = forecast(snap)
    with store.connect() as db:
        store.authorize(db, ctx)
        company = dict(
            db.execute("SELECT * FROM companies WHERE tenant_id=?", (ctx.tenant_id,)).fetchone()
        )
        names = _labels(db, ctx.tenant_id)
        actions = _actions(db, ctx.tenant_id)
        approvals = [
            dict(r)
            for r in db.execute(
                "SELECT approval_id,expires_at,revoked FROM approvals WHERE tenant_id=?",
                (ctx.tenant_id,),
            )
        ]
        reserved = sum(
            r[0]
            for r in db.execute(
                "SELECT amount_minor FROM reservations WHERE tenant_id=? AND status='ACTIVE'",
                (ctx.tenant_id,),
            )
        )
        recon_rows = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='reconciliation' ORDER BY created_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
        has_facts = bool(snap["facts"])
    recon = json.loads(recon_rows[0]) if recon_rows else None
    found = alerts(snap, fc, actions, approvals, company, recon, names)
    found = _remember_alerts(service, ctx, found)
    case = current_case(service, ctx, snap, fc) if has_facts else None
    base = fc["scenarios"][0]
    stress = [s for s in fc["scenarios"][1:] if s["first_gap_at"]]
    unknown = [a for a in actions if a["status"] == "UNKNOWN"]
    in_flight = [a for a in actions if a["status"] in {"RESERVED", "SUBMITTED"}]
    selected = (case or {}).get("selected")
    due_review = None
    if selected and selected.get("plan_id"):
        due_review = next_reviewable(service, ctx, selected["plan_id"], actions)
    if not has_facts:
        state, headline, cta = (
            "EMPTY",
            "No financial data yet",
            {"label": "Import records", "route": "#documents"},
        )
    elif snap["quality_flags"]:
        state, headline, cta = (
            "DATA_REVIEW",
            "Forecast needs review",
            {"label": "Review import issues", "route": "#documents"},
        )
    elif unknown:
        state, headline, cta = (
            "UNKNOWN_PAYMENT",
            "Checking payment status. Do not send again.",
            {"label": "Open operation", "route": f"#activity/{unknown[0]['action_id']}"},
        )
    elif due_review and due_review.get("approvable"):
        state, headline = "PENDING_DECISION", "Review the next action"
        cta = {
            "label": "Review " + due_review["title"],
            "route": f"#review/{(selected or {}).get('plan_id')}/{due_review['action_id']}",
        }
    elif in_flight:
        state, headline, cta = (
            "IN_FLIGHT",
            "Payment in progress",
            {"label": "Open activity", "route": "#activity"},
        )
    elif base["first_gap_at"]:
        state = "GAP"
        headline = f"Cash falls below your reserve on {_day(base['first_gap_at'])}"
        cta = {"label": "Compare ways to cover the gap", "route": "#case"}
    elif any(a["type"] == "OVERDUE_PAYABLE" for a in found):
        state, headline, cta = (
            "OVERDUE",
            "A payment is overdue",
            {"label": "Open the financial task", "route": "#case"},
        )
    elif stress:
        state = "STRESS_GAP"
        headline = f"No gap on contract dates, but a late customer payment creates one ({stress[0]['scenario_id']})"
        cta = {"label": "Review the risk", "route": "#case"}
    else:
        state, headline, cta = (
            "NO_GAP",
            "No gap in the selected scenarios",
            {"label": "Open cash flow", "route": "#money"},
        )
    upcoming = [
        {
            "fact_id": o["fact_id"],
            "reference": o["external_id"],
            "kind": o["kind"],
            "party": party(names, o["counterparty"]),
            "due_at": o["due_at"],
            "overdue": o["due_at"] < snap["as_of"],
            "protected": bool(o["protected"]),
            "amount": money(o["outstanding_minor"]),
            "source_id": o["source_id"],
        }
        for o in snap["obligations"]
        if o["outstanding_minor"]
    ][:8]
    return {
        "schema_version": 1,
        "computed_at": now(),
        "business_as_of": snap["as_of"],
        "snapshot_id": snap["snapshot_id"],
        "data_version": snap["data_version"],
        "company": {
            "name": snap["profile"]["name"],
            "role": ctx.role,
            "mode": "SYNTHETIC · SANDBOX",
        },
        "state": state,
        "headline": headline,
        "cta": cta,
        "problem": {
            "need": money(base["net_need_minor"]),
            "first_gap_at": base["first_gap_at"],
            "minimum": money(base["minimum_balance_minor"]),
            "scenario_id": base["scenario_id"],
            "stress": [
                {
                    "scenario_id": s["scenario_id"],
                    "minimum": money(s["minimum_balance_minor"]),
                    "first_gap_at": s["first_gap_at"],
                    "need": money(s["net_need_minor"]),
                }
                for s in fc["scenarios"][1:]
            ],
            "drivers": drivers(snap, scenarios()[0], names) | {"path": None},
        },
        "metrics": {
            "confirmed_cash": money(snap["confirmed_cash_minor"])
            | {"definition": "Opening balance plus settled transactions observed by the sandbox"},
            "reserved": money(reserved)
            | {"definition": "Held for approved operations that are not yet reconciled"},
            "reserve": money(snap["policy"]["reserve_minor"])
            | {
                "definition": "Hard minimum the plan must keep (policy "
                + snap["policy"]["version"]
                + ")"
            },
            "expected_minimum": money(base["minimum_balance_minor"])
            | {
                "definition": "Lowest projected cash on contract dates (f0); expected receipts are not settled cash"
            },
        },
        "chart": chart(snap, fc),
        "upcoming": upcoming,
        "alerts": found,
        "transactions": [
            {
                "reference": f["external_id"],
                "at": f["value"]["event_time"],
                "party": party(names, f["value"]["counterparty"] or ""),
                "amount": money(f["value"]["amount_minor"]),
                "provider": f["provider"],
                "source_id": f["source_id"],
                "status": f["value"]["status"],
            }
            for f in sorted(snap["facts"], key=lambda f: f["value"]["event_time"], reverse=True)
            if f["kind"] in {"TRANSACTION", "BALANCE"}
        ][:20],
        "case": case_summary(case) if case else None,
        "next_review": due_review,
        "stopped": bool(company["stopped"]),
        "quality_flags": snap["quality_flags"],
        "evidence_refs": snap["evidence_refs"],
    }


def chart(snap: Json, fc: Json) -> Json:
    series = []
    for s in fc["scenarios"]:
        points = [
            {
                "at": snap["as_of"],
                "balance": money(snap["confirmed_cash_minor"]),
                "label": "Today (confirmed)",
            }
        ]
        points += [
            {
                "at": p["at"],
                "balance": money(p["balance_minor"]),
                "label": p["reference"],
                "delta": money(p["amount_minor"]),
            }
            for p in s["points"]
        ]
        series.append(
            {"scenario_id": s["scenario_id"], "provenance": s.get("provenance"), "points": points}
        )
    return {
        "series": series,
        "reserve": money(snap["policy"]["reserve_minor"]),
        "kind": "FORECAST_UNCALIBRATED",
        "note": "Scenarios are DEMO assumptions, not probabilities.",
    }


def case_summary(case: Json) -> Json:
    return {
        "case_id": case["case_id"],
        "opened_at": case.get("opened_at"),
        "problem": case["problem"],
        "selected": case["selected"],
        "has_options": bool(case["options"]),
        "history": case["history"][-12:],
    }


# ---------------------------------------------------------------- options


STRATEGIES = [
    (
        "FINANCE_MIN_COST",
        "MIN_COST",
        "Bridge financing at lowest cost",
        "Borrow the least-cost amount that keeps the reserve on contract dates.",
    ),
    (
        "NO_NEW_DEBT",
        "NO_NEW_DEBT",
        "No new debt",
        "Pay everything on the current dates with existing cash only.",
    ),
    (
        "HIGHER_RESERVE",
        "HIGHER_RESERVE",
        "Keep a larger cushion",
        "Lowest cost that keeps an explicit higher cash target on contract dates.",
    ),
    (
        "STRESS_RESILIENT",
        "PRESERVE_LIQUIDITY",
        "Survive late customer payments",
        "Lowest cost that keeps the reserve even if the customer pays 5 or 25 days late.",
    ),
]


def option_card(
    key: str,
    objective: str,
    label: str,
    summary: str,
    result: Json,
    snap: Json,
    names: dict[str, str],
) -> Json:
    plan = result["plan"]
    card: Json = {
        "key": key,
        "objective": objective,
        "label": label,
        "summary": summary,
        "objective_implemented": result.get("objective_implemented"),
        "solver_status": result["solver_status"],
        "status": "EXECUTABLE"
        if plan
        else ("INFEASIBLE" if result["solver_status"] == "INFEASIBLE" else "UNKNOWN"),
        "floor": money(result.get("liquidity_floor_minor", snap["policy"]["reserve_minor"])),
        "validated_scenarios": result.get("validated_scenarios", []),
        "candidate_scope": result.get("candidate_scope"),
        "candidate_count": result.get("candidate_count"),
        "scope_note": "Best within the finite DEMO product/amount grid; not a global optimum or a lender offer.",
    }
    if not plan:
        card["reasons"] = explain_infeasible(snap, objective, result)
        card["reasons_label"] = "Diagnostic checks, not a minimal infeasibility proof"
        return card
    q = plan.get("quote")
    card |= {
        "plan_id": plan["plan_id"],
        "financing": None
        if not q
        else {
            "product": q["terms"]["name"],
            "product_id": q["product_version"],
            "gross": money(q["principal_minor"]),
            "net": money(q["net_minor"]),
            "upfront_fee": money(q["upfront_fee_minor"]),
            "repayment_fee": money(q["repayment_fee_minor"]),
            "interest": money(q["interest_minor"]),
            "repayment": money(q["repayment_minor"]),
            "total_cost": money(q["total_cost_minor"]),
            "annual_cost": annual_cost(q),
            "disburse_at": q["disburse_at"],
            "repay_at": q["repay_at"],
            "quote_expires_at": q["expires_at"],
            "binding": "SYNTHETIC_QUOTE",
        },
        "total_cost": money(plan["total_cost_minor"]),
        "actions": [
            {
                "action_id": a["action_id"],
                "kind": a["kind"],
                "at": a["at"],
                "amount": money(a["amount_minor"]),
                "party": "Lender"
                if a["kind"] in {"DRAW_LOAN"}
                or (a["kind"] == "REPAY_LOAN" and not a.get("obligation_provider"))
                else party(names, a.get("obligation_id") or ""),
                "dependencies": a["dependencies"],
            }
            for a in plan["actions"]
        ],
        "scenarios": [
            {
                "scenario_id": p["scenario_id"],
                "minimum": money(p["minimum_balance_minor"]),
                "final": money(p["final_balance_minor"]),
                "first_breach_at": p["first_gap_at"],
                "holds": p["minimum_balance_minor"] >= snap["policy"]["reserve_minor"],
                "validated": p["scenario_id"] in result.get("validated_scenarios", []),
            }
            for p in plan["stress_paths"]
        ],
    }
    card["path"] = [
        {"at": p["at"], "balance": money(p["balance_minor"]), "label": p["reference"]}
        for p in plan["stress_paths"][0]["points"]
    ]
    failing = [s for s in card["scenarios"] if not s["holds"]]
    if failing:
        card["warnings"] = [
            f"Not validated for {s['scenario_id']}: cash falls to {s['minimum']['display']}."
            for s in failing
        ]
    return card


def extension_cards(
    service: ExecutionService, ctx: AuthContext, snap: Json, names: dict[str, str]
) -> list[Json]:
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM extension_requests WHERE tenant_id=?", (ctx.tenant_id,)
            )
        ]
        plans = {p["request_id"]: p for p in _objects(db, ctx.tenant_id, "contingent_plan")}
    cards = []
    for r in rows:
        env = plans.get(r["request_id"])
        fact = next(
            (o for o in snap["obligations"] if o["fact_id"] == r["obligation_fact_id"]), None
        )
        result = env["if_confirmed"] if env else None
        cards.append(
            {
                "key": "EXTENSION_" + r["request_id"][-8:],
                "request_id": r["request_id"],
                "label": "Ask "
                + (party(names, fact["counterparty"]) if fact else "supplier")
                + " to move the due date",
                "status": "CONDITIONAL" if r["status"] == "REQUESTED" else r["status"],
                "executable": False,
                "proposed_due_at": r["proposed_due_at"],
                "summary": "Not executable until the counterparty's decision is observed. The confirmed due date is unchanged.",
                "if_confirmed": None
                if not result
                else {
                    "solver_status": result["solver_status"],
                    "minimum": money(
                        min(p["minimum_balance_minor"] for p in result["plan"]["paths"])
                    )
                    if result["plan"]
                    else None,
                    "total_cost": money(0) if result["plan"] else None,
                },
            }
        )
    return cards


def compute_options(
    service: ExecutionService, ctx: AuthContext, reserve_target_minor: int | None = None
) -> Json:
    snap = snapshot(service.store, ctx)
    fc = forecast(snap)
    case = current_case(service, ctx, snap, fc)
    require(case is not None, "NO_OPEN_CASE", "No cash problem is detected in current data")
    assert case is not None
    with service.store.connect() as db:
        names = _labels(db, ctx.tenant_id)
    cards = []
    for key, objective, label, summary in STRATEGIES:
        target = reserve_target_minor if objective == "HIGHER_RESERVE" else None
        if objective == "HIGHER_RESERVE" and target is None:
            target = snap["policy"]["reserve_minor"] * 5 // 4
        result = service.make_plan(ctx, objective, None, target)
        card = option_card(key, objective, label, summary, result, snap, names)
        if objective == "HIGHER_RESERVE" and target is not None:
            card["label"] = f"Keep at least {cny(target)}"
            card["reserve_target"] = money(target)
        cards.append(card)
    cards += extension_cards(service, ctx, snap, names)
    executable = [c for c in cards if c["status"] == "EXECUTABLE"]
    cheapest = min(executable, key=lambda c: c["total_cost"]["minor"], default=None)
    data = {
        "snapshot_id": snap["snapshot_id"],
        "computed_for_as_of": snap["as_of"],
        "options": cards,
        "lowest_cost_key": cheapest["key"] if cheapest else None,
        "note": "No option is labelled recommended: compare cost, scenarios and conditions.",
        "summary": f"{len(executable)} executable of {len(cards)} options",
    }
    require(
        _append(service, ctx, case["case_id"], "OPTIONS_COMPUTED", data) is not None,
        "STALE_CASE",
        "This case was closed or replaced meanwhile; reload the home page",
    )
    return data


def case_detail(service: ExecutionService, ctx: AuthContext) -> Json:
    snap = snapshot(service.store, ctx)
    fc = forecast(snap)
    case = current_case(service, ctx, snap, fc)
    with service.store.connect() as db:
        names = _labels(db, ctx.tenant_id)
    if case is None:
        with service.store.connect() as db:
            closed = [c for c in fold(case_events(db, ctx.tenant_id)).values() if c["closed"]]
        last = closed[-1] if closed else None
        return {
            "case": None,
            "state": "NO_OPEN_CASE",
            "snapshot_id": snap["snapshot_id"],
            "message": "No cash gap or overdue payment detected in the current data.",
            "last_closed": None
            if not last
            else case_summary(last) | {"closed_reason": last.get("closed_reason")},
        }
    options = case["options"]
    stale = bool(options and options["snapshot_id"] != snap["snapshot_id"])
    base = fc["scenarios"][0]
    known = [
        "Confirmed cash " + cny(snap["confirmed_cash_minor"]) + " (settled observations)",
        f"{len([o for o in snap['obligations'] if o['kind'] == 'PAYABLE' and o['outstanding_minor']])} confirmed payables with fixed dates",
    ]
    unknown = [
        "Whether customers pay on time (receipts are expected, not settled)",
        "Lender approval: DEMO eligibility is not a credit decision",
    ]
    selected = case["selected"]
    plan_view = None
    if selected and selected.get("plan_id"):
        plan_view = plan_progress(service, ctx, selected["plan_id"])
    return {
        "case": case_summary(case),
        "state": "OPEN",
        "snapshot_id": snap["snapshot_id"],
        "business_as_of": snap["as_of"],
        "problem": {
            "need": money(base["net_need_minor"]),
            "first_gap_at": base["first_gap_at"],
            "minimum": money(base["minimum_balance_minor"]),
            "reserve": money(snap["policy"]["reserve_minor"]),
            "drivers": drivers(snap, scenarios()[0], names) | {"path": None},
            "stress": [
                {
                    "scenario_id": s["scenario_id"],
                    "minimum": money(s["minimum_balance_minor"]),
                    "first_gap_at": s["first_gap_at"],
                }
                for s in fc["scenarios"][1:]
            ],
        },
        "known": known,
        "unknown": unknown,
        "chart": chart(snap, fc),
        "options": options,
        "options_stale": stale,
        "selected": selected,
        "plan": plan_view,
    }


def select_option(service: ExecutionService, ctx: AuthContext, key: str) -> Json:
    require(
        isinstance(key, str) and ID.match(key) is not None,
        "INVALID_ARGUMENTS",
        "Option key required",
    )
    snap = snapshot(service.store, ctx)
    case = current_case(service, ctx, snap, forecast(snap))
    require(case is not None and case["options"], "NO_OPTIONS", "Compute options first")
    assert case is not None
    card = next((c for c in case["options"]["options"] if c["key"] == key), None)
    require(card is not None, "NOT_FOUND", "Option not in this case")
    assert card is not None
    require(
        card["status"] == "EXECUTABLE" and card.get("plan_id"),
        "OPTION_NOT_EXECUTABLE",
        "Only an executable validated option can be selected; conditional/infeasible options cannot",
    )
    require(
        case["options"]["snapshot_id"] == snap["snapshot_id"],
        "STALE_OPTIONS",
        "Data changed since the options were computed; recompute before selecting",
    )
    service.store.get_object(ctx, "plan", card["plan_id"])
    data = {
        "key": key,
        "plan_id": card["plan_id"],
        "objective": card["objective"],
        "snapshot_id": snap["snapshot_id"],
        "summary": f"Selected {card['label']} ({card['total_cost']['display']} cost)",
    }
    require(
        _append(service, ctx, case["case_id"], "OPTION_SELECTED", data) is not None,
        "STALE_CASE",
        "This case was closed or replaced meanwhile; reload the home page",
    )
    return data


# ---------------------------------------------------------------- review & timeline


ACTION_TITLES = {"DRAW_LOAN": "Draw loan", "PAY_OBLIGATION": "Pay", "REPAY_LOAN": "Repay loan"}


def _action_title(a: Json, names: dict[str, str]) -> str:
    if a["kind"] == "PAY_OBLIGATION":
        return f"Pay {party(names, a.get('obligation_id') or '')} · {cny(a['amount_minor'])}"
    return f"{ACTION_TITLES[a['kind']]} · {cny(a['amount_minor'])}"


def next_reviewable(
    service: ExecutionService, ctx: AuthContext, plan_id: str, actions: list[Json] | None = None
) -> Json | None:
    plan = service.store.get_object(ctx, "plan", plan_id)
    states = {a["action_id"]: a["status"] for a in (actions or [])} if actions is not None else None
    if states is None:
        with service.store.connect() as db:
            states = {a["action_id"]: a["status"] for a in _actions(db, ctx.tenant_id)}
    for a in plan["actions"]:
        if a["action_id"] not in states:
            return review(service, ctx, plan_id, a["action_id"], plan=plan)
    return None


def review(
    service: ExecutionService,
    ctx: AuthContext,
    plan_id: str,
    action_id: str,
    plan: Json | None = None,
) -> Json:
    require(
        ID.match(plan_id or "") is not None and ID.match(action_id or "") is not None,
        "INVALID_ARGUMENTS",
        "IDs required",
    )
    plan = plan or service.store.get_object(ctx, "plan", plan_id)
    target = next((a for a in plan["actions"] if a["action_id"] == action_id), None)
    require(target is not None, "NOT_FOUND", "Action does not belong to this plan")
    assert target is not None
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        names = _labels(db, ctx.tenant_id)
        row = db.execute(
            "SELECT status FROM actions WHERE tenant_id=? AND action_id=?",
            (ctx.tenant_id, action_id),
        ).fetchone()
        reserved = sum(
            r[0]
            for r in db.execute(
                "SELECT amount_minor FROM reservations WHERE tenant_id=? AND status='ACTIVE'",
                (ctx.tenant_id,),
            )
        )
        beneficiary = db.execute(
            "SELECT verified,payload FROM beneficiaries WHERE tenant_id=? AND version_id=?",
            (ctx.tenant_id, target["beneficiary_version_id"]),
        ).fetchone()
    snap = snapshot(service.store, ctx)
    index = [a["action_id"] for a in plan["actions"]].index(action_id) + 1
    projection: Json = {
        "plan_id": plan_id,
        "action_id": action_id,
        "kind": target["kind"],
        "title": _action_title(target, names),
        "recipient": {
            "name": json.loads(beneficiary["payload"])["name"]
            if beneficiary
            else target["beneficiary_version_id"],
            "beneficiary_version_id": target["beneficiary_version_id"],
            "verified": bool(beneficiary and beneficiary["verified"]),
        },
        "amount": money(target["amount_minor"]),
        "currency": "CNY",
        "due_at": target["at"],
        "cash_effect": money(target["cash_delta_minor"]),
        "available_now": money(snap["confirmed_cash_minor"] - reserved),
        "available_after": money(
            snap["confirmed_cash_minor"] - reserved + target["cash_delta_minor"]
        ),
        "reserve": money(snap["policy"]["reserve_minor"]),
        "scope": f"Action {index} of {len(plan['actions'])} in this plan. Other actions need their own approval.",
        "approval_means": [
            "This exact command, amount, recipient version and terms may be sent once by the sandbox worker.",
            "Funds are reserved first; the send is re-checked against current facts and policy.",
        ],
        "approval_does_not_mean": [
            "Approval of any other step of the plan.",
            "Settlement: the payment counts as done only after reconciliation.",
            "Cancellation: sent operations cannot be recalled in this sandbox.",
        ],
        "status": row[0] if row else "NOT_APPROVED",
    }
    if target.get("quote"):
        q = target["quote"]
        projection["loan_terms"] = {
            "product": q["terms"]["name"],
            "gross": money(q["principal_minor"]),
            "net": money(q["net_minor"]),
            "upfront_fee": money(q["upfront_fee_minor"]),
            "interest": money(q["interest_minor"]),
            "repayment_fee": money(q["repayment_fee_minor"]),
            "repayment": money(q["repayment_minor"]),
            "annual_cost": annual_cost(q),
            "repay_at": q["repay_at"],
            "quote_expires_at": q["expires_at"],
            "binding": "SYNTHETIC_QUOTE — not a lender offer",
        }
    if row:
        projection["approvable"] = False
        projection["block"] = {
            "code": "ALREADY_" + row[0],
            "text": "Already approved; follow its timeline.",
        }
        return projection
    try:
        command = service.command(ctx, plan_id, action_id)
    except FinanceError as exc:
        text = {
            "PRECONDITION_FAILED": f"Available for approval on {_day(target['at'])} (sandbox clock is {_day(snap['as_of'])}) or after its dependency settles.",
            "STALE_PLAN": "Facts changed since this plan was built; recompute options.",
            "INSUFFICIENT_DATA": "Resolve import issues first.",
            "PLAN_CANCELLED": "This plan was cancelled.",
        }.get(exc.code, exc.safe_message if hasattr(exc, "safe_message") else str(exc))
        projection["approvable"] = False
        projection["block"] = {"code": exc.code, "text": text}
        return projection
    projection["approvable"] = ctx.role == "OWNER"
    if ctx.role != "OWNER":
        projection["block"] = {
            "code": "OWNER_REQUIRED",
            "text": "Only the OWNER can approve payments.",
        }
    projection["command"] = command
    projection["payload_hash"] = digest(command)
    projection["button"] = "Approve " + projection["title"].replace(" · ", " — ")
    return projection


TIMELINE = [
    ("APPROVED", "Approved by owner", {"approval.created"}),
    ("QUEUED", "Funds reserved and queued", {"action.reserved"}),
    ("SENT", "Sent to sandbox", {"action.submitted", "action.unknown"}),
    ("RECONCILED", "Settled and reconciled", {"action.settled_reconciled"}),
]


def timeline(service: ExecutionService, ctx: AuthContext, action_id: str) -> Json:
    require(ID.match(action_id or "") is not None, "INVALID_ARGUMENTS", "Action ID required")
    action = service.action(ctx, action_id)
    command = action["payload"]
    log = [
        e
        for e in service.store.audit_log(ctx)
        if action_id in e["payload"] or command["required_approval_id"] in e["payload"]
    ]
    steps = []
    for code, label, events in TIMELINE:
        hit = next((e for e in log if e["event_type"] in events), None)
        steps.append(
            {
                "step": code,
                "label": label,
                "observed_at": hit["occurred_at"] if hit else None,
                "done": bool(hit),
            }
        )
    status = action["status"]
    if status == "UNKNOWN":
        message = "The sandbox response was lost. The operation may already exist: we check by its original key and never send a second copy. Funds stay reserved."
    elif status == "SUBMITTED":
        message = "Sent. Waiting for the sandbox to report settlement; it counts as paid only after reconciliation."
    elif status == "SETTLED":
        message = "Settled and reconciled against the sandbox movement."
    elif status == "FAILED":
        message = "Failed. The reservation was released; nothing was paid."
    else:
        message = "Approved and reserved; the worker will send it."
    with service.store.connect() as db:
        recon = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='reconciliation' ORDER BY created_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
        names = _labels(db, ctx.tenant_id)
    return {
        "action_id": action_id,
        "plan_id": command["plan_id"],
        "title": _action_title(command, names),
        "status": status,
        "message": message,
        "steps": steps,
        "attempts": [{"at": a["at"], "status": a["status"]} for a in action["attempts"]]
        if action["attempts"] and "at" in action["attempts"][0]
        else [{"status": a.get("status")} for a in action["attempts"]],
        "provider_ref": action.get("provider_ref"),
        "can_check_status": status in {"UNKNOWN", "SUBMITTED", "RESERVED"},
        "check_status_note": "Looks up the original operation by its stable key before anything else; it never creates a new payment.",
        "reconciliation": json.loads(recon[0]) if recon and status == "SETTLED" else None,
        "command": command,
    }


def plan_progress(service: ExecutionService, ctx: AuthContext, plan_id: str) -> Json:
    plan = service.store.get_object(ctx, "plan", plan_id)
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        states = {a["action_id"]: a["status"] for a in _actions(db, ctx.tenant_id)}
        names = _labels(db, ctx.tenant_id)
        cancelled = db.execute(
            "SELECT 1 FROM objects WHERE tenant_id=? AND kind='cancelled_plan' AND object_id=?",
            (ctx.tenant_id, plan_id),
        ).fetchone()
    steps = [
        {
            "action_id": a["action_id"],
            "title": _action_title(a, names),
            "kind": a["kind"],
            "at": a["at"],
            "amount": money(a["amount_minor"]),
            "status": states.get(a["action_id"], "NOT_APPROVED"),
        }
        for a in plan["actions"]
    ]
    done = sum(s["status"] == "SETTLED" for s in steps)
    return {
        "plan_id": plan_id,
        "objective": plan["objective"],
        "steps": steps,
        "settled": done,
        "total": len(steps),
        "cancelled": bool(cancelled),
        "status": "COMPLETED"
        if done == len(steps)
        else "PARTIALLY_EXECUTED"
        if done
        else "NOT_STARTED",
    }


# ---------------------------------------------------------------- what-if


def what_if(service: ExecutionService, ctx: AuthContext, value: Json) -> Json:
    snap = snapshot(service.store, ctx)
    ref, delay, bps = (
        value.get("obligation_id"),
        value.get("delay_days", 0),
        value.get("receipt_bps", 10000),
    )
    target = next(
        (
            o
            for o in snap["obligations"]
            if o["external_id"] == ref and o["kind"] == "RECEIVABLE" and o["outstanding_minor"]
        ),
        None,
    )
    require(target is not None, "NOT_FOUND", "Choose an open receivable from the current data")
    require(
        type(delay) is int and 0 <= delay <= 365 and type(bps) is int and 0 <= bps <= 10000,
        "INVALID_SCENARIO",
        "Delay 0–365 days, receipt 0–10000 bps",
    )
    assert target is not None and isinstance(ref, str)
    scenario = {
        "scenario_id": "what_if_" + ref,
        "delay_days": 0,
        "provenance": "OWNER_WHAT_IF",
        "calibration_status": "UNCALIBRATED",
        "obligation_shocks": {ref: {"delay_days": delay, "receipt_bps": bps}},
    }
    fc = forecast(snap, scenario_set=[scenarios()[0], scenario])
    base, alt = fc["scenarios"]
    from finance.planner import solve

    hypothetical = solve(snap, "MIN_COST", scenario_set=[scenario])
    selected_check = None
    case = current_case(service, ctx, snap, forecast(snap))
    if case and case.get("selected"):
        plan = service.store.get_object(ctx, "plan", case["selected"]["plan_id"])
        path = plan_trajectories(snap, plan, [scenario])[0]
        selected_check = {
            "plan_id": plan["plan_id"],
            "minimum": money(path["minimum_balance_minor"]),
            "holds": path["minimum_balance_minor"] >= snap["policy"]["reserve_minor"],
        }
    return {
        "label": "SCENARIO ONLY — actual facts are unchanged",
        "snapshot_id": snap["snapshot_id"],
        "assumption": {
            "obligation_id": ref,
            "party": target["counterparty"],
            "delay_days": delay,
            "receipt_bps": bps,
        },
        "baseline": {
            "minimum": money(base["minimum_balance_minor"]),
            "first_gap_at": base["first_gap_at"],
            "need": money(base["net_need_minor"]),
        },
        "scenario": {
            "minimum": money(alt["minimum_balance_minor"]),
            "first_gap_at": alt["first_gap_at"],
            "need": money(alt["net_need_minor"]),
        },
        "chart": {
            "series": [chart(snap, fc)["series"][0], chart(snap, fc)["series"][1]],
            "reserve": money(snap["policy"]["reserve_minor"]),
        },
        "selected_plan": selected_check,
        "hypothetical_min_cost": {
            "solver_status": hypothetical["solver_status"],
            "total_cost": money(hypothetical["plan"]["total_cost_minor"])
            if hypothetical["plan"]
            else None,
            "executable": False,
        },
    }


# ---------------------------------------------------------------- user context


CONTEXT_KEYS = {"route", "case_id", "plan_id", "action_id", "obligation_id", "option_key"}


def save_context(service: ExecutionService, ctx: AuthContext, value: Json) -> Json:
    require(set(value) <= CONTEXT_KEYS, "INVALID_ARGUMENTS", "Unknown context field")
    for v in value.values():
        require(
            v is None
            or (
                isinstance(v, str)
                and len(v) <= 200
                and re.match(r"^[#A-Za-z0-9_./:\-]*$", v) is not None
            ),
            "INVALID_ARGUMENTS",
            "Context values are short references",
        )
    with service.store.transaction() as db:
        service.store.authorize(db, ctx)
        service.store.put_object(
            db,
            ctx.tenant_id,
            "ui_context",
            uid("ui_context"),
            {"user_id": ctx.user_id, "role": ctx.role, "value": value, "at": now()},
        )
    return {"saved": True}


def load_context(service: ExecutionService, ctx: AuthContext) -> Json:
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        rows = _objects(db, ctx.tenant_id, "ui_context")
    mine = [r for r in rows if r["user_id"] == ctx.user_id and r["role"] == ctx.role]
    return {
        "context": mine[-1]["value"] if mine else {},
        "note": "References are re-authorized when used",
    }


EVENT_LABELS = {
    "approval.created": "Approved",
    "approval.revoked": "Approval revoked",
    "action.reserved": "Funds reserved",
    "action.submitted": "Sent to sandbox",
    "action.unknown": "Response lost — checking status",
    "action.failed": "Operation failed",
    "action.settled_reconciled": "Settled and reconciled",
    "source.imported": "Records imported",
    "import.mapped": "Mapped import committed",
    "plan.validated": "Plan validated",
    "plan.cancelled": "Plan cancelled",
    "control.stop": "Send control changed",
    "reconciliation.mismatch": "Reconciliation mismatch",
    "extension.requested": "Extension requested",
    "case.opened": "Financial task opened",
    "case.problem_changed": "Data changed the problem",
    "case.options_computed": "Options compared",
    "case.option_selected": "Plan selected",
    "session.created": "Signed in",
}


def activity(service: ExecutionService, ctx: AuthContext) -> Json:
    with service.store.connect() as db:
        service.store.authorize(db, ctx)
        names = _labels(db, ctx.tenant_id)
        actions = _actions(db, ctx.tenant_id)
        recon = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='reconciliation' ORDER BY created_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
        stopped = db.execute(
            "SELECT stopped FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()[0]
    raw = [e for e in service.store.audit_log(ctx) if e["event_type"] in EVENT_LABELS]
    # The worker re-records an unchanged status on every poll; collapse identical repeats.
    events: list[Json] = []
    for e in raw:
        payload = json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"]
        key = (e["event_type"], payload.get("action_id"))
        if events and events[-1]["_key"] == key:
            events[-1]["repeats"] += 1
            events[-1]["last_at"] = e["occurred_at"]
            continue
        events.append(
            {
                "_key": key,
                "repeats": 1,
                "occurred_at": e["occurred_at"],
                "last_at": e["occurred_at"],
                "event_type": e["event_type"],
                "payload": payload,
            }
        )
    events = events[-60:]
    operations = [
        {
            "action_id": a["action_id"],
            "title": _action_title(a["payload"], names),
            "status": a["status"],
            "kind": a["payload"]["kind"],
            "amount": money(a["payload"]["amount_minor"]),
            "due_at": a["payload"]["at"],
            "plan_id": a["payload"]["plan_id"],
        }
        for a in actions
    ]
    order = {"UNKNOWN": 0, "RESERVED": 1, "SUBMITTED": 1, "FAILED": 2, "SETTLED": 3}
    return {
        "operations": sorted(operations, key=lambda o: (order.get(o["status"], 4), o["due_at"])),
        "events": [
            {
                "at": e["occurred_at"],
                "last_at": e["last_at"],
                "repeats": e["repeats"],
                "type": e["event_type"],
                "label": EVENT_LABELS[e["event_type"]],
                "payload": e["payload"],
            }
            for e in reversed(events)
        ],
        "reconciliation": json.loads(recon[0]) if recon else None,
        "stopped": bool(stopped),
    }
