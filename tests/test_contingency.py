import tempfile
import unittest
from pathlib import Path

from finance.contingency import request_extension
from finance.compute import shift
from finance.domain import FinanceError
from finance.ingestion import snapshot
from scripts.runtime import ORIGIN, Runtime, run_golden


class ContingencyTests(unittest.TestCase):
    def test_T051_branch_activates_only_after_observed_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            before = snapshot(r.store, r.ctx)
            supplier = next(o for o in before["obligations"] if o["external_id"] == "supplier")
            branch = request_extension(r.store, r.ctx, supplier["fact_id"], shift(ORIGIN, 12))
            self.assertFalse(branch["executable"])
            self.assertEqual(branch["if_confirmed"]["solver_status"], "OPTIMAL")
            self.assertEqual(snapshot(r.store, r.ctx)["snapshot_id"], before["snapshot_id"])
            with self.assertRaises(FinanceError):
                r.service.command(r.ctx, branch["if_confirmed"]["plan"]["plan_id"], "fake")
            r.admin(
                "/admin/extension",
                {
                    "request_id": branch["request_id"],
                    "obligation_id": "supplier",
                    "due_at": shift(ORIGIN, 12),
                    "accepted": True,
                },
            )
            self.assertEqual(snapshot(r.store, r.ctx)["snapshot_id"], before["snapshot_id"])
            r.service.refresh(r.ctx)
            after = snapshot(r.store, r.ctx)
            self.assertNotEqual(after["snapshot_id"], before["snapshot_id"])
            result = r.service.make_plan(r.ctx, "NO_NEW_DEBT")
            self.assertEqual(result["solver_status"], "OPTIMAL")
            self.assertIsNone(result["plan"]["quote"])
            r.service.refresh(r.ctx)
            self.assertEqual(snapshot(r.store, r.ctx)["snapshot_id"], after["snapshot_id"])
            executed = run_golden(r)
            self.assertTrue(executed["independent_evaluation"]["success"])
            self.assertEqual(executed["independent_evaluation"]["final_cash_minor"], 3000000)

    def test_decline_preserves_original_terms(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            snap = snapshot(r.store, r.ctx)
            supplier = next(o for o in snap["obligations"] if o["external_id"] == "supplier")
            branch = request_extension(r.store, r.ctx, supplier["fact_id"], shift(ORIGIN, 12))
            r.admin(
                "/admin/extension",
                {
                    "request_id": branch["request_id"],
                    "obligation_id": "supplier",
                    "due_at": shift(ORIGIN, 12),
                    "accepted": False,
                },
            )
            r.service.refresh(r.ctx)
            self.assertEqual(snapshot(r.store, r.ctx)["obligations"], snap["obligations"])
            self.assertEqual(
                r.service.make_plan(r.ctx, "NO_NEW_DEBT")["solver_status"], "INFEASIBLE"
            )
