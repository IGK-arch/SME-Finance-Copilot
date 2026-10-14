"""Independent plan arithmetic and constraints. Does not call trajectory/optimizer."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from finance.domain import Json, digest


def validate_plan(snap: Json, plan: Json, scenario_set: list[Json]) -> Json:
    errors: list[str] = []
    actions = plan["actions"]
    ids = {a["action_id"] for a in actions}
    completed: set[str] = set()
    for _ in range(len(actions) + 1):
        ready = {a["action_id"] for a in actions if set(a["dependencies"]) <= completed}
        if ready <= completed:
            break
        completed |= ready
    if completed != ids or len(ids) != len(actions):
        errors.append("INVALID_DAG")
    payables = {
        (o["provider"], o["external_id"]): o
        for o in snap["obligations"]
        if o["kind"] == "PAYABLE" and o["outstanding_minor"]
    }
    paid: set[tuple[str, str]] = set()
    for a in actions:
        if a["kind"] == "PAY_OBLIGATION" or (
            a["kind"] == "REPAY_LOAN" and "obligation_provider" in a
        ):
            key = (a["obligation_provider"], a["obligation_id"])
            o = payables.get(key)
            if o is None or key in paid or a["amount_minor"] != o["outstanding_minor"]:
                errors.append("OBLIGATION_AMOUNT")
            elif a["at"] != o["due_at"] or a["beneficiary_version_id"] != o["beneficiary_version"]:
                errors.append("PROTECTED_OR_CONFIRMED_TERMS")
            if a["cash_delta_minor"] != -a["amount_minor"]:
                errors.append("PAYMENT_CASH_DELTA")
            paid.add(key)
    if paid != payables.keys():
        errors.append("MISSING_OBLIGATION")
    quote = plan.get("quote")
    if quote:
        terms = quote["terms"]
        days = (
            datetime.fromisoformat(terms["repay_at"]) - datetime.fromisoformat(terms["disburse_at"])
        ).days
        independent_interest = int(
            (
                Decimal(quote["principal_minor"])
                * Decimal(terms["rate"])
                * Decimal(days)
                / Decimal(365)
            ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )
        if (
            quote["repayment_minor"]
            != quote["principal_minor"] + independent_interest + terms["repayment_fee_minor"]
        ):
            errors.append("REPAYMENT_ARITHMETIC")
        if quote["net_minor"] != quote["principal_minor"] - terms["upfront_fee_minor"]:
            errors.append("NET_ARITHMETIC")
        draws = [a for a in actions if a["kind"] == "DRAW_LOAN"]
        repays = [
            a for a in actions if a["kind"] == "REPAY_LOAN" and "obligation_provider" not in a
        ]
        if len(draws) != 1 or len(repays) != 1:
            errors.append("DEBT_SCHEDULE")
        else:
            if repays[0]["amount_minor"] != quote["repayment_minor"]:
                errors.append("REPAYMENT_AMOUNT")
            if (
                draws[0]["cash_delta_minor"]
                != quote["principal_minor"] - terms["upfront_fee_minor"]
            ):
                errors.append("NET_FINANCING")
            if (
                draws[0]["at"] != terms["disburse_at"]
                or draws[0]["amount_minor"] != quote["principal_minor"]
            ):
                errors.append("DISBURSEMENT_TERMS")
            if (
                repays[0]["at"] != terms["repay_at"]
                or repays[0]["cash_delta_minor"] != -quote["repayment_minor"]
            ):
                errors.append("REPAYMENT_TAIL")
    elif any(
        a["kind"] != "PAY_OBLIGATION"
        and not (a["kind"] == "REPAY_LOAN" and "obligation_provider" in a)
        for a in actions
    ):
        errors.append("UNSUPPORTED_FINANCING")
    lows = []
    for scenario in scenario_set:
        events: list[tuple[str, int, str]] = [
            (a["at"], a["cash_delta_minor"], a["action_id"]) for a in actions
        ]
        for o in snap["obligations"]:
            if o["kind"] == "RECEIVABLE" and o["outstanding_minor"]:
                due = max(
                    o["due_at"],
                    (datetime.fromisoformat(snap["as_of"]) + timedelta(days=1)).isoformat(),
                )
                shock = (scenario.get("obligation_shocks") or {}).get(o["external_id"]) or (
                    scenario.get("customer_shocks") or {}
                ).get(o["counterparty"], {})
                when = (
                    datetime.fromisoformat(due)
                    + timedelta(days=shock.get("delay_days", scenario["delay_days"]))
                ).isoformat()
                receipt_paid = (
                    o["outstanding_minor"]
                    * shock.get("receipt_bps", scenario.get("receipt_bps", 10000))
                    // 10000
                )
                events.append((when, receipt_paid, o["external_id"]))
                if (
                    o["outstanding_minor"] > receipt_paid
                    and scenario.get("remainder_delay_days") is not None
                ):
                    tail = (
                        datetime.fromisoformat(when)
                        + timedelta(days=scenario["remainder_delay_days"])
                    ).isoformat()
                    events.append(
                        (
                            tail,
                            o["outstanding_minor"] - receipt_paid,
                            o["external_id"] + "_remainder",
                        )
                    )
        ordered = sorted(events, key=lambda e: (e[0], e[1] >= 0, e[2]))
        prefixes = [
            snap["confirmed_cash_minor"] + sum(e[1] for e in ordered[:end])
            for end in range(len(ordered) + 1)
        ]
        lows.append(min(prefixes))
        if min(prefixes) < snap["policy"]["reserve_minor"]:
            errors.append("HARD_RESERVE")
    if snap["quality_flags"]:
        errors.append("DATA_QUALITY")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "minimum_balances_minor": lows,
        "validator_version": "independent-prefix-oracle-v1",
        "plan_digest": digest(plan),
        "snapshot_id": snap["snapshot_id"],
    }
