"""Durable scoped delivery queue. Leases reduce races; provider keys prevent duplicates."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from finance.adapter import SandboxAdapter
from finance.domain import AuthContext, FinanceError, Json, require, uid
from finance.execution import ExecutionService
from finance.store import Store


def enqueue(
    service: ExecutionService, ctx: AuthContext, command: Json, fault: str = "none"
) -> Json:
    require(fault in {"none", "lost_response"}, "INVALID_ARGUMENTS", "Unsupported fault")
    service.prepare(ctx, command, job_fault=fault)
    with service.store.transaction() as db:
        service.store.authorize(db, ctx, {"OWNER"})
        db.execute(
            "INSERT OR IGNORE INTO execution_jobs(tenant_id,action_id,actor,fault) VALUES(?,?,?,?)",
            (ctx.tenant_id, command["action_id"], ctx.user_id, fault),
        )
    return service.action(ctx, command["action_id"])


def work_once(service: ExecutionService, tenant: str, worker_id: str) -> Json:
    stamp = time.time()
    with service.store.transaction() as db:
        db.execute(
            "INSERT INTO worker_health VALUES(?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET worker_id=excluded.worker_id,heartbeat=excluded.heartbeat",
            (tenant, worker_id, stamp),
        )
        db.execute(
            "INSERT OR IGNORE INTO execution_jobs(tenant_id,action_id,actor) SELECT a.tenant_id,a.action_id,p.actor FROM actions a JOIN approvals p ON a.tenant_id=p.tenant_id AND a.approval_id=p.approval_id WHERE a.tenant_id=? AND a.status NOT IN ('SETTLED','FAILED')",
            (tenant,),
        )
        row = db.execute(
            "SELECT j.*,m.role,m.active FROM execution_jobs j JOIN memberships m ON j.tenant_id=m.tenant_id AND j.actor=m.user_id WHERE j.tenant_id=? AND j.finished=0 AND j.lease_until<? AND j.next_attempt<=? ORDER BY j.next_attempt,j.action_id LIMIT 1",
            (tenant, stamp, stamp),
        ).fetchone()
        if row is None:
            return {"status": "IDLE"}
        db.execute(
            "UPDATE execution_jobs SET lease_owner=?,lease_until=?,attempts=attempts+1 WHERE tenant_id=? AND action_id=?",
            (worker_id, stamp + 30, tenant, row["action_id"]),
        )
    error = None
    status = "BLOCKED"
    try:
        ctx = AuthContext(tenant, row["actor"], row["role"])
        result = service.deliver(
            ctx, row["action_id"], row["fault"] if row["attempts"] == 0 else "none"
        )
        status = result["status"]
    except FinanceError as exc:
        error = exc.code
    except Exception:
        error = "WORKER_INTERNAL_ERROR"
    with service.store.transaction() as db:
        db.execute(
            "UPDATE execution_jobs SET lease_owner=NULL,lease_until=0,next_attempt=?,last_error=?,finished=? WHERE tenant_id=? AND action_id=? AND lease_owner=?",
            (
                time.time() + (5 if error else 1),
                error,
                int(status in {"SETTLED", "FAILED"}),
                tenant,
                row["action_id"],
                worker_id,
            ),
        )
        service.store.audit(
            db,
            tenant,
            "worker.attempt",
            {"action_id": row["action_id"], "status": status, "error": error},
        )
    return {"action_id": row["action_id"], "status": status, "error": error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = json.loads(os.environ["SME_WORKER_CONNECTION"])
    store = Store(args.db) if not os.getenv("SME_WORKER_DATABASE_DSN") else None
    if store is None:
        from finance.postgres import PostgresStore

        store = PostgresStore(os.environ["SME_WORKER_DATABASE_DSN"], Path(args.db).parent)
    service = ExecutionService(store, SandboxAdapter(config["base_url"], config["execute_token"]))
    worker_id = uid("worker")
    while True:
        result = work_once(service, args.tenant, worker_id)
        if args.once:
            print(json.dumps(result))
            break
        time.sleep(0.5)


if __name__ == "__main__":
    main()
