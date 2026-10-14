"""Deterministic financial compiler -> OR-Tools CP-SAT -> independent validator."""

from __future__ import annotations

import time
from importlib.metadata import version

from ortools.sat.python import cp_model

from finance.compute import (
    catalog,
    candidate,
    eligibility,
    financing,
    obligation_flows,
    plan_trajectories,
    scenarios,
)
from finance.domain import Json, minor, require
from finance.validation import validate_plan


OBJECTIVES = {
    "MIN_COST": "Lowest financing cost, then lowest principal, keeping the hard reserve in the base scenario",
    "NO_NEW_DEBT": "No financing candidates; feasible only if current cash and dates keep the hard reserve",
    "HIGHER_RESERVE": "Lowest cost keeping an explicit higher cash target (reserve_target_minor) in the base scenario",
    "PRESERVE_LIQUIDITY": "Lowest cost keeping the hard reserve in every DEMO stress scenario (f0, delay_5, delay_25)",
}


def objective_scope(
    snap: Json, objective: str, scenario_set: list[Json] | None, target: int | None
) -> tuple[list[Json], int]:
    """Shared by CP-SAT and the enumeration oracle: scenarios and cash floor per objective."""
    reserve = snap["policy"]["reserve_minor"]
    if objective == "PRESERVE_LIQUIDITY" and scenario_set is None:
        scenario_set = scenarios()
    floor = reserve
    if objective == "HIGHER_RESERVE":
        target = reserve * 5 // 4 if target is None else target
        require(
            type(target) is int and reserve <= target <= 10**12,
            "INVALID_ARGUMENTS",
            "Reserve target must be an integer at or above the hard reserve",
        )
        floor = target
    else:
        require(target is None, "INVALID_ARGUMENTS", "Reserve target applies to HIGHER_RESERVE")
    return scenario_set or [scenarios()[0]], floor


def candidate_scope(snap: Json, items: list[Json] | None, objective: str) -> Json:
    products = (
        items if items is not None else snap.get("financing_products", catalog(snap["as_of"]))
    )
    return {
        "kind": "FINITE_GRID",
        "no_new_debt_option": True,
        "products": []
        if objective == "NO_NEW_DEBT"
        else [
            {
                "product_id": p["product_id"],
                "min_minor": p["min_minor"],
                "max_minor": p["max_minor"],
                "grid_minor": p["grid_minor"],
            }
            for p in products
        ],
        "combinations": "At most one financing product; payable dates fixed at confirmed terms",
    }


