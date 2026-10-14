import copy
import tempfile
import unittest
from pathlib import Path

from finance.compute import optimize
from finance.ingestion import snapshot
from finance.planner import solve
from scripts.runtime import Runtime


class PlannerTests(unittest.TestCase):
    def test_cp_sat_matches_independent_enumeration_across_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            base = snapshot(runtime.store, runtime.ctx)
            for cash in (12000000, 14000000, 22000000):
                for reserve in (1000000, 2000000, 4000000):
                    for objective in ("MIN_COST", "HIGHER_RESERVE", "NO_NEW_DEBT"):
                        snap = copy.deepcopy(base)
                        snap["confirmed_cash_minor"] = cash
                        snap["policy"]["reserve_minor"] = reserve
                        expected, actual = optimize(snap, objective), solve(snap, objective)
                        self.assertEqual(expected["solver_status"], actual["solver_status"])
                        if expected["plan"]:
                            self.assertEqual(expected["plan"]["quote"], actual["plan"]["quote"])

    def test_timeout_unknown_and_repayment_tail(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            snap = snapshot(runtime.store, runtime.ctx)
            self.assertEqual(solve(snap, timeout_seconds=0)["solver_status"], "UNKNOWN")
            result = solve(snap, scenario_set=[{"scenario_id": "late", "delay_days": 25}])
            self.assertEqual(result["solver_status"], "INFEASIBLE")
