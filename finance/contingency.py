"""A request changes no obligation; only an observed counterparty decision can do so."""

from __future__ import annotations

import json
import sqlite3

from finance.domain import AuthContext, Json, canonical, digest, require, utc
from finance.ingestion import snapshot
from finance.planner import solve
from finance.store import Store


def request_extension(store: Store, ctx: AuthContext, fact_id: str, due_at: str) -> Json:
    snap = snapshot(store, ctx)
    obligation = next((o for o in snap["obligations"] if o["fact_id"] == fact_id), None)
    require(obligation is not None, "NOT_FOUND", "Current obligation required")
    assert obligation is not None
    due_at = utc(due_at)
    require(
        obligation["kind"] == "PAYABLE"
        and not obligation["protected"]
        and obligation["external_id"] not in snap["policy"]["protected"]
        and due_at > obligation["due_at"],
        "PROTECTED_OR_INVALID_TERMS",
        "Only unprotected payables may be proposed for extension",
    )
    request_id = "extension_request_" + digest([ctx.tenant_id, fact_id, due_at])[:24]
    hypothetical = json.loads(canonical(snap))
    for o in hypothetical["obligations"]:
        if o["fact_id"] == fact_id:
            o["due_at"] = due_at
    hypothetical["snapshot_id"] = "hypothetical_" + digest([snap["snapshot_id"], request_id])[:24]
    result = solve(hypothetical, "NO_NEW_DEBT")
    envelope = {
        "request_id": request_id,
        "status": "WAITING_OBSERVED_CONFIRMATION",
        "trigger": {"request_id": request_id, "accepted": True},
        "if_confirmed": result,
        "declined_branch": "REPLAN_OR_KEEP_ORIGINAL_TERMS",
        "executable": False,
        "source_snapshot_id": snap["snapshot_id"],
    }
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        db.execute(
            "INSERT OR IGNORE INTO extension_requests VALUES(?,?,?,?,'REQUESTED',NULL)",
            (ctx.tenant_id, request_id, fact_id, due_at),
        )
        if not db.execute(
            "SELECT 1 FROM objects WHERE tenant_id=? AND kind='contingent_plan' AND object_id=?",
            (ctx.tenant_id, request_id),
        ).fetchone():
            store.put_object(db, ctx.tenant_id, "contingent_plan", request_id, envelope)
            store.audit(
                db,
                ctx.tenant_id,
                "extension.requested",
                {
                    "request_id": request_id,
                    "obligation_fact_id": fact_id,
                    "proposed_due_at": due_at,
                },
            )
    return envelope


def observe_decisions(
    store: Store, db: sqlite3.Connection, tenant: str, events: list[Json], clock: str
) -> None:
    for event in events:
        if db.execute(
            "SELECT 1 FROM inbox WHERE tenant_id=? AND provider='sandbox_decision' AND event_id=?",
            (tenant, event["event_id"]),
        ).fetchone():
            continue
        request = db.execute(
            "SELECT r.*,f.provider,f.external_id,f.kind,f.version,f.payload FROM extension_requests r JOIN facts f ON r.tenant_id=f.tenant_id AND r.obligation_fact_id=f.fact_id WHERE r.tenant_id=? AND r.request_id=?",
            (tenant, event["request_id"]),
        ).fetchone()
        require(
            request is not None, "UNMATCHED_DECISION", "Observed decision has no scoped request"
        )
        require(
            event["obligation_id"] == request["external_id"]
            and event["due_at"] == request["proposed_due_at"]
            and event["observed_at"] <= clock,
            "DECISION_MISMATCH",
            "Decision differs from the request",
        )
        source, _ = store.source(db, tenant, "sandbox_decision", canonical(event).encode(), clock)
        status = "DECLINED"
        if event["accepted"] is True:
            latest = db.execute(
                "SELECT MAX(version) FROM facts WHERE tenant_id=? AND kind=? AND provider=? AND external_id=?",
                (tenant, request["kind"], request["provider"], request["external_id"]),
            ).fetchone()[0]
            require(
                latest == request["version"],
                "STALE_EXTENSION",
                "Obligation changed after extension request; manual review needed",
            )
            value = json.loads(request["payload"])
            value = value | {
                "original_due_at": value["due_at"],
                "due_at": event["due_at"],
                "version": latest + 1,
                "observed_time": clock,
                "event_time": clock,
            }
            store.add_fact(db, tenant, request["provider"], source, value)
            status = "CONFIRMED"
        db.execute(
            "UPDATE extension_requests SET status=?,decision_source_id=? WHERE tenant_id=? AND request_id=?",
            (status, source, tenant, request["request_id"]),
        )
        db.execute("INSERT INTO inbox VALUES(?,'sandbox_decision',?)", (tenant, event["event_id"]))
        store.audit(
            db,
            tenant,
            "extension." + status.lower(),
            {"request_id": request["request_id"], "source_id": source, "impact": "REPLAN_REQUIRED"},
        )
