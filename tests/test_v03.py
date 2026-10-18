"""v0.3 owner main path: read models, strategies, review/approve, timeline, import mapping."""

import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from finance import cases, mapping
from finance.compute import optimize
from finance.digest_check import approve_and_queue
from finance.domain import FinanceError, digest
from finance.ingestion import snapshot
from finance.planner import solve
from finance.worker import work_once
from scripts.runtime import Runtime


def drive_worker(runtime: Runtime, rounds: int = 6) -> None:
    for _ in range(rounds):
        work_once(runtime.service, runtime.ctx.tenant_id, "test-worker")


class V03Tests(unittest.TestCase):
    def test_V03_10_V03_17_home_names_problem_date_next_action_and_dedups_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            home = cases.home(runtime.service, runtime.ctx)
            self.assertEqual(home["state"], "GAP")
            self.assertEqual(home["problem"]["need"]["minor"], 9000000)
            self.assertEqual(home["problem"]["minimum"]["minor"], -7000000)
            self.assertTrue(home["problem"]["first_gap_at"].startswith("2026-10-08"))
            self.assertEqual(home["cta"]["route"], "#case")
            drivers = home["problem"]["drivers"]
            self.assertEqual(
                {d["reference"] for d in drivers["outflows"]}, {"salary", "rent", "supplier"}
            )
            self.assertEqual(
                [d["reference"] for d in drivers["late_inflows"]], ["customer_invoice"]
            )
            self.assertTrue(all(d["source_id"].startswith("source_") for d in drivers["outflows"]))
            self.assertEqual(home["metrics"]["confirmed_cash"]["display"], "CNY 120,000.00")
            self.assertEqual(home["metrics"]["confirmed_cash"]["minor_str"], "12000000")
            types = [a["type"] for a in home["alerts"]]
            self.assertIn("CASH_GAP", types)
            # Repeating the read does not duplicate alerts or cases (idempotent first-seen).
            again = cases.home(runtime.service, runtime.ctx)
            self.assertEqual(
                [a["alert_id"] for a in again["alerts"]], [a["alert_id"] for a in home["alerts"]]
            )
            self.assertEqual(again["case"]["case_id"], home["case"]["case_id"])
            with runtime.store.connect() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM objects WHERE kind='case_event'").fetchone()[
                        0
                    ],
                    1,
                )

    def test_V03_13_strategies_are_distinct_and_oracle_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            snap = snapshot(runtime.store, runtime.ctx)
            base = solve(snap, "MIN_COST")
            self.assertEqual(base["plan"]["quote"]["principal_minor"], 9100000)
            stress = solve(snap, "PRESERVE_LIQUIDITY")
            self.assertEqual(stress["validated_scenarios"], ["f0", "delay_5", "delay_25"])
            self.assertEqual(stress["solver_status"], "INFEASIBLE")
            target = solve(snap, "HIGHER_RESERVE", reserve_target_minor=2500000)
            self.assertEqual(target["liquidity_floor_minor"], 2500000)
            self.assertEqual(target["plan"]["quote"]["principal_minor"], 9600000)
            self.assertGreater(
                target["plan"]["quote"]["principal_minor"], base["plan"]["quote"]["principal_minor"]
            )
            unreachable = solve(snap, "HIGHER_RESERVE", reserve_target_minor=6000000)
            self.assertEqual(unreachable["solver_status"], "INFEASIBLE")
            for objective, kwargs in (
                ("PRESERVE_LIQUIDITY", {}),
                ("HIGHER_RESERVE", {"reserve_target_minor": 2500000}),
            ):
                expected = optimize(snap, objective, **kwargs)
                actual = solve(snap, objective, **kwargs)
                self.assertEqual(expected["solver_status"], actual["solver_status"])
                self.assertEqual(
                    (expected["plan"] or {}).get("quote"), (actual["plan"] or {}).get("quote")
                )
            with self.assertRaises(FinanceError):
                solve(snap, "HIGHER_RESERVE", reserve_target_minor=100)
            with self.assertRaises(FinanceError):
                solve(snap, "MIN_COST", reserve_target_minor=2500000)

    def test_V03_11_options_show_executable_conditional_and_infeasible_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            snap = snapshot(runtime.store, runtime.ctx)
            supplier = next(o for o in snap["obligations"] if o["external_id"] == "supplier")
            from finance.contingency import request_extension

            request_extension(
                runtime.store, runtime.ctx, supplier["fact_id"], "2026-10-13T00:00:00Z"
            )
            data = cases.compute_options(runtime.service, runtime.ctx)
            by = {c["key"]: c for c in data["options"]}
            self.assertEqual(by["FINANCE_MIN_COST"]["status"], "EXECUTABLE")
            fin = by["FINANCE_MIN_COST"]["financing"]
            self.assertEqual(
                (fin["gross"]["minor"], fin["net"]["minor"], fin["repayment"]["minor"]),
                (9100000, 9000000, 9100000),
            )
            self.assertEqual(by["NO_NEW_DEBT"]["status"], "INFEASIBLE")
            self.assertIn(
                "SHORTFALL_WITHOUT_FINANCING", {r["code"] for r in by["NO_NEW_DEBT"]["reasons"]}
            )
            codes = {r["code"] for r in by["STRESS_RESILIENT"]["reasons"]}
            self.assertIn("REPAYMENT_CREATES_GAP", codes)
            self.assertIn("FUNDING_ARRIVES_LATE", codes)
            conditional = [c for c in data["options"] if c["status"] == "CONDITIONAL"]
            self.assertEqual(len(conditional), 1)
            self.assertFalse(conditional[0]["executable"])
            with self.assertRaises(FinanceError) as refused:
                cases.select_option(runtime.service, runtime.ctx, conditional[0]["key"])
            self.assertEqual(refused.exception.code, "OPTION_NOT_EXECUTABLE")
            with self.assertRaises(FinanceError):
                cases.select_option(runtime.service, runtime.ctx, "NO_NEW_DEBT")
            selected = cases.select_option(runtime.service, runtime.ctx, "FINANCE_MIN_COST")
            detail = cases.case_detail(runtime.service, runtime.ctx)
            self.assertEqual(detail["selected"]["plan_id"], selected["plan_id"])
            self.assertFalse(detail["options_stale"])

    def test_V03_12_review_approve_exact_payload_timeline_and_lost_response(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            cases.compute_options(runtime.service, runtime.ctx)
            plan_id = cases.select_option(runtime.service, runtime.ctx, "FINANCE_MIN_COST")[
                "plan_id"
            ]
            plan = runtime.store.get_object(runtime.ctx, "plan", plan_id)
            draw = plan["actions"][0]
            early = cases.review(runtime.service, runtime.ctx, plan_id, draw["action_id"])
            self.assertFalse(early["approvable"])
            self.assertEqual(early["block"]["code"], "PRECONDITION_FAILED")
            runtime.advance(1)
            review = cases.review(runtime.service, runtime.ctx, plan_id, draw["action_id"])
            self.assertTrue(review["approvable"])
            self.assertEqual(review["loan_terms"]["net"]["minor"], 9000000)
            self.assertEqual(review["payload_hash"], digest(review["command"]))
            with self.assertRaises(FinanceError) as mismatch:
                approve_and_queue(
                    runtime.service,
                    runtime.ctx,
                    plan_id,
                    draw["action_id"],
                    {
                        "payload_hash": "0" * 64,
                        "confirm": True,
                        "reauth": runtime.tokens["OWNER"],
                    },
                )
            self.assertEqual(mismatch.exception.code, "APPROVAL_HASH_MISMATCH")
            for wrong in (None, "", runtime.tokens["ACCOUNTANT"], "x" * 40):
                with self.assertRaises(FinanceError) as no_step_up:
                    approve_and_queue(
                        runtime.service,
                        runtime.ctx,
                        plan_id,
                        draw["action_id"],
                        {"payload_hash": review["payload_hash"], "confirm": True, "reauth": wrong},
                    )
                self.assertEqual(no_step_up.exception.code, "STEP_UP_REQUIRED")
            queued = approve_and_queue(
                runtime.service,
                runtime.ctx,
                plan_id,
                draw["action_id"],
                {
                    "payload_hash": review["payload_hash"],
                    "confirm": True,
                    "reauth": runtime.tokens["OWNER"],
                    "inject_lost_response": True,
                },
            )
            self.assertEqual(queued["status"], "RESERVED")
            drive_worker(runtime, 1)
            state = runtime.service.action(runtime.ctx, draw["action_id"])["status"]
            self.assertIn(state, {"UNKNOWN", "SUBMITTED"})
            line = cases.timeline(runtime.service, runtime.ctx, draw["action_id"])
            self.assertTrue(line["steps"][0]["done"] and line["steps"][1]["done"])
            if state == "UNKNOWN":
                home = cases.home(runtime.service, runtime.ctx)
                self.assertEqual(home["state"], "UNKNOWN_PAYMENT")
            for _ in range(4):
                runtime.settle()
                drive_worker(runtime, 2)
            line = cases.timeline(runtime.service, runtime.ctx, draw["action_id"])
            self.assertEqual(line["status"], "SETTLED")
            self.assertTrue(all(s["done"] for s in line["steps"]))
            evaluation = runtime.admin("/admin/evaluate", {"reserve_minor": 2000000})
            draws = (
                [m for m in evaluation.get("movements", []) if m.get("delta") == 9000000]
                if isinstance(evaluation, dict)
                else []
            )
            self.assertLessEqual(len(draws), 1)
            with runtime.store.connect() as db:
                ledger = db.execute(
                    "SELECT COUNT(*) FROM ledger WHERE amount_minor=9000000"
                ).fetchone()[0]
            self.assertEqual(ledger, 1)
            # A second approve of the same action cannot create a second operation.
            again = cases.review(runtime.service, runtime.ctx, plan_id, draw["action_id"])
            self.assertFalse(again["approvable"])

    def test_V03_18_what_if_changes_one_receivable_and_keeps_facts(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            before = snapshot(runtime.store, runtime.ctx)
            result = cases.what_if(
                runtime.service,
                runtime.ctx,
                {"obligation_id": "customer_invoice", "delay_days": 25, "receipt_bps": 5000},
            )
            self.assertEqual(result["label"], "SCENARIO ONLY — actual facts are unchanged")
            self.assertEqual(result["baseline"]["minimum"]["minor"], -7000000)
            after = snapshot(runtime.store, runtime.ctx)
            self.assertEqual(before["snapshot_id"], after["snapshot_id"])
            with self.assertRaises(FinanceError):
                cases.what_if(
                    runtime.service, runtime.ctx, {"obligation_id": "supplier", "delay_days": 5}
                )
            snap = snapshot(runtime.store, runtime.ctx)
            shock = {
                "scenario_id": "one",
                "delay_days": 0,
                "obligation_shocks": {"customer_invoice": {"delay_days": 25}},
            }
            from finance.compute import obligation_flows

            flows = obligation_flows(snap, shock)
            receipt = next(f for f in flows if f["reference"] == "customer_invoice")
            self.assertTrue(receipt["at"].startswith("2026-11-05"))

    def test_V03_16_mapped_csv_and_xlsx_import_with_review_and_versions(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            text = 'Invoice No,Customer,Amount,Due date,Type\nINV-7,客户乙,"12,500.50",03/04/2026,RECEIVABLE\nINV-8,Beta,1.234,2026-10-20,RECEIVABLE\n'
            value = {"template": "obligations", "format": "csv", "content": text}
            preview = mapping.preview(runtime.store, runtime.ctx, value)
            self.assertEqual(preview["mapping"]["reference"], "Invoice No")
            rows = preview["rows"]
            self.assertEqual(rows[0]["errors"][0]["code"], "AMBIGUOUS_DATE")
            self.assertEqual(rows[1]["errors"][0]["code"], "AMBIGUOUS_DECIMAL")
            value["content"] = text.replace(",1.234,", ",1234,")
            value["options"] = {"date_format": "DD/MM/YYYY"}
            preview = mapping.preview(runtime.store, runtime.ctx, value)
            self.assertEqual(preview["rows"][0]["normalized"]["amount_minor"], 1250050)
            self.assertTrue(
                preview["rows"][0]["normalized"]["due_at"].startswith("2026-04-02T16:00")
            )
            self.assertEqual(preview["rows"][1]["normalized"]["amount_minor"], 123400)
            with self.assertRaises(FinanceError):
                mapping.commit(
                    runtime.store, runtime.ctx, value | {"confirm": True, "raw_digest": "x"}
                )
            record = mapping.commit(
                runtime.store,
                runtime.ctx,
                value | {"confirm": True, "raw_digest": preview["raw_digest"]},
            )
            self.assertEqual(record["import"]["accepted"], 2)
            self.assertTrue(record["raw_source_id"].startswith("source_"))
            snap = snapshot(runtime.store, runtime.ctx)
            self.assertEqual(snap["confirmed_cash_minor"], 12000000)
            self.assertIn("INV-7", {o["external_id"] for o in snap["obligations"]})
            # Updating an existing obligation in its own namespace creates version 2.
            moved = {
                "template": "obligations",
                "format": "csv",
                "options": {"namespace": "synthetic_csv", "kind": "RECEIVABLE"},
                "content": "reference,counterparty,amount,due_date\ncustomer_invoice,customer,100000.00,2026-10-20\n",
            }
            p2 = mapping.preview(runtime.store, runtime.ctx, moved)
            self.assertEqual(p2["rows"][0]["normalized"]["version"], 2)
            self.assertIn("due_at", p2["rows"][0]["update"]["changes"])
            mapping.commit(
                runtime.store,
                runtime.ctx,
                moved | {"confirm": True, "raw_digest": p2["raw_digest"]},
            )
            receivable = next(
                o
                for o in snapshot(runtime.store, runtime.ctx)["obligations"]
                if o["external_id"] == "customer_invoice"
            )
            self.assertEqual(receivable["version"], 2)
            # XLSX path (first sheet, shared strings, numeric cells), and bad rows are quarantined.
            sheet = (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>'
                '<row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c><c r="C2"><v>500</v></c><c r="D2" t="s"><v>6</v></c></row>'
                '<row r="3"><c r="A3" t="s"><v>7</v></c><c r="B3" t="s"><v>5</v></c><c r="C3" t="s"><v>8</v></c><c r="D3" t="s"><v>6</v></c></row>'
                "</sheetData></worksheet>"
            )
            strings = [
                "reference",
                "counterparty",
                "amount",
                "due_date",
                "X-1",
                "Gamma",
                "2026-11-01",
                "X-2",
                "abc",
            ]
            shared = (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + "".join(f"<si><t>{s}</t></si>" for s in strings)
                + "</sst>"
            )
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as z:
                z.writestr("xl/worksheets/sheet1.xml", sheet)
                z.writestr("xl/sharedStrings.xml", shared)
            xlsx = {
                "template": "obligations",
                "format": "xlsx",
                "options": {"kind": "PAYABLE"},
                "content_base64": base64.b64encode(buffer.getvalue()).decode(),
            }
            p3 = mapping.preview(runtime.store, runtime.ctx, xlsx)
            self.assertEqual(p3["rows"][0]["normalized"]["amount_minor"], 50000)
            self.assertEqual(p3["rows"][1]["errors"][0]["code"], "INVALID_AMOUNT")
            result = mapping.commit(
                runtime.store, runtime.ctx, xlsx | {"confirm": True, "raw_digest": p3["raw_digest"]}
            )
            self.assertEqual(result["import"]["status"], "REVIEW_REQUIRED")
            self.assertEqual(cases.home(runtime.service, runtime.ctx)["state"], "DATA_REVIEW")

    def test_V03_09_case_records_changes_and_context_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            first = cases.home(runtime.service, runtime.ctx)["case"]
            moved = {
                "template": "obligations",
                "format": "csv",
                "options": {"namespace": "synthetic_csv", "kind": "RECEIVABLE"},
                "content": "reference,counterparty,amount,due_date\ncustomer_invoice,customer,100000.00,2026-10-05\n",
            }
            p = mapping.preview(runtime.store, runtime.ctx, moved)
            mapping.commit(
                runtime.store, runtime.ctx, moved | {"confirm": True, "raw_digest": p["raw_digest"]}
            )
            second = cases.home(runtime.service, runtime.ctx)
            self.assertEqual(second["case"]["case_id"], first["case_id"])
            history = [h["type"] for h in second["case"]["history"]]
            self.assertIn("PROBLEM_CHANGED", history)
            cases.save_context(
                runtime.service, runtime.ctx, {"route": "#case", "option_key": "FINANCE_MIN_COST"}
            )
            self.assertEqual(
                cases.load_context(runtime.service, runtime.ctx)["context"]["route"], "#case"
            )
            with self.assertRaises(FinanceError):
                cases.save_context(runtime.service, runtime.ctx, {"route": "<script>"})

    def test_V03_09_case_closes_honestly_when_gap_disappears_from_data(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            opened = cases.home(runtime.service, runtime.ctx)["case"]["case_id"]
            moved = {
                "template": "obligations",
                "format": "csv",
                "options": {"namespace": "synthetic_csv", "kind": "PAYABLE"},
                "content": "reference,counterparty,amount,due_date\nsupplier,supplier,90000.00,2026-12-31\n",
            }
            p = mapping.preview(runtime.store, runtime.ctx, moved)
            mapping.commit(
                runtime.store, runtime.ctx, moved | {"confirm": True, "raw_digest": p["raw_digest"]}
            )
            home = cases.home(runtime.service, runtime.ctx)
            self.assertIsNone(home["case"])
            detail = cases.case_detail(runtime.service, runtime.ctx)
            self.assertEqual(detail["last_closed"]["case_id"], opened)
            self.assertEqual(detail["last_closed"]["closed_reason"], "NO_LONGER_DETECTED_IN_DATA")

    def test_V03_20_real_time_approval_ttl_with_frozen_business_clock(self) -> None:
        from unittest import mock

        from finance import execution

        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            cases.compute_options(runtime.service, runtime.ctx)
            plan_id = cases.select_option(runtime.service, runtime.ctx, "FINANCE_MIN_COST")[
                "plan_id"
            ]
            runtime.advance(1)
            draw = runtime.store.get_object(runtime.ctx, "plan", plan_id)["actions"][0]
            command = runtime.service.command(runtime.ctx, plan_id, draw["action_id"])
            runtime.service.approve(runtime.ctx, command)
            later = execution.time.time() + execution.APPROVAL_REAL_TTL_SECONDS + 60
            with mock.patch.object(execution.time, "time", return_value=later):
                with self.assertRaises(FinanceError) as expired:
                    runtime.service.prepare(runtime.ctx, command)
                self.assertEqual(expired.exception.code, "APPROVAL_INVALID")
                runtime.service.approve(runtime.ctx, command)  # explicit owner re-approval renews
                self.assertEqual(
                    runtime.service.prepare(runtime.ctx, command)["status"], "RESERVED"
                )

    def test_V03_02_health_reports_actual_backend(self) -> None:
        from finance.api import dispatch

        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            health = dispatch(runtime.service, runtime.ctx, "GET", "/v1/health", {})
            self.assertEqual(health["database"]["backend"], "sqlite")
            self.assertEqual(runtime.store.backend, "sqlite")

    def test_V03_15_cookie_session_refresh_revoke_and_csrf(self) -> None:
        from fastapi.testclient import TestClient
        from finance.asgi import make_app

        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            self.assertEqual(client.post("/session", json={"token": "wrong"}).status_code, 401)
            signed = client.post("/session", json={"token": runtime.tokens["OWNER"]})
            self.assertEqual(signed.status_code, 200)
            self.assertIn("httponly", signed.headers["set-cookie"].lower())
            self.assertIn("samesite=strict", signed.headers["set-cookie"].lower())
            self.assertEqual(client.get("/v1/home").status_code, 200)  # survives "refresh"
            self.assertEqual(
                client.post("/v1/context", json={"route": "#home"}).status_code, 403
            )  # no CSRF header
            self.assertEqual(
                client.post(
                    "/v1/context", json={"route": "#home"}, headers={"X-SME-Request": "1"}
                ).status_code,
                200,
            )
            cross = client.post(
                "/v1/context",
                json={"route": "#x"},
                headers={"X-SME-Request": "1", "Origin": "http://evil.test"},
            )
            self.assertEqual(cross.status_code, 403)
            client.post("/session/logout")
            self.assertEqual(client.get("/v1/home").status_code, 401)
            # Membership deactivation ends an existing session immediately.
            client.post("/session", json={"token": runtime.tokens["ACCOUNTANT"]})
            with runtime.store.transaction() as db:
                db.execute("UPDATE memberships SET active=0 WHERE user_id='accountant'")
            self.assertEqual(client.get("/v1/home").status_code, 401)

    def test_V03_05_background_copilot_shows_results_without_narrative(self) -> None:
        import time
        import threading
        from contextlib import ExitStack
        from unittest.mock import patch
        from finance.copilot import start_background, view

        with (
            tempfile.TemporaryDirectory() as folder,
            Runtime(Path(folder)) as runtime,
            ExitStack() as background,
        ):
            thread_type = threading.Thread

            def start_thread(*args, **kwargs):
                thread = thread_type(*args, **kwargs)

                def finish():
                    # A visible terminal checkpoint can precede connection close.
                    # Join the actual worker before deleting its SQLite files.
                    thread.join(timeout=60)
                    self.assertFalse(thread.is_alive(), "Background Copilot did not finish")

                background.callback(finish)
                return thread

            with patch("finance.copilot.threading.Thread", side_effect=start_thread):
                started = start_background(
                    runtime.service,
                    runtime.ctx,
                    {"task": "How much cash do we have?", "context": {"route": "#home"}},
                )
            self.assertIn("Server-verified UI context", started["task"])
            deadline = time.time() + 60
            result = None
            while time.time() < deadline:
                try:
                    result = view(runtime.service, runtime.ctx, started["workflow_id"])
                    if result["statuses"]["workflow"] not in {"RUNNING"}:
                        break
                except FinanceError:
                    pass
                time.sleep(0.5)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["provider"], "mock")
            self.assertTrue(any(c["type"] in {"cash", "plan", "forecast"} for c in result["cards"]))
            with self.assertRaises(FinanceError):
                from finance.copilot import compose_task

                compose_task(runtime.service, runtime.ctx, "x", {"plan_id": "plan_invented"})


if __name__ == "__main__":
    unittest.main()
