"""Actual opt-in PostgreSQL + independent simulator integration, never SQLite substitution."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

from finance.domain import FinanceError, uid
from finance.ingestion import snapshot
from finance.postgres import PostgresStore, migrate, provision
from finance.worker import enqueue, work_once
from finance.workspace import settings
from finance.workflows import WorkflowEngine
from scripts.runtime import ORIGIN, PROFILE, Runtime, run_golden


@unittest.skipUnless(os.getenv("SME_POSTGRES_TEST_CONFIG"), "PostgreSQL integration not configured")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.admin_dsn = json.loads(
            Path(os.environ["SME_POSTGRES_TEST_CONFIG"]).read_text(encoding="utf-8")
        )["dsn"]
        migrate(cls.admin_dsn)

    def test_full_golden_on_postgresql_with_independent_simulator(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            tenant = uid("pg_golden")
            store, tokens = provision(
                self.admin_dsn, tenant, PROFILE, ORIGIN, directory / "observed"
            )
            with Runtime(directory, tenant=tenant, store=store, bootstrap_tokens=tokens) as runtime:
                result = run_golden(runtime, lost_response=True)
                self.assertTrue(result["independent_evaluation"]["success"])
                self.assertEqual(result["independent_evaluation"]["final_cash_minor"], 2900000)
                self.assertEqual(result["reconciliation"]["discrepancy_minor"], 0)
                self.assertEqual(len(runtime.adapter.observation()["movements"]), 6)

    def test_agent_business_reads_and_real_plan_ids_on_postgresql(self) -> None:
        from finance.agent_data import DATASETS, list_records, read_record
        from finance.agents import ToolRegistry

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            tenant = uid("pg_agent_data")
            store, tokens = provision(
                self.admin_dsn, tenant, PROFILE, ORIGIN, directory / "observed"
            )
            with Runtime(directory, tenant=tenant, store=store, bootstrap_tokens=tokens) as r:
                registry = ToolRegistry(r.service, r.ctx)
                plan = registry.call("optimize_plan", {"objective": "MIN_COST"})["result"]["plan"]
                for dataset in DATASETS:
                    page = list_records(r.service, r.ctx, dataset, "", 0)
                    for entry in page["records"]:
                        detail = read_record(r.service, r.ctx, dataset, entry["record_id"], 0)
                        self.assertEqual(detail["dataset"], dataset)
                detail = registry.call(
                    "get_plan_details", {"plan_id": plan["plan_id"], "offset": 0}
                )
                self.assertEqual(
                    detail["result"]["actions"][0]["action_id"], plan["actions"][0]["action_id"]
                )
                self.assertEqual(
                    registry.call(
                        "read_business_record",
                        {"dataset": "plans", "record_id": "foreign-plan", "offset": 0},
                    )["status"],
                    "ERROR",
                )
                with store.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
                # Populate real operational records via explicit harness approvals,
                # an independent simulator and reconciliation, then read those rows.
                self.assertTrue(
                    run_golden(r, lost_response=True)["independent_evaluation"]["success"]
                )
                for dataset in (
                    "actions",
                    "approvals",
                    "ledger",
                    "allocations",
                    "outbox",
                    "inbox",
                    "reservations",
                    "attempts",
                ):
                    page = list_records(r.service, r.ctx, dataset, "", 0)
                    self.assertGreater(page["total_matches"], 0, dataset)
                    for item in page["records"]:
                        self.assertEqual(
                            read_record(r.service, r.ctx, dataset, item["record_id"], 0)["dataset"],
                            dataset,
                        )

    def test_rls_restricted_roles_and_cross_tenant_sql(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            first, tokens = provision(
                self.admin_dsn, uid("tenant_a"), PROFILE, ORIGIN, Path(folder) / "a"
            )
            second, other_tokens = provision(
                self.admin_dsn, uid("tenant_b"), PROFILE, ORIGIN, Path(folder) / "b"
            )
            one, two = (
                first.authenticate(tokens["OWNER"]),
                second.authenticate(other_tokens["OWNER"]),
            )
            with first.connect() as db:
                rows = list(db.execute("SELECT tenant_id FROM companies"))
                self.assertEqual([row["tenant_id"] for row in rows], [one.tenant_id])
                self.assertIsNone(
                    db.execute(
                        "SELECT * FROM companies WHERE tenant_id=?", (two.tenant_id,)
                    ).fetchone()
                )
                # Even accidental missing tenant predicates cannot reveal other company rows.
                self.assertEqual(
                    db.execute(
                        "UPDATE companies SET stopped=1 WHERE tenant_id=?", (two.tenant_id,)
                    ).rowcount,
                    0,
                )
                for forbidden in [
                    "SELECT * FROM tenant_login_scopes",
                    "CREATE TABLE public.escape(x int)",
                    "ALTER TABLE companies DISABLE ROW LEVEL SECURITY",
                    "DELETE FROM audit",
                ]:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        db.execute(forbidden)
            with self.assertRaises(FinanceError):
                first.authenticate(other_tokens["OWNER"])
            with self.assertRaises(FinanceError):
                first.company(two)
            with second.connect() as db:
                self.assertEqual(db.execute("SELECT stopped FROM companies").fetchone()[0], 0)

    def test_restart_worker_graph_and_parallel_reservations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            tenant = uid("pg_recovery")
            store, tokens = provision(
                self.admin_dsn, tenant, PROFILE, ORIGIN, directory / "observed"
            )
            with Runtime(directory, tenant=tenant, store=store, bootstrap_tokens=tokens) as runtime:
                run = WorkflowEngine(runtime.service).run(
                    runtime.ctx, task="Protect reserve and plan payments"
                )
                plan = runtime.store.get_object(runtime.ctx, "plan", run["state"]["plan_id"])
                runtime.advance(1)
                command = runtime.service.command(
                    runtime.ctx, plan["plan_id"], plan["actions"][0]["action_id"]
                )
                runtime.service.approve(runtime.ctx, command)
                enqueue(runtime.service, runtime.ctx, command, "lost_response")
                self.assertEqual(
                    work_once(runtime.service, tenant, "before-crash")["status"], "UNKNOWN"
                )
                before = snapshot(store, runtime.ctx)
                settings(
                    store, runtime.ctx, {"reserve_minor": 2000001, "protected": ["salary", "rent"]}
                )
                self.assertEqual(
                    snapshot(store, runtime.ctx, ORIGIN, ORIGIN)["policy"]["reserve_minor"], 2000000
                )
                settings(
                    store, runtime.ctx, {"reserve_minor": 2000000, "protected": ["salary", "rent"]}
                )
                before = snapshot(store, runtime.ctx)
            reopened = PostgresStore(store.dsn, directory / "observed")
            with Runtime(directory, tenant=tenant, store=reopened, resume=True) as runtime:
                self.assertEqual(
                    before["snapshot_id"], snapshot(reopened, runtime.ctx)["snapshot_id"]
                )
                self.assertEqual(
                    WorkflowEngine(runtime.service).read(runtime.ctx, run["workflow_id"])["phase"],
                    "PAUSED",
                )
                runtime.settle()
                runtime.service.deliver(runtime.ctx, command["action_id"])
                self.assertEqual(len(runtime.adapter.observation()["movements"]), 1)
                runtime.advance(4)
                commands = []
                for objective in ("MIN_COST", "NO_NEW_DEBT"):
                    plan = runtime.service.make_plan(runtime.ctx, objective)["plan"]
                    action = next(a for a in plan["actions"] if a["obligation_id"] == "salary")
                    cmd = runtime.service.command(runtime.ctx, plan["plan_id"], action["action_id"])
                    runtime.service.approve(runtime.ctx, cmd)
                    commands.append(cmd)

                def prepare(value):
                    try:
                        return runtime.service.prepare(runtime.ctx, value)["status"]
                    except FinanceError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    statuses = list(pool.map(prepare, commands))
                self.assertEqual(statuses.count("RESERVED"), 1)
                self.assertIn("OBLIGATION_RESERVED", statuses)
