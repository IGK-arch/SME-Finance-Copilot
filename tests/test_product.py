from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from finance.domain import FinanceError
from finance.ingestion import snapshot
from finance.worker import enqueue, work_once
from scripts.runtime import Runtime


class PersistentProductTests(unittest.TestCase):
    def test_backend_restart_preserves_business_state_and_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with Runtime(directory) as first:
                plan = first.service.make_plan(first.ctx)["plan"]
                first.advance(1)
                action_id = plan["actions"][0]["action_id"]
                command = first.service.command(first.ctx, plan["plan_id"], action_id)
                first.service.approve(first.ctx, command)
                enqueue(first.service, first.ctx, command, "lost_response")
                self.assertEqual(work_once(first.service, first.tenant, "one")["status"], "UNKNOWN")
                tokens = first.tokens
                before = snapshot(first.store, first.ctx)
            with Runtime(directory, resume=True) as second:
                self.assertEqual(tokens, second.tokens)
                self.assertEqual(
                    before["snapshot_id"], snapshot(second.store, second.ctx)["snapshot_id"]
                )
                second.settle()
                second.service.deliver(second.ctx, action_id)
                second.service.deliver(second.ctx, action_id)
                self.assertEqual(second.service.action(second.ctx, action_id)["status"], "SETTLED")
                self.assertEqual(len(second.adapter.observation()["movements"]), 1)
                self.assertEqual(
                    second.store.get_object(second.ctx, "plan", plan["plan_id"])["plan_id"],
                    plan["plan_id"],
                )

    def test_restart_refuses_reseed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with Runtime(Path(folder)):
                pass
            with self.assertRaises(FinanceError):
                Runtime(Path(folder))

    def test_worker_revoked_approval_cannot_send(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            plan = runtime.service.make_plan(runtime.ctx)["plan"]
            runtime.advance(1)
            command = runtime.service.command(
                runtime.ctx, plan["plan_id"], plan["actions"][0]["action_id"]
            )
            runtime.service.approve(runtime.ctx, command)
            enqueue(runtime.service, runtime.ctx, command)
            runtime.service.revoke(runtime.ctx, command["required_approval_id"])
            result = work_once(runtime.service, runtime.tenant, "revoked")
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(
                runtime.adapter.status(command["idempotency_key"])["status"], "NOT_FOUND"
            )
