"""Synthetic harness. Owns private admin capability; never included in model tools."""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from finance.adapter import SandboxAdapter
from finance.compute import catalog, shift
from finance.domain import FinanceError, Json, canonical, require, utc
from finance.execution import ExecutionService
from finance.ingestion import COLUMNS, import_csv, snapshot
from finance.store import Store

ORIGIN = utc("2026-10-01T00:00:00Z")
PROFILE: Json = {
    "name": "苏州合成精密配件 · Synthetic B2B",
    "legal_form": "LIMITED_COMPANY",
    "jurisdiction": "CN",
    "timezone": "Asia/Shanghai",
    "currency": "CNY",
    "documents": ["synthetic_statement"],
    "demo_flag": True,
}


def golden_rows(cash_minor: int = 12000000) -> list[Json]:
    rows: list[Json] = []
    for kind, identifier, amount, due, party, beneficiary, protected in [
        ("BALANCE", "opening", cash_minor, None, "", "", False),
        ("INVOICE", "invoice_customer", 10000000, 10, "customer", "", False),
        ("RECEIVABLE", "customer_invoice", 10000000, 10, "customer", "", False),
        ("PAYABLE", "salary", 8000000, 4, "salary", "salary_v1", True),
        ("PAYABLE", "rent", 2000000, 5, "rent", "rent_v1", True),
        ("PAYABLE", "supplier", 9000000, 7, "supplier", "supplier_v1", False),
    ]:
        rows.append(
            {
                "kind": kind,
                "external_id": identifier,
                "version": 1,
                "event_time": ORIGIN,
                "observed_time": ORIGIN,
                "amount_minor": amount,
                "currency": "CNY",
                "due_at": shift(ORIGIN, due) if due is not None else "",
                "counterparty": party,
                "beneficiary_version": beneficiary,
                "reference": "",
                "protected": "true" if protected else "false",
                "status": "CONFIRMED",
            }
        )
    return rows


def csv_bytes(rows: list[Json]) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode("utf-8")


