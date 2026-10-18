import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path

from finance.domain import FinanceError
from finance.hooks import receive
from finance.asgi import make_app
from fastapi.testclient import TestClient
from scripts.runtime import Runtime


class WebhookTests(unittest.TestCase):
    def test_T083_repeated_signed_webhook_preserves_one_movement_and_ledger_pair(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            plan = r.service.make_plan(r.ctx)["plan"]
            r.advance(1)
            command = r.service.command(r.ctx, plan["plan_id"], plan["actions"][0]["action_id"])
            r.service.approve(r.ctx, command)
            r.service.prepare(r.ctx, command)
            r.service.deliver(r.ctx, command["action_id"], "lost_response")
            r.admin("/admin/advance", {"clock": r.store.company(r.ctx)["clock"]})
            body = json.dumps({"event_id": "signed-test-wakeup"}).encode()
            stamp = str(int(time.time()))
            secret = "offline-test-signing-key"
            signature = hmac.new(
                secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            with TestClient(
                make_app(r.service, webhook=(r.ctx, secret)), base_url="http://127.0.0.1:8080"
            ) as client:
                headers = {"X-SME-Timestamp": stamp, "X-SME-Signature": signature}
                first = client.post("/hooks/sandbox", content=body, headers=headers)
                self.assertEqual(first.status_code, 200, first.text)
                self.assertFalse(first.json()["duplicate"])
                self.assertTrue(
                    client.post("/hooks/sandbox", content=body, headers=headers).json()["duplicate"]
                )
            self.assertEqual(r.service.action(r.ctx, command["action_id"])["status"], "SETTLED")
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0], 2)
                self.assertEqual(
                    db.execute("SELECT SUM(amount_minor) FROM ledger").fetchone()[0], 0
                )
            with self.assertRaises(FinanceError):
                receive(r.service, r.ctx, secret, body, stamp, "bad-signature")
