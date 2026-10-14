"""Authorized product actions, reviewed data and source-scoped retrieval."""

from __future__ import annotations

import json
import re
import subprocess
import sys

from finance.compute import catalog, eligibility, forecast, metrics
from finance.domain import AuthContext, FinanceError, Json, canonical, minor, now, require, uid, utc
from finance.ingestion import parse_row, snapshot
from finance.store import READ_ROLES, Store


def imports(store: Store, ctx: AuthContext) -> Json:
    with store.connect() as db:
        store.authorize(db, ctx)
        batches = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM imports WHERE tenant_id=? ORDER BY rowid DESC", (ctx.tenant_id,)
            )
        ]
        for batch in batches:
            batch["rows"] = [
                dict(r)
                for r in db.execute(
                    "SELECT q.*,d.decision,d.reason,d.corrected_source_id FROM quarantine q LEFT JOIN review_decisions d ON q.tenant_id=d.tenant_id AND q.import_id=d.import_id AND q.row_number=d.row_number WHERE q.tenant_id=? AND q.import_id=?",
                    (ctx.tenant_id, batch["import_id"]),
                )
            ]
            for row in batch["rows"]:
                row["raw"] = json.loads(row["raw"])
            batch["open_rows"] = sum(r["decision"] is None for r in batch["rows"])
            batch["review_status"] = (
                "RESOLVED" if batch["rows"] and not batch["open_rows"] else batch["status"]
            )
        return {"imports": batches}


def review(
    store: Store,
    ctx: AuthContext,
    import_id: str,
    row_number: int,
    decision: str,
    reason: str,
    corrected: Json | None,
) -> Json:
    require(
        decision in {"CORRECT", "DISCARD"} and isinstance(reason, str) and 5 <= len(reason) <= 1000,
        "INVALID_REVIEW",
        "Decision and substantive review reason required",
    )
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        row = db.execute(
            "SELECT q.*,s.provider FROM quarantine q JOIN imports i ON q.tenant_id=i.tenant_id AND q.import_id=i.import_id JOIN sources s ON i.tenant_id=s.tenant_id AND i.source_id=s.source_id WHERE q.tenant_id=? AND q.import_id=? AND q.row_number=?",
            (ctx.tenant_id, import_id, row_number),
        ).fetchone()
        require(row is not None, "NOT_FOUND", "Scoped quarantine row not found")
        require(
            not db.execute(
                "SELECT 1 FROM review_decisions WHERE tenant_id=? AND import_id=? AND row_number=?",
                (ctx.tenant_id, import_id, row_number),
            ).fetchone(),
            "ALREADY_REVIEWED",
            "Review already recorded",
        )
        clock = db.execute(
            "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()[0]
        source_id = None
        if decision == "CORRECT":
            require(isinstance(corrected, dict), "INVALID_REVIEW", "Corrected CSV fields required")
            assert corrected is not None
            value = parse_row(corrected, clock)
            original = json.loads(row["raw"])
            require(
                value["kind"] == original["kind"]
                and value["external_id"] == original["external_id"],
                "INVALID_REVIEW",
                "Correction must preserve the economic identity",
            )
            source_id, _ = store.source(
                db,
                ctx.tenant_id,
                "review",
                canonical({"row": corrected, "reason": reason, "import_id": import_id}).encode(),
                clock,
            )
            store.add_fact(db, ctx.tenant_id, row["provider"], source_id, value)
        db.execute(
            "INSERT INTO review_decisions VALUES(?,?,?,?,?,?,?,?)",
            (ctx.tenant_id, import_id, row_number, ctx.user_id, decision, reason, source_id, clock),
        )
        store.audit(
            db,
            ctx.tenant_id,
            "data.reviewed",
            {
                "import_id": import_id,
                "row_number": row_number,
                "decision": decision,
                "source_id": source_id,
            },
        )
        db.execute(
            "UPDATE companies SET data_version=data_version+1 WHERE tenant_id=?", (ctx.tenant_id,)
        )
    return {"decision": decision, "source_id": source_id, "snapshot": snapshot(store, ctx)}


def settings(store: Store, ctx: AuthContext, update: Json | None = None) -> Json:
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER"} if update is not None else None)
        policy = store.policy(db, ctx.tenant_id)
        if update is not None:
            require(
                set(update) == {"reserve_minor", "protected"},
                "INVALID_ARGUMENTS",
                "Reserve and protected references required",
            )
            reserve = minor(update["reserve_minor"])
            require(
                0 <= reserve <= 10**12
                and isinstance(update["protected"], list)
                and all(isinstance(x, str) and len(x) <= 160 for x in update["protected"]),
                "INVALID_POLICY",
                "Invalid reserve or protection list",
            )
            policy = policy | update | {"version": uid("policy")}
            db.execute(
                "INSERT INTO policies(tenant_id,version,payload,observed_at) VALUES(?,?,?,?)",
                (
                    ctx.tenant_id,
                    policy["version"],
                    canonical(policy),
                    db.execute(
                        "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
                    ).fetchone()[0],
                ),
            )
            store.audit(db, ctx.tenant_id, "policy.changed", policy)
        roles = [
            dict(r)
            for r in db.execute(
                "SELECT user_id,role,active FROM memberships WHERE tenant_id=?", (ctx.tenant_id,)
            )
        ]
        return {"policy": policy, "memberships": roles}


def add_document(
    store: Store,
    ctx: AuthContext,
    title: str,
    text: str,
    roles: list[str] | None = None,
    document_id: str | None = None,
) -> Json:
    require(
        isinstance(title, str)
        and 0 < len(title) <= 200
        and isinstance(text, str)
        and 0 < len(text) <= 200000,
        "INVALID_DOCUMENT",
        "Title and bounded extracted text required",
    )
    roles = roles or sorted(READ_ROLES)
    require(
        set(roles) <= READ_ROLES and ctx.role in roles,
        "INVALID_DOCUMENT",
        "Document permissions invalid",
    )
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        clock = db.execute(
            "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()[0]
        document_id = document_id or uid("document")
        previous = db.execute(
            "SELECT version,read_roles FROM documents WHERE tenant_id=? AND document_id=? ORDER BY version DESC LIMIT 1",
            (ctx.tenant_id, document_id),
        ).fetchone()
        require(
            previous is None or ctx.role in json.loads(previous["read_roles"]),
            "POLICY_DENIED",
            "Document access denied",
        )
        version = previous["version"] + 1 if previous else 1
        source_id, _ = store.source(
            db,
            ctx.tenant_id,
            "document",
            canonical(
                {"document_id": document_id, "version": version, "title": title, "text": text}
            ).encode(),
            clock,
        )
        db.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)",
            (ctx.tenant_id, document_id, version, source_id, title, text, canonical(roles), clock),
        )
        store.audit(
            db,
            ctx.tenant_id,
            "document.imported",
            {"document_id": document_id, "version": version, "source_id": source_id},
        )
        return {
            "document_id": document_id,
            "version": version,
            "source_id": source_id,
            "status": "INDEXED_TEXT",
            "trust": "UNTRUSTED_DATA",
        }


