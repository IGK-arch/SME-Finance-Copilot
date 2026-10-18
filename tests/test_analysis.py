"""Business health analysis: integer ratios derived only from the observed snapshot."""

import tempfile
import unittest
from pathlib import Path

from finance import cases
from finance.compute import analysis
from finance.ingestion import snapshot
from scripts.runtime import Runtime


class AnalysisTests(unittest.TestCase):
    def test_golden_snapshot_health_ratios(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            a = analysis(snapshot(runtime.store, runtime.ctx))
            # 120,000 cash + 100,000 receivable − 190,000 payables.
            self.assertEqual(a["net_working_position_minor"], 3000000)
            # Lowest projected cash −70,000 against a 20,000 reserve.
            self.assertEqual(a["liquidity_buffer_minor"], -9000000)
            self.assertEqual(a["days_to_gap"], 7)
            self.assertEqual(a["payables_due_30d_minor"], 19000000)
            self.assertEqual(a["coverage_30d_bps"], 12000000 * 10000 // 19000000)
            self.assertEqual(a["receivables_aging"]["d0_30"], 10000000)
            self.assertEqual(sum(a["payables_aging"].values()), 19000000)
            self.assertEqual(a["customer_concentration"]["top"][0]["share_bps"], 10000)
            shares = [t["share_bps"] for t in a["supplier_concentration"]["top"]]
            self.assertEqual(shares, sorted(shares, reverse=True))
            self.assertTrue(all(type(v) is int for v in a["payables_aging"].values()))
            self.assertEqual(a["pnl"]["status"], "INSUFFICIENT_DATA")

    def test_overdue_bucket_and_settled_window(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            snap = snapshot(runtime.store, runtime.ctx)
            snap["as_of"] = "2026-10-07T00:00:00.000000+00:00"
            snap["facts"] = snap["facts"] + [
                {
                    "kind": "TRANSACTION",
                    "value": {
                        "status": "SETTLED",
                        "amount_minor": -500000,
                        "event_time": "2026-10-03T00:00:00.000000+00:00",
                    },
                },
                {
                    "kind": "TRANSACTION",
                    "value": {
                        "status": "PENDING",
                        "amount_minor": 700000,
                        "event_time": "2026-10-04T00:00:00.000000+00:00",
                    },
                },
            ]
            a = analysis(snap)
            # Salary (5 Oct) and rent (6 Oct) are past due on 7 Oct.
            self.assertEqual(a["payables_aging"]["overdue"], 10000000)
            self.assertEqual(a["settled_outflow_minor"], 500000)
            self.assertEqual(a["settled_inflow_minor"], 0)

    def test_home_exposes_owner_facing_health(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            view = cases.home(runtime.service, runtime.ctx)["analysis"]
            self.assertEqual(view["net_working_position"]["display"], "CNY 30,000.00")
            self.assertEqual([b["bucket"] for b in view["aging"]][0], "overdue")
            self.assertEqual(view["customers"]["top"][0]["party"], "Customer")


if __name__ == "__main__":
    unittest.main()