def solve(
    snap: Json,
    objective: str = "MIN_COST",
    items: list[Json] | None = None,
    scenario_set: list[Json] | None = None,
    timeout_seconds: float = 5,
    reserve_target_minor: int | None = None,
) -> Json:
    require(
        objective in OBJECTIVES,
        "INVALID_OBJECTIVE",
        "Unknown objective",
    )
    require(0 <= timeout_seconds <= 30, "INVALID_ARGUMENTS", "Solver timeout must be 0–30 seconds")
    scenario_set, floor = objective_scope(snap, objective, scenario_set, reserve_target_minor)
    options: list[Json | None] = [None]
    screens = []
    for item in (
        items if items is not None else snap.get("financing_products", catalog(snap["as_of"]))
    ):
        screen = eligibility(snap["profile"], item)
        screens.append(screen)
        if (
            screen["status"] == "PASS"
            and objective != "NO_NEW_DEBT"
            and item["disburse_at"] >= snap["as_of"]
            and item["expires_at"] >= snap["as_of"]
        ):
            for principal in range(item["min_minor"], item["max_minor"] + 1, item["grid_minor"]):
                if principal > item["upfront_fee_minor"]:
                    options.append(financing(item, principal))
    plans = [candidate(snap, quote, objective) for quote in options]
    model = cp_model.CpModel()
    choose = [model.new_bool_var(f"option_{i}") for i in range(len(plans))]
    model.add_exactly_one(choose)
    prefixes = []
    minima = [snap["confirmed_cash_minor"]] * len(plans)
    # Monetary constraints are compiled before solving, not a post-hoc choice label.
    for scenario in scenario_set:
        receipts = obligation_flows(snap, scenario, False)
        option_flows = [
            receipts
            + [{"at": a["at"], "amount_minor": a["cash_delta_minor"]} for a in p["actions"]]
            for p in plans
        ]
        times = sorted({(f["at"], f["amount_minor"] >= 0) for flows in option_flows for f in flows})
        balances = [snap["confirmed_cash_minor"]] * len(plans)
        prefixes.append(sum(b * x for b, x in zip(balances, choose)))
        for stamp, incoming in times:
            for i, flows in enumerate(option_flows):
                balances[i] = minor(
                    balances[i]
                    + sum(
                        f["amount_minor"]
                        for f in flows
                        if f["at"] == stamp and (f["amount_minor"] >= 0) == incoming
                    )
                )
                minima[i] = min(minima[i], balances[i])
            # Bound expression magnitude for CP-SAT's signed 64-bit arithmetic.
            require(
                sum(abs(b) for b in balances) < 2**60,
                "SOLVER_RANGE",
                "Financial coefficients exceed safe solver range",
            )
            prefixes.append(sum(b * x for b, x in zip(balances, choose)))
    for expression in prefixes:
        model.add(expression >= floor)
    if snap["quality_flags"]:
        model.add(False)
    # Exactly one option is chosen, so its precompiled minimum is a linear term.
    low = sum(b * x for b, x in zip(minima, choose))
    costs = sum(p["total_cost_minor"] * x for p, x in zip(plans, choose))
    principals = sum((q["principal_minor"] if q else 0) * x for q, x in zip(options, choose))
    # Every objective now prices liquidity explicitly: the floor/scenario scope differs,
    # then cost and principal are minimized. No objective rewards unbounded borrowing.
    del low
    objectives = [costs, principals]
    deadline = time.monotonic() + timeout_seconds
    selected = None
    status = cp_model.UNKNOWN
    optimal = True
    for expression in objectives:
        model.minimize(expression)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0, deadline - time.monotonic())
        status = solver.solve(model)
        if status == cp_model.MODEL_INVALID:
            require(False, "MODEL_INVALID", "CP-SAT compiler produced an invalid model")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            optimal = False
            break
        selected = next(i for i, x in enumerate(choose) if solver.value(x))
        if status != cp_model.OPTIMAL:
            optimal = False
            break
        model.add(expression == solver.value(expression))
    label = (
        "OPTIMAL"
        if selected is not None and optimal
        else "FEASIBLE"
        if selected is not None
        else "INFEASIBLE"
        if status == cp_model.INFEASIBLE
        else "UNKNOWN"
    )
    plan = plans[selected] if selected is not None else None
    if plan is not None:
        validation = validate_plan(snap, plan, scenario_set)
        require(
            validation["valid"], "MODEL_INVALID", "Independent validator rejected CP-SAT result"
        )
        plan.update(
            status="VALIDATED",
            solver_status=label,
            validation=validation,
            paths=plan_trajectories(snap, plan, scenario_set),
            stress_paths=plan_trajectories(snap, plan, scenarios()),
        )
        plan["scenario_set"] = scenario_set
    return {
        "solver_status": label,
        "plan": plan,
        "solver_version": "ortools-cp-sat-" + version("ortools"),
        "candidate_count": len(plans),
        "constraint_count": len(prefixes),
        "scenario_set": scenario_set,
        "screens": screens,
        "scope": "DEMO finite product/principal grid; eligibility is not credit approval",
        "objective_implemented": OBJECTIVES[objective],
        "liquidity_floor_minor": floor,
        "validated_scenarios": [s["scenario_id"] for s in scenario_set],
        "candidate_scope": candidate_scope(snap, items, objective),
        "reason": None if plan else "No admissible plan proven under current constraints",
    }