def retrieve(store: Store, ctx: AuthContext, query: str, cutoff: str | None = None) -> Json:
    require(
        isinstance(query, str) and 1 <= len(query) <= 200, "INVALID_QUERY", "Search text required"
    )
    cutoff = utc(cutoff or store.company(ctx)["clock"])
    terms = re.findall(r"\w+", query.casefold())
    hits = []
    with store.connect() as db:
        store.authorize(db, ctx)
        rows = db.execute(
            "SELECT d.* FROM documents d WHERE d.tenant_id=? AND d.observed_at<=? AND d.version=(SELECT MAX(v.version) FROM documents v WHERE v.tenant_id=d.tenant_id AND v.document_id=d.document_id AND v.observed_at<=?)",
            (ctx.tenant_id, cutoff, cutoff),
        )
        for row in rows:
            if ctx.role not in json.loads(row["read_roles"]):
                continue
            for number, line in enumerate(row["text_content"].splitlines(), 1):
                score = sum(term in line.casefold() for term in terms)
                if score:
                    hits.append(
                        {
                            "document_id": row["document_id"],
                            "version": row["version"],
                            "source_id": row["source_id"],
                            "title": row["title"],
                            "line": number,
                            "excerpt": line[:1200],
                            "score": score,
                            "trust": "UNTRUSTED_DATA",
                        }
                    )
    return {
        "mode": "LEXICAL_FULL_TEXT",
        "semantic_search": False,
        "cutoff": cutoff,
        "hits": sorted(hits, key=lambda h: -h["score"])[:20],
    }


def extract_pdf(content_base64: str) -> str:
    require(
        isinstance(content_base64, str) and len(content_base64) <= 700000,
        "INVALID_FILE",
        "PDF limit is 500 KB",
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "finance.parser"],
            input=content_base64,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise FinanceError("DOCUMENT_TIMEOUT", "PDF text extraction exceeded 20 seconds") from exc
    require(
        result.returncode == 0,
        "DOCUMENT_PARSE_FAILED",
        "PDF parser failed or exceeded supported limits",
    )
    return result.stdout


def report(store: Store, ctx: AuthContext) -> Json:
    snap = snapshot(store, ctx)
    with store.connect() as db:
        store.authorize(db, ctx)
        plans = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM objects WHERE tenant_id=? AND kind='plan' ORDER BY created_at DESC",
                (ctx.tenant_id,),
            )
        ]
        operations = [
            dict(r)
            for r in db.execute(
                "SELECT action_id,status,provider_ref,payload_hash FROM actions WHERE tenant_id=?",
                (ctx.tenant_id,),
            )
        ]
        allocations = [
            dict(r)
            for r in db.execute("SELECT * FROM allocations WHERE tenant_id=?", (ctx.tenant_id,))
        ]
    return {
        "generated_at": now(),
        "data": "SYNTHETIC",
        "execution": "SANDBOX",
        "snapshot": snap,
        "metrics": metrics(snap),
        "forecast": forecast(snap),
        "plans": plans,
        "operations": operations,
        "allocations": allocations,
        "audit": store.audit_log(ctx),
        "evidence_edges": [
            {"from": f["source_id"], "to": f["fact_id"], "kind": "SOURCE_FACT"}
            for f in snap["facts"]
        ]
        + [
            {"from": f["fact_id"], "to": snap["snapshot_id"], "kind": "FACT_SNAPSHOT"}
            for f in snap["facts"]
        ]
        + [{"from": p["snapshot_id"], "to": p["plan_id"], "kind": "SNAPSHOT_PLAN"} for p in plans]
        + [
            {"from": p["plan_id"], "to": a["action_id"], "kind": "PLAN_ACTION"}
            for p in plans
            for a in p["actions"]
        ],
    }


def products(store: Store, ctx: AuthContext) -> Json:
    snap = snapshot(store, ctx)
    return {
        "snapshot_id": snap["snapshot_id"],
        "products": [
            {"terms": p, "eligibility": eligibility(snap["profile"], p)}
            for p in snap.get("financing_products", catalog(snap["as_of"]))
        ],
    }
