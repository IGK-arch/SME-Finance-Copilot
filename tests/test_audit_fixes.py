"""Regression tests for the 17 Oct 2026 code audit (R1-R8 reproductions + fixes).

Each test first reproduces the scenario that was confirmed broken, then asserts the
fixed behaviour. They use the real Runtime (store + sandbox process), like test_v03.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finance import cases, workspace
from finance.asgi import make_app
from finance.compute import shift, trajectory, obligation_flows
from finance.contingency import request_extension
from finance.digest_check import approve_and_queue
from finance.domain import FinanceError, utc
from finance.ingestion import COLUMNS, import_csv, snapshot
from finance.validation import validate_plan
from scripts.runtime import ORIGIN, Runtime, csv_bytes


def _row(**values: str) -> dict:
    return {c: "" for c in COLUMNS} | values


def scenario_f0() -> dict:
    return {"scenario_id": "f0", "delay_days": 0}


def _ctx(runtime: Runtime, role: str):
    return runtime.store.authenticate(runtime.tokens[role])


def _approve_first_draw(runtime: Runtime) -> dict:
    ctx = runtime.ctx
    cases.compute_options(runtime.service, ctx)
    plan_id = cases.select_option(runtime.service, ctx, "FINANCE_MIN_COST")["plan_id"]
    draw = runtime.store.get_object(ctx, "plan", plan_id)["actions"][0]
    runtime.advance(1)
    review = cases.review(runtime.service, ctx, plan_id, draw["action_id"])
    return approve_and_queue(
        runtime.service,
        ctx,
        plan_id,
        draw["action_id"],
        {
            "payload_hash": review["payload_hash"],
            "confirm": True,
            "reauth": runtime.tokens["OWNER"],
        },
    )


class AuditFixTests(unittest.TestCase):
    def test_R1_quarantine_review_does_not_block_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            bad = _row(
                kind="PAYABLE",
                external_id="bad1",
                version="1",
                event_time=ORIGIN,
                observed_time=ORIGIN,
                amount_minor="abc",
                currency="CNY",
                due_at=shift(ORIGIN, 6),
                counterparty="supplier",
                protected="false",
                status="CONFIRMED",
            )
            imported = import_csv(runtime.store, runtime.ctx, csv_bytes([bad]), "acct", ORIGIN)
            workspace.review(
                runtime.store,
                runtime.ctx,
                imported["import_id"],
                2,
                "DISCARD",
                "typo row, discard",
                None,
            )
            self.assertEqual(_approve_first_draw(runtime)["status"], "RESERVED")

    def test_R2_bad_counterparty_decision_does_not_break_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            ctx = runtime.ctx
            supplier = next(
                o
                for o in snapshot(runtime.store, ctx)["obligations"]
                if o["external_id"] == "supplier"
            )
            later = shift(supplier["due_at"], 10)
            envelope = request_extension(runtime.store, ctx, supplier["fact_id"], later)
            corrected = _row(
                kind="PAYABLE",
                external_id="supplier",
                version="2",
                event_time=ORIGIN,
                observed_time=ORIGIN,
                amount_minor="9100000",
                currency="CNY",
                due_at=supplier["due_at"],
                counterparty="supplier",
                beneficiary_version="supplier_v1",
                protected="false",
                status="CONFIRMED",
            )
            import_csv(
                runtime.store,
                _ctx(runtime, "ACCOUNTANT"),
                csv_bytes([corrected]),
                "synthetic_csv",
                ORIGIN,
            )
            runtime.admin(
                "/admin/extension",
                {
                    "request_id": envelope["request_id"],
                    "obligation_id": "supplier",
                    "due_at": later,
                    "accepted": True,
                },
            )
            for _ in range(2):
                self.assertIn("status", runtime.service.refresh(ctx))
            with runtime.store.connect() as db:
                status = db.execute(
                    "SELECT status FROM extension_requests WHERE request_id=?",
                    (envelope["request_id"],),
                ).fetchone()[0]
            self.assertEqual(status, "NEEDS_REVIEW")
            current = next(
                o
                for o in snapshot(runtime.store, ctx)["obligations"]
                if o["external_id"] == "supplier"
            )
            self.assertEqual(current["due_at"], supplier["due_at"])  # no fact changed

    def test_R4_R5_role_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            owner = {"Authorization": "Bearer " + runtime.tokens["OWNER"]}
            admin = {"Authorization": "Bearer " + runtime.tokens["ADMIN"]}
            auditor = {"Authorization": "Bearer " + runtime.tokens["AUDITOR"]}
            stop = {"enabled": True, "reason": "owner suspects a changed account"}
            resume = {"enabled": False, "reason": "resume"}
            self.assertEqual(
                client.post("/v1/controls/stop", json=stop, headers=owner).status_code, 200
            )
            self.assertEqual(
                client.post("/v1/controls/stop", json=resume, headers=admin).status_code, 403
            )
            self.assertTrue(runtime.store.company(runtime.ctx)["stopped"])
            self.assertEqual(
                client.post("/v1/controls/stop", json=resume, headers=owner).status_code, 200
            )
            self.assertFalse(runtime.store.company(runtime.ctx)["stopped"])
            self.assertEqual(
                client.post("/v1/reconcile", json={}, headers=auditor).status_code, 403
            )
            self.assertEqual(client.post("/v1/reconcile", json={}, headers=admin).status_code, 200)

    def test_R3_localhost_origin_is_same_origin(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://localhost:8080")
            response = client.post(
                "/session",
                json={"token": runtime.tokens["OWNER"]},
                headers={"Origin": "http://localhost:8080"},
            )
            self.assertEqual(response.status_code, 200)
            evil = client.post(
                "/session",
                json={"token": runtime.tokens["OWNER"]},
                headers={"Origin": "http://evil.example"},
            )
            self.assertEqual(evil.status_code, 403)

    def test_R6_validator_orders_ties_like_planner(self) -> None:
        as_of, due = utc("2026-10-01T00:00:00Z"), utc("2026-10-05T00:00:00Z")
        snap = {
            "as_of": as_of,
            "confirmed_cash_minor": 2000000,
            "snapshot_id": "s",
            "policy": {"reserve_minor": 2000000},
            "quality_flags": [],
            "obligations": [
                {
                    "kind": "PAYABLE",
                    "provider": "p",
                    "external_id": "pay",
                    "outstanding_minor": 500000,
                    "due_at": due,
                    "beneficiary_version": "supplier_v1",
                    "counterparty": "supplier",
                    "source_id": "x",
                    "protected": False,
                },
                {
                    "kind": "RECEIVABLE",
                    "provider": "p",
                    "external_id": "rec",
                    "outstanding_minor": 500000,
                    "due_at": due,
                    "beneficiary_version": "",
                    "counterparty": "customer",
                    "source_id": "x",
                    "protected": False,
                },
            ],
        }
        plan = {
            "quote": None,
            "actions": [
                {
                    "action_id": "a1",
                    "kind": "PAY_OBLIGATION",
                    "at": due,
                    "amount_minor": 500000,
                    "cash_delta_minor": -500000,
                    "obligation_id": "pay",
                    "obligation_provider": "p",
                    "beneficiary_version_id": "supplier_v1",
                    "dependencies": [],
                }
            ],
        }
        scenario = {"scenario_id": "f0", "delay_days": 0}
        planner_low = trajectory(
            2000000,
            obligation_flows(snap, scenario, False)
            + [{"at": due, "amount_minor": -500000, "reference": "a1"}],
            2000000,
        )["minimum_balance_minor"]
        checked = validate_plan(snap, plan, [scenario])
        self.assertEqual(checked["minimum_balances_minor"], [planner_low])
        self.assertFalse(checked["valid"])
        self.assertIn("HARD_RESERVE", checked["errors"])

    def test_R7_parallel_home_opens_one_case(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            threads = [
                threading.Thread(target=cases.home, args=(runtime.service, runtime.ctx))
                for _ in range(6)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            with runtime.store.connect() as db:
                opened = [
                    r
                    for r in db.execute("SELECT payload FROM objects WHERE kind='case_event'")
                    if '"type":"OPENED"' in r[0]
                ]
            self.assertEqual(len(opened), 1)

    def test_R8_unreachable_model_is_recorded_as_failed_run(self) -> None:
        names = ("MODEL_PROVIDER", "MODEL_NAME", "ALLOW_LOCAL_MODEL_INFERENCE", "MODEL_BASE_URL")
        saved = {k: os.environ.get(k) for k in names}
        os.environ.update(
            MODEL_PROVIDER="ollama",
            MODEL_NAME="missing-model",
            ALLOW_LOCAL_MODEL_INFERENCE="true",
            MODEL_BASE_URL="http://127.0.0.1:9",
        )
        try:
            with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
                from finance.copilot import start_background, view

                started = start_background(runtime.service, runtime.ctx, {"task": "cash?"})
                deadline = time.time() + 10
                state = None
                while time.time() < deadline:
                    try:
                        state = view(runtime.service, runtime.ctx, started["workflow_id"])
                    except FinanceError:
                        state = None
                    if state and state["statuses"]["workflow"] == "FAILED":
                        break
                    time.sleep(0.2)
                self.assertIsNotNone(state)
                assert state is not None
                self.assertEqual(state["statuses"]["workflow"], "FAILED")
                self.assertTrue(state["errors"])
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_S02_cost_cap_is_a_hard_constraint(self) -> None:
        from finance.compute import catalog, financing
        from finance.domain import MAX_ANNUALIZED_COST_BPS

        bridge = catalog(ORIGIN)[0]
        # The pre-fix golden quote (two 1,000 CNY fees on 90,000 net, 29 days) ~ 28% p.a.
        old_terms = financing(bridge | {"repayment_fee_minor": 100000}, 9100000)
        self.assertGreater(old_terms["annualized_cost_bps"], MAX_ANNUALIZED_COST_BPS)
        self.assertFalse(old_terms["within_cost_cap"])
        golden = financing(bridge, 9100000)
        self.assertEqual((golden["net_minor"], golden["repayment_minor"]), (9000000, 9100000))
        self.assertTrue(golden["within_cost_cap"])
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            snap = snapshot(runtime.store, runtime.ctx)
            plan = runtime.service.make_plan(runtime.ctx)["plan"]
            self.assertTrue(plan["quote"]["within_cost_cap"])
            # The independent validator recomputes the rate itself.
            expensive = dict(
                plan,
                quote=dict(
                    plan["quote"], terms=dict(plan["quote"]["terms"], repayment_fee_minor=100000)
                ),
            )
            self.assertIn("COST_CAP", validate_plan(snap, expensive, [scenario_f0()])["errors"])

    def test_S01_browser_session_needs_step_up_and_no_legacy_route(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            signed = client.post("/session", json={"token": runtime.tokens["OWNER"]})
            self.assertEqual(signed.status_code, 200)
            csrf = {"X-SME-Request": "1"}
            legacy = client.post("/v1/approvals", json={"command": {}}, headers=csrf)
            self.assertEqual(legacy.status_code, 403)
            dispatch = client.post("/v1/actions/x/dispatch", json={"command": {}}, headers=csrf)
            self.assertEqual(dispatch.status_code, 403)
            ctx = runtime.ctx
            cases.compute_options(runtime.service, ctx)
            plan_id = cases.select_option(runtime.service, ctx, "FINANCE_MIN_COST")["plan_id"]
            draw = runtime.store.get_object(ctx, "plan", plan_id)["actions"][0]
            runtime.advance(1)
            review = client.get(f"/v1/review/{plan_id}/{draw['action_id']}").json()["result"]
            url = f"/v1/review/{plan_id}/{draw['action_id']}/approve"
            body = {"payload_hash": review["payload_hash"], "confirm": True}
            denied = client.post(url, json=body, headers=csrf)
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json()["error"]["code"], "STEP_UP_REQUIRED")
            ok = client.post(url, json=body | {"reauth": runtime.tokens["OWNER"]}, headers=csrf)
            self.assertEqual(ok.status_code, 200, ok.text)
            self.assertEqual(ok.json()["result"]["status"], "RESERVED")

    def test_resume_requires_matching_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            ctx = runtime.ctx
            runtime.service.stop(ctx, True, "test")
            original = runtime.service.refresh

            def mismatched(c, observation=None):
                result = original(c, observation)
                return result | {"matched": False}

            runtime.service.refresh = mismatched  # type: ignore[method-assign]
            with self.assertRaises(FinanceError) as denied:
                runtime.service.stop(ctx, False, "resume")
            self.assertEqual(denied.exception.code, "RECONCILIATION_REQUIRED")
            self.assertTrue(runtime.store.company(ctx)["stopped"])

    def test_S06_audit_records_actor_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            runtime.service.stop(runtime.ctx, True, "owner stop")
            events = runtime.store.audit_log(runtime.ctx)
            stop = [e for e in events if e["event_type"] == "control.stop"][-1]
            self.assertEqual(json.loads(stop["payload"])["actor_role"], "OWNER")
            auditor = _ctx(runtime, "AUDITOR")
            self.assertTrue(runtime.store.verify_audit(auditor)["valid"])
            # Attacker with file access: the append-only trigger is bypassed, the chain is not.
            import sqlite3

            with sqlite3.connect(runtime.store.path) as db:
                db.execute("DROP TRIGGER immutable_audit_update")
                db.execute(
                    "UPDATE audit SET payload=? WHERE audit_id=?",
                    (stop["payload"].replace("OWNER", "ADMIN"), stop["audit_id"]),
                )
            broken = runtime.store.verify_audit(auditor)
            self.assertFalse(broken["valid"])
            self.assertEqual(broken["first_bad_audit_id"], stop["audit_id"])

    def test_auditor_cannot_start_copilot(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            from finance.copilot import start_background

            with self.assertRaises(FinanceError) as denied:
                start_background(runtime.service, _ctx(runtime, "AUDITOR"), {"task": "cash?"})
            self.assertEqual(denied.exception.code, "POLICY_DENIED")


if __name__ == "__main__":
    unittest.main()
