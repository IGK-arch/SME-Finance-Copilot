"""Actual deterministic comparison; B1/B2/live-model metrics deliberately NOT_RUN."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from finance.compute import (
    candidate,
    catalog,
    eligibility,
    financing,
    forecast,
    optimize,
    plan_trajectories,
    scenarios,
)
from finance.domain import Config, Json, digest
from finance.ingestion import snapshot
from finance.validation import validate_plan
from scripts.runtime import Runtime


def evaluate_baseline_pair(snap: Json) -> Json:
    # B0: calendar need + first timely eligible product, rounded to its amount grid.
    # Same observations, allowed actions and reserve; no safeguards are weakened.
    start = time.perf_counter()
    need = forecast(snap, [scenarios()[0]])["scenarios"][0]["net_need_minor"]
    base = candidate(snap, None, "MIN_COST")
    if need:
        first_gap = forecast(snap, [scenarios()[0]])["scenarios"][0]["first_gap_at"]
        for item in catalog(snap["as_of"]):
            if (
                eligibility(snap["profile"], item)["status"] == "PASS"
                and item["disburse_at"] <= first_gap
            ):
                amount = (
                    (need + item["upfront_fee_minor"] + item["grid_minor"] - 1)
                    // item["grid_minor"]
                ) * item["grid_minor"]
                if amount <= item["max_minor"]:
                    base = candidate(snap, financing(item, amount), "MIN_COST")
                    break
    base_valid = validate_plan(snap, base, [scenarios()[0]])
    baseline_seconds = time.perf_counter() - start
    start = time.perf_counter()
    full = optimize(snap)
    full_seconds = time.perf_counter() - start
    return {
        "mode": "DETERMINISTIC_COMPUTE_ONLY",
        "baseline_observation_hash": digest(snap),
        "full_observation_hash": digest(snap),
        "scenario_ids": [s["scenario_id"] for s in scenarios()],
        "B0": {
            "valid_in_f0": base_valid["valid"],
            "cost_minor": base["total_cost_minor"],
            "paths": plan_trajectories(snap, base, scenarios()),
            "elapsed_seconds": baseline_seconds,
        },
        "optimizer": {
            "solver_status": full["solver_status"],
            "cost_minor": full["plan"]["total_cost_minor"] if full["plan"] else None,
            "paths": full["plan"]["stress_paths"] if full["plan"] else None,
            "elapsed_seconds": full_seconds,
        },
        "B1": {"status": "NOT_RUN", "reason": "Authorized live LLM unavailable"},
        "B2": {"status": "NOT_RUN", "reason": "Authorized live LLM unavailable"},
        "B3_live": {"status": "NOT_RUN", "reason": "No measured real-agent performance"},
        "limitations": [
            "Single golden template with changed starting cash is a sensitivity test, not diverse SME holdout",
            "No empirical calibration or model-quality/ROI claims",
            "No real-bank or field evidence",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/benchmark.json")
    args = parser.parse_args()
    Config.from_environment()
    runs = []
    for cash in (12000000, 14000000, 22000000):
        with tempfile.TemporaryDirectory(prefix="sme_benchmark_") as temporary:
            with Runtime(Path(temporary), cash_minor=cash) as runtime:
                runs.append(
                    {
                        "starting_cash_minor": cash,
                        "comparison": evaluate_baseline_pair(snapshot(runtime.store, runtime.ctx)),
                    }
                )
    result = {
        "schema_version": 1,
        "episode_count": len(runs),
        "runs": runs,
        "scope": "Three synthetic starting-cash sensitivity points; paired deterministic computation",
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Recorded {len(runs)} deterministic comparisons to {destination.resolve()}; live model evaluation NOT_RUN"
    )


if __name__ == "__main__":
    main()