class Runtime:
    def __init__(
        self,
        directory: Path,
        *,
        delay_days: int = 0,
        cash_minor: int = 12000000,
        tenant: str = "demo_company",
        resume: bool = False,
        store: Store | None = None,
        bootstrap_tokens: dict[str, str] | None = None,
    ) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.tenant = tenant
        metadata = directory / "runtime.secret.json"
        pg_config_path = directory / "postgres.secret.json"
        if store is None and pg_config_path.exists():
            from finance.postgres import PostgresStore

            pg_config = json.loads(pg_config_path.read_text(encoding="utf-8"))
            store = PostgresStore(pg_config["dsn"], directory / "observed")
            bootstrap_tokens = pg_config["tokens"]
            require(
                pg_config["tenant"] == tenant, "WORKSPACE_MISMATCH", "PostgreSQL tenant differs"
            )
        existed = (
            metadata.exists() if store is not None else (directory / "observed/finance.db").exists()
        )
        require(not existed or resume, "WORKSPACE_EXISTS", "Use resume for an existing workspace")
        self.store = store or Store(directory / "observed/finance.db")
        if existed:
            require(
                metadata.exists(), "WORKSPACE_INCOMPLETE", "Runtime metadata missing; do not reseed"
            )
            saved = json.loads(metadata.read_text(encoding="utf-8"))
            require(saved["tenant"] == tenant, "WORKSPACE_MISMATCH", "Workspace tenant differs")
            require(
                (directory / "private/world.db").exists(),
                "WORKSPACE_INCOMPLETE",
                "Sandbox database missing; do not reseed",
            )
            self.tokens = json.loads(
                (directory / "local-login.secret.json").read_text(encoding="utf-8")
            )
            self.credentials = saved["capabilities"]
        else:
            self.tokens = bootstrap_tokens or self.store.create_company(tenant, PROFILE, ORIGIN)
            self.credentials = {
                scope: secrets.token_urlsafe(32) for scope in ("admin", "observe", "execute")
            }
            (directory / "local-login.secret.json").write_text(
                canonical(self.tokens), encoding="utf-8"
            )
            metadata.write_text(
                canonical({"tenant": tenant, "capabilities": self.credentials}), encoding="utf-8"
            )
        self.ctx = self.store.authenticate(self.tokens["OWNER"])
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["SME_SANDBOX_CAPABILITIES"] = canonical(self.credentials)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "sandbox.server",
                "--db",
                str(directory / "private/world.db"),
                "--port",
                str(port),
                "--tenant",
                tenant,
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            last_error = ""
            for _ in range(80):
                if self.process.poll() is not None:
                    detail = (
                        self.process.stderr.read().decode()
                        if self.process.stderr is not None
                        else "stderr unavailable"
                    )
                    raise RuntimeError("Sandbox process failed: " + detail)
                try:
                    if existed:
                        SandboxAdapter(self.base_url, self.credentials["observe"]).observation()
                        break
                    self.admin(
                        "/admin/seed",
                        {
                            "tenant": tenant,
                            "clock": ORIGIN,
                            "cash_minor": cash_minor,
                            "private_schedule": [
                                {
                                    "ref": "receipt_1",
                                    "at": shift(ORIGIN, 10 + delay_days),
                                    "delta": 10000000,
                                    "reference": "customer_invoice",
                                    "counterparty": "customer",
                                }
                            ],
                            "obligations": {
                                r["external_id"]: {
                                    "outstanding_minor": r["amount_minor"],
                                    "due_at": r["due_at"],
                                }
                                for r in golden_rows(cash_minor)
                                if r["kind"] == "PAYABLE"
                            },
                            "products": catalog(ORIGIN),
                        },
                    )
                    break
                except URLError as exc:
                    last_error = str(exc.reason)
                    time.sleep(0.05)
                except FinanceError as exc:
                    if not exc.retryable:
                        raise
                    last_error = exc.code
                    time.sleep(0.05)
            else:
                raise RuntimeError("Sandbox did not become ready: " + last_error)
            self.adapter = SandboxAdapter(self.base_url, self.credentials["execute"])
            self.service = ExecutionService(self.store, self.adapter)
            self.import_result = (
                {"status": "RESUMED"}
                if existed
                else import_csv(
                    self.store,
                    self.ctx,
                    csv_bytes(golden_rows(cash_minor)),
                    "synthetic_csv",
                    ORIGIN,
                    cash_minor,
                )
            )
            with self.store.transaction() as db:
                if not db.execute(
                    "SELECT 1 FROM objects WHERE tenant_id=? AND kind='product_catalog'", (tenant,)
                ).fetchone():
                    self.store.put_object(
                        db,
                        tenant,
                        "product_catalog",
                        "demo_catalog_v1",
                        {"products": catalog(ORIGIN), "observed_at": ORIGIN},
                    )
            self.service.refresh(self.ctx)
        except BaseException:
            self.close()
            raise

    def admin(self, path: str, value: Json) -> Json:
        request = Request(
            self.base_url + path,
            data=canonical(value).encode(),
            headers={
                "Authorization": "Bearer " + self.credentials["admin"],
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def advance(self, day: int) -> Json:
        self.admin("/admin/advance", {"clock": shift(ORIGIN, day)})
        return self.service.refresh(self.ctx)

    def settle(self) -> Json:
        clock = self.store.company(self.ctx)["clock"]
        self.admin("/admin/advance", {"clock": clock})
        return self.service.refresh(self.ctx)

    def close(self) -> None:
        if hasattr(self, "worker") and self.worker.poll() is None:
            self.worker.terminate()
            self.worker.wait(timeout=10)
        if hasattr(self, "process") and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        if hasattr(self, "process") and self.process.stderr:
            self.process.stderr.close()

    def start_worker(self) -> None:
        env = os.environ.copy()
        env["SME_WORKER_CONNECTION"] = canonical(
            {"base_url": self.base_url, "execute_token": self.credentials["execute"]}
        )
        env.pop("SME_SANDBOX_CAPABILITIES", None)
        if hasattr(self.store, "dsn"):
            env["SME_WORKER_DATABASE_DSN"] = self.store.dsn
        self.worker = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "finance.worker",
                "--db",
                self.store.path,
                "--tenant",
                self.tenant,
            ],
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def __enter__(self) -> Runtime:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def run_golden(runtime: Runtime, lost_response: bool = False) -> Json:
    before = snapshot(runtime.store, runtime.ctx)
    result = runtime.service.make_plan(runtime.ctx)
    plan = result["plan"]
    if plan is None:
        raise RuntimeError("Golden plan was not feasible")
    timeline = []
    for action in plan["actions"]:
        day = (
            __import__("datetime").datetime.fromisoformat(action["at"])
            - __import__("datetime").datetime.fromisoformat(ORIGIN)
        ).days
        runtime.advance(day)
        command = runtime.service.command(runtime.ctx, plan["plan_id"], action["action_id"])
        approval = runtime.service.approve(runtime.ctx, command)
        runtime.service.prepare(runtime.ctx, command)
        dispatched = runtime.service.deliver(
            runtime.ctx,
            action["action_id"],
            "lost_response" if lost_response and action["kind"] == "PAY_OBLIGATION" else "none",
        )
        timeline.append(
            {"command": command, "approval": approval, "after_send": dispatched["status"]}
        )
        runtime.settle()
        runtime.service.deliver(runtime.ctx, action["action_id"])
    after = snapshot(runtime.store, runtime.ctx)
    evaluation = runtime.admin(
        "/admin/evaluate", {"reserve_minor": before["policy"]["reserve_minor"]}
    )
    return {
        "mode": "SYNTHETIC_SANDBOX",
        "model_provider": "mock",
        "approval_mode": "scripted synthetic owner approvals",
        "before": before,
        "solver": result,
        "timeline": timeline,
        "after": after,
        "plan_status": runtime.service.plan_status(runtime.ctx, plan["plan_id"]),
        "reconciliation": runtime.service.refresh(runtime.ctx),
        "independent_evaluation": evaluation,
        "audit": runtime.store.audit_log(runtime.ctx),
        "live_model_evaluation": {
            "status": "NOT_RUN",
            "reason": "No authorized real model configured",
        },
    }
