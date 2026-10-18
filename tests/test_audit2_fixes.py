"""Regression tests for the second (verification) audit, 18 Oct 2026.

Each test reproduces a confirmed finding (S-10..S-13, B-03 regression, B-09..B-12,
S-01 legacy, S-07 limits) and asserts the fixed behaviour.
"""

import io
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from finance.asgi import make_app
from finance.compute import trajectory
from finance.digest_check import STEP_UP_MAX_FAILURES, approve_and_queue
from finance.domain import FinanceError, utc
from finance.ingestion import COLUMNS, parse_row
from finance.mapping import read_xlsx
from finance.workflows import MAX_CONCURRENT_RUNS, MODEL_SLOTS, WorkflowEngine
from scripts.runtime import ORIGIN, Runtime
from tests.test_audit_fixes import _approve_first_draw, _ctx


def _xlsx(cell_ref: str) -> bytes:
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData><row r="1"><c r="{cell_ref}" t="inlineStr"><is><t>x</t></is></c></row>'
        "</sheetData></worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


class AuditTwoFixTests(unittest.TestCase):
    def test_B03_trajectory_orders_same_instant_across_formats(self) -> None:
        due = utc("2026-10-05T00:00:00Z")  # "...00.000000+00:00"
        same_instant = datetime.fromisoformat(due).isoformat()  # "...00+00:00"
        self.assertNotEqual(due, same_instant)
        result = trajectory(
            1000,
            [
                {"at": due, "amount_minor": -500, "reference": "pay"},
                {"at": same_instant, "amount_minor": 500, "reference": "receipt"},
            ],
            1000,
        )
        # Outflow first at the same moment: the dip below the reserve must be visible.
        self.assertEqual(result["minimum_balance_minor"], 500)
        self.assertEqual(result["first_gap_at"], due)

    def test_B09_settlement_with_different_amount_is_not_settled(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            ctx = runtime.ctx
            queued = _approve_first_draw(runtime)
            runtime.service.deliver(ctx, queued["action_id"])
            clock = runtime.store.company(ctx)["clock"]
            runtime.admin("/admin/advance", {"clock": clock})
            observation = runtime.service.adapter.observation()
            command = runtime.service.action(ctx, queued["action_id"])["payload"]
            movement = next(
                m
                for m in observation["movements"]
                if m.get("stable_key") == command["idempotency_key"]
            )
            movement["delta"] += 100  # the bank moved a different sum than approved
            observation["cash_minor"] += 100
            runtime.service.refresh(ctx, observation)
            self.assertNotEqual(
                runtime.service.action(ctx, queued["action_id"])["status"], "SETTLED"
            )
            self.assertTrue(runtime.store.company(ctx)["stopped"])
            events = [e["event_type"] for e in runtime.store.audit_log(ctx)]
            self.assertIn("action.settlement_amount_mismatch", events)

    def test_B12_resume_refuses_when_newer_observation_arrived(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            service, ctx = runtime.service, runtime.ctx
            service.stop(ctx, True, "owner stop")
            original = service.refresh

            def refresh_then_worker_observes(c, observation=None):
                mine = original(c, observation)
                original(c)  # a worker/webhook reconciles between the two transactions
                return mine

            service.refresh = refresh_then_worker_observes  # type: ignore[method-assign]
            with self.assertRaises(FinanceError) as denied:
                service.stop(ctx, False, "resume")
            self.assertEqual(denied.exception.code, "RECONCILIATION_REQUIRED")
            self.assertTrue(runtime.store.company(ctx)["stopped"])
            service.refresh = original  # type: ignore[method-assign]
            service.stop(ctx, False, "resume")
            self.assertFalse(runtime.store.company(ctx)["stopped"])

    def test_S10_synchronous_runs_share_the_model_slot_limit(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            held = [MODEL_SLOTS.acquire(blocking=False) for _ in range(MAX_CONCURRENT_RUNS)]
            self.assertTrue(all(held))
            try:
                with self.assertRaises(FinanceError) as busy:
                    WorkflowEngine(runtime.service).run(runtime.ctx, task="cash?")
                self.assertEqual(busy.exception.code, "WORKFLOW_BUSY")
            finally:
                for _ in held:
                    MODEL_SLOTS.release()
            done = WorkflowEngine(runtime.service).run(runtime.ctx, task="cash?")
            self.assertIn("phase", done)

    def test_S13_auditor_cannot_start_pdf_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            response = client.post(
                "/v1/documents",
                json={"title": "x", "format": "pdf", "content_base64": "JVBERi0="},
                headers={"Authorization": "Bearer " + runtime.tokens["AUDITOR"]},
            )
            self.assertEqual(response.status_code, 403)

    def test_S01_legacy_cabinet_is_off_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            self.assertEqual(client.get("/legacy").status_code, 404)
            self.assertEqual(client.get("/legacy/app.js").status_code, 404)
            os.environ["SME_ENABLE_LEGACY"] = "1"
            try:
                self.assertEqual(client.get("/legacy/app.js").status_code, 200)
            finally:
                os.environ.pop("SME_ENABLE_LEGACY", None)

    def test_S07_step_up_locks_after_repeated_wrong_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            ctx = runtime.ctx
            body = {"payload_hash": "0" * 64, "confirm": True}
            for _ in range(STEP_UP_MAX_FAILURES):
                with self.assertRaises(FinanceError) as wrong:
                    approve_and_queue(runtime.service, ctx, "p", "a", body | {"reauth": "x" * 40})
                self.assertEqual(wrong.exception.code, "STEP_UP_REQUIRED")
            with self.assertRaises(FinanceError) as locked:
                approve_and_queue(
                    runtime.service, ctx, "p", "a", body | {"reauth": runtime.tokens["OWNER"]}
                )
            self.assertEqual(locked.exception.code, "STEP_UP_LOCKED")
            # Another member is not affected by the owner's lock.
            other = _ctx(runtime, "ACCOUNTANT")
            with self.assertRaises(FinanceError) as fine:
                approve_and_queue(
                    runtime.service,
                    other,
                    "p",
                    "a",
                    body | {"reauth": runtime.tokens["ACCOUNTANT"]},
                )
            self.assertNotEqual(fine.exception.code, "STEP_UP_LOCKED")

    def test_S07_sign_in_failures_are_rate_limited(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            for _ in range(20):
                self.assertEqual(client.post("/session", json={"token": "wrong"}).status_code, 401)
            blocked = client.post("/session", json={"token": runtime.tokens["OWNER"]})
            self.assertEqual(blocked.status_code, 429)

    def test_B10_xlsx_bombs_and_broken_references_are_invalid_files(self) -> None:
        for ref in ("ZZZZZZZZ1", "XFE1"):
            with self.assertRaises(FinanceError) as bomb:
                read_xlsx(_xlsx(ref))
            self.assertEqual(bomb.exception.code, "INVALID_FILE")
        self.assertEqual(read_xlsx(_xlsx("C1")), [["", "", "x"]])

    def test_B11_non_ascii_digits_are_rejected(self) -> None:
        row = {c: "" for c in COLUMNS} | {
            "kind": "PAYABLE",
            "external_id": "x",
            "version": "1",
            "event_time": ORIGIN,
            "observed_time": ORIGIN,
            "amount_minor": "١٢٣",  # Arabic-Indic digits: str.isdigit() is True
            "currency": "CNY",
            "due_at": ORIGIN,
            "counterparty": "supplier",
            "protected": "false",
            "status": "CONFIRMED",
        }
        with self.assertRaises(FinanceError) as rejected:
            parse_row(row, ORIGIN)
        self.assertEqual(rejected.exception.code, "INVALID_ROW")

    def test_audit_events_filter_matches_full_scan(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            ctx = runtime.ctx
            queued = _approve_first_draw(runtime)
            types = {"approval.created", "action.reserved"}
            fast = runtime.store.audit_events(ctx, types, contains=[queued["action_id"]])
            slow = [
                e
                for e in runtime.store.audit_log(ctx)
                if e["event_type"] in types and queued["action_id"] in e["payload"]
            ]
            self.assertEqual(fast, slow)
            self.assertTrue(fast)
            self.assertEqual(json.loads(fast[0]["payload"])["actor_role"], "OWNER")


if __name__ == "__main__":
    unittest.main()
