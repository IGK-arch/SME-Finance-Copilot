"""K15: settlement must prove the exact approved operation, not only its cash delta."""

import copy
import tempfile
import unittest
from pathlib import Path

from finance import cases
from finance.digest_check import approve_and_queue
from finance.domain import FinanceError
from finance.execution import ExecutionService
from finance.ingestion import snapshot
from finance.store import Store
from finance.worker import work_once
from scripts.runtime import ORIGIN, PROFILE, Runtime


class SettlementIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temp.name))
        self.service, self.ctx = self.runtime.service, self.runtime.ctx
        cases.compute_options(self.service, self.ctx)
        selected = cases.select_option(self.service, self.ctx, "FINANCE_MIN_COST")
        self.plan = self.runtime.store.get_object(self.ctx, "plan", selected["plan_id"])

    def tearDown(self) -> None:
        self.runtime.close()
        self.temp.cleanup()

    def submit(self, index: int, fault: str = "none") -> dict:
        action = self.plan["actions"][index]
        self.runtime.admin("/admin/advance", {"clock": action["at"]})
        self.service.refresh(self.ctx)
        review = cases.review(self.service, self.ctx, self.plan["plan_id"], action["action_id"])
        approve_and_queue(
            self.service,
            self.ctx,
            self.plan["plan_id"],
            action["action_id"],
            {
                "confirm": True,
                "reauth": self.runtime.tokens["OWNER"],
                "payload_hash": review["payload_hash"],
            },
        )
        self.service.deliver(self.ctx, action["action_id"], fault)
        return self.service.action(self.ctx, action["action_id"])["payload"]

    def observation(self, index: int, fault: str = "none") -> tuple[dict, dict, dict]:
        for n in range(index):
            self.submit(n)
            self.runtime.settle()
        command = self.submit(index, fault)
        self.runtime.admin("/admin/advance", {"clock": command["at"]})
        observed = self.service.adapter.observation()
        movement = next(
            m for m in observed["movements"] if m.get("stable_key") == command["idempotency_key"]
        )
        return command, observed, movement

    def assert_blocked(self, command: dict, observed: dict, field: str) -> dict:
        result = self.service.refresh(self.ctx, observed)
        action = self.service.action(self.ctx, command["action_id"])
        self.assertEqual(action["status"], "UNKNOWN")
        self.assertIn(field, action["settlement_issue"]["mismatch_fields"])
        self.assertFalse(result["matched"])
        self.assertTrue(result["cash_matched"])
        self.assertEqual(result["discrepancy_minor"], 0)
        self.assertTrue(self.runtime.store.company(self.ctx)["stopped"])
        with self.runtime.store.connect() as db:
            hold = db.execute(
                "SELECT * FROM reservations WHERE tenant_id=? AND action_id=?",
                (self.ctx.tenant_id, command["action_id"]),
            ).fetchone()
            self.assertEqual(hold["status"], "ACTIVE")
            self.assertEqual(hold["included_in_provider_available"], 0)
            pair = db.execute(
                "SELECT COUNT(*), SUM(amount_minor) FROM ledger WHERE tenant_id=? AND entry_id=?",
                (self.ctx.tenant_id, action["settlement_issue"]["provider_ref"]),
            ).fetchone()
            self.assertEqual(tuple(pair), (2, 0))
        snap = snapshot(self.runtime.store, self.ctx)
        self.assertEqual(snap["confirmed_cash_minor"], observed["cash_minor"])
        self.assertNotEqual(
            self.service.plan_status(self.ctx, self.plan["plan_id"])["status"], "COMPLETED"
        )
        self.assertNotEqual(
            cases.plan_progress(self.service, self.ctx, self.plan["plan_id"])["status"], "COMPLETED"
        )
        home = cases.home(self.service, self.ctx)
        self.assertTrue(any(a["type"] == "RECONCILIATION_MISMATCH" for a in home["alerts"]))
        timeline = cases.timeline(self.service, self.ctx, command["action_id"])
        self.assertIn("needs review", timeline["message"])
        self.assertNotIn("response was lost", timeline["message"])
        self.assertFalse(timeline["can_check_status"])
        self.assertFalse(timeline["reconciliation"]["matched"])
        return action

    def test_wrong_payee_keeps_cash_and_obligation_open(self) -> None:
        command, obs, movement = self.observation(1)
        movement["counterparty"] = "wrong_recipient"
        self.assert_blocked(command, obs, "counterparty")
        salary = next(
            o
            for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            if o["external_id"] == "salary"
        )
        self.assertEqual(salary["outstanding_minor"], 8000000)

    def test_wrong_reference_does_not_allocate_another_bill(self) -> None:
        command, obs, movement = self.observation(1)
        movement.update(reference="rent", counterparty="rent")
        self.assert_blocked(command, obs, "reference")
        outstanding = {
            o["external_id"]: o["outstanding_minor"]
            for o in snapshot(self.runtime.store, self.ctx)["obligations"]
        }
        self.assertEqual((outstanding["salary"], outstanding["rent"]), (8000000, 2000000))

    def test_wrong_payment_reference_alone_is_not_settled(self) -> None:
        command, obs, movement = self.observation(1)
        movement["reference"] = "unrelated_payroll"
        self.assert_blocked(command, obs, "reference")

    def test_wrong_draw_reference_does_not_invent_confirmed_debt(self) -> None:
        command, obs, movement = self.observation(0)
        movement["reference"] = "unrelated_loan"
        self.assert_blocked(command, obs, "reference")
        self.assertFalse(
            any(
                o["external_id"].endswith("_debt")
                for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            )
        )

    def test_wrong_draw_counterparty_is_not_settled(self) -> None:
        command, obs, movement = self.observation(0)
        movement["counterparty"] = "unrelated_lender"
        self.assert_blocked(command, obs, "counterparty")

    def test_wrong_repayment_reference_keeps_debt_open(self) -> None:
        command, obs, movement = self.observation(4)
        movement["reference"] = "different_debt"
        self.assert_blocked(command, obs, "reference")
        debt = next(
            o
            for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            if o["external_id"] == command["obligation_id"]
        )
        self.assertEqual(debt["outstanding_minor"], command["amount_minor"])

    def test_wrong_repayment_payee_keeps_debt_open(self) -> None:
        command, obs, movement = self.observation(4)
        movement["counterparty"] = "different_lender"
        self.assert_blocked(command, obs, "counterparty")
        debt = next(
            o
            for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            if o["external_id"] == command["obligation_id"]
        )
        self.assertEqual(debt["outstanding_minor"], command["amount_minor"])

    def test_disputed_debit_restores_local_reserve_after_provider_hold(self) -> None:
        self.submit(0)
        self.runtime.settle()
        command = self.submit(1)
        self.service.refresh(self.ctx)
        with self.runtime.store.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT included_in_provider_available FROM reservations WHERE tenant_id=? AND action_id=?",
                    (self.ctx.tenant_id, command["action_id"]),
                ).fetchone()[0],
                1,
            )
        self.runtime.admin("/admin/advance", {"clock": command["at"]})
        obs = self.service.adapter.observation()
        movement = next(
            m for m in obs["movements"] if m.get("stable_key") == command["idempotency_key"]
        )
        movement["counterparty"] = "wrong_recipient"
        self.assert_blocked(command, obs, "counterparty")

    def test_conflicting_key_and_provider_ref_do_not_pick_first_row(self) -> None:
        command, obs, movement = self.observation(1)
        draw = self.service.action(self.ctx, self.plan["actions"][0]["action_id"])
        movement["stable_key"] = draw["idempotency_key"]
        self.assert_blocked(command, obs, "ambiguous_operation")
        # A past settled action is not rolled back to hide the new inconsistency.
        self.assertEqual(self.service.action(self.ctx, draw["action_id"])["status"], "SETTLED")

    def test_missing_stable_key_cannot_be_confirmed_by_ref_only(self) -> None:
        command, obs, movement = self.observation(1)
        movement.pop("stable_key")
        self.assert_blocked(command, obs, "stable_key")

    def test_unexpected_provider_ref_cannot_override_the_known_ref(self) -> None:
        command, obs, movement = self.observation(1)
        movement["ref"] = "unexpected_provider_ref"
        self.assert_blocked(command, obs, "provider_ref")

    def test_amount_mismatch_keeps_actual_cash_without_confirmed_debt(self) -> None:
        command, obs, movement = self.observation(0)
        movement["delta"] += 100
        obs["cash_minor"] += 100
        self.assert_blocked(command, obs, "amount")
        self.assertFalse(
            any(
                o["external_id"].endswith("_debt")
                for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            )
        )

    def test_dispute_survives_replay_restart_status_and_resume(self) -> None:
        command, obs, movement = self.observation(1, "lost_response")
        original = copy.deepcopy(obs)
        movement["counterparty"] = "wrong_recipient"
        self.assert_blocked(command, obs, "counterparty")
        restarted = ExecutionService(Store(self.runtime.store.path), self.service.adapter)
        for again in [obs, obs, original]:
            self.assertFalse(restarted.refresh(self.ctx, again)["matched"])
        for status in ["FAILED", "SETTLED", "SUBMITTED", "UNKNOWN"]:
            restarted._record_result(
                self.ctx, command["action_id"], {"status": status, "ref": movement["ref"]}
            )
            self.assertEqual(restarted.action(self.ctx, command["action_id"])["status"], "UNKNOWN")
        with self.assertRaises(FinanceError) as blocked:
            restarted.deliver(self.ctx, command["action_id"])
        self.assertEqual(blocked.exception.code, "RECONCILIATION_REQUIRED")
        with self.assertRaises(FinanceError) as stopped:
            restarted.stop(self.ctx, False, "cash balances match")
        self.assertEqual(stopped.exception.code, "RECONCILIATION_REQUIRED")
        attempts = restarted.action(self.ctx, command["action_id"])["attempts"]
        # Completed prerequisites can still have an unfinished queue row. Drain it,
        # then confirm the actual worker blocks the disputed command without a send.
        for _ in range(2):
            job = work_once(restarted, self.ctx.tenant_id, "settlement_test")
            if job.get("action_id") == command["action_id"]:
                break
        self.assertEqual(job["action_id"], command["action_id"])
        self.assertEqual(job["status"], "BLOCKED")
        self.assertEqual(job["error"], "RECONCILIATION_REQUIRED")
        self.assertEqual(restarted.action(self.ctx, command["action_id"])["attempts"], attempts)
        with self.runtime.store.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM ledger WHERE tenant_id=? AND entry_id=?",
                    (self.ctx.tenant_id, movement["ref"]),
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM objects WHERE tenant_id=? AND kind='settlement_issue'",
                    (self.ctx.tenant_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM reservations WHERE tenant_id=? AND action_id=?",
                    (self.ctx.tenant_id, command["action_id"]),
                ).fetchone()[0],
                "ACTIVE",
            )

    def test_settlement_issues_are_tenant_scoped(self) -> None:
        command, obs, movement = self.observation(1)
        movement["counterparty"] = "wrong_recipient"
        self.assert_blocked(command, obs, "counterparty")
        tokens = self.runtime.store.create_company("other_company", PROFILE, ORIGIN)
        other = self.runtime.store.authenticate(tokens["OWNER"])
        result = self.service.refresh(
            other, {"clock": ORIGIN, "cash_minor": 0, "available_minor": 0, "movements": []}
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["settlement_issues"], [])
        self.assertFalse(self.runtime.store.company(other)["stopped"])

    def test_valid_lost_response_settles_once_and_releases_hold(self) -> None:
        command, obs, movement = self.observation(1, "lost_response")
        for _ in range(3):
            result = self.service.refresh(self.ctx, obs)
            self.assertTrue(result["matched"])
        self.assertEqual(self.service.action(self.ctx, command["action_id"])["status"], "SETTLED")
        salary = next(
            o
            for o in snapshot(self.runtime.store, self.ctx)["obligations"]
            if o["external_id"] == "salary"
        )
        self.assertEqual(salary["outstanding_minor"], 0)
        with self.runtime.store.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM ledger WHERE tenant_id=? AND entry_id=?",
                    (self.ctx.tenant_id, movement["ref"]),
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM reservations WHERE tenant_id=? AND action_id=?",
                    (self.ctx.tenant_id, command["action_id"]),
                ).fetchone()[0],
                "RELEASED",
            )


if __name__ == "__main__":
    unittest.main()
