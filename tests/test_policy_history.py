import tempfile
import unittest
from pathlib import Path

from finance.compute import shift
from finance.domain import FinanceError
from finance.ingestion import snapshot
from finance.workspace import settings
from scripts.runtime import ORIGIN, Runtime


class PolicyHistoryTests(unittest.TestCase):
    def test_historical_snapshot_does_not_borrow_later_reserve_policy(self):
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            old = snapshot(r.store, r.ctx)
            r.advance(1)
            settings(r.store, r.ctx, {"reserve_minor": 3000000, "protected": ["salary", "rent"]})
            current = snapshot(r.store, r.ctx)
            self.assertEqual(current["policy"]["reserve_minor"], 3000000)
            historical = snapshot(r.store, r.ctx, ORIGIN, ORIGIN)
            self.assertEqual(old["snapshot_id"], historical["snapshot_id"])
            self.assertEqual(historical["policy"]["reserve_minor"], 2000000)
            self.assertEqual(
                snapshot(r.store, r.ctx, ORIGIN, shift(ORIGIN, 1))["policy"]["reserve_minor"],
                2000000,
            )

    def test_legacy_unknown_policy_time_fails_historical_query(self):
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            # Simulate a real migration's preserved NULL observation metadata.
            with r.store.transaction() as db:
                db.execute("UPDATE policies SET observed_at=NULL")
            r.advance(1)
            self.assertEqual(snapshot(r.store, r.ctx)["policy"]["reserve_minor"], 2000000)
            with self.assertRaises(FinanceError) as failed:
                snapshot(r.store, r.ctx, ORIGIN, ORIGIN)
            self.assertEqual(failed.exception.code, "POLICY_HISTORY_UNVERIFIED")
