import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.runtime import ORIGIN, Runtime


class DeadlineTests(unittest.TestCase):
    def test_late_settled_payment_is_not_full_success(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            Runtime(Path(folder), cash_minor=22000000) as r,
        ):
            plan = r.service.make_plan(r.ctx, "NO_NEW_DEBT")["plan"]
            for action in plan["actions"]:
                day = (datetime.fromisoformat(action["at"]) - datetime.fromisoformat(ORIGIN)).days
                r.advance(max(day, 5))
                command = r.service.command(r.ctx, plan["plan_id"], action["action_id"])
                r.service.approve(r.ctx, command)
                r.service.prepare(r.ctx, command)
                r.service.deliver(r.ctx, action["action_id"])
                r.settle()
            result = r.admin("/admin/evaluate", {"reserve_minor": 2000000})
            self.assertEqual(result["remaining_payables_minor"], 0)
            self.assertGreaterEqual(result["minimum_cash_minor"], 2000000)
            self.assertEqual(result["missed_deadlines"], ["salary"])
            self.assertFalse(result["success"])
