"""Versioned synthetic CSV adapter. Bad rows persist; document text is never code."""

from __future__ import annotations

import csv
import io
import json
import sqlite3

from finance.domain import AuthContext, FinanceError, Json, canonical, minor, require, uid, utc
from finance.store import Store

COLUMNS = [
    "kind",
    "external_id",
    "version",
    "event_time",
    "observed_time",
    "amount_minor",
    "currency",
    "due_at",
    "counterparty",
    "beneficiary_version",
    "reference",
    "protected",
    "status",
]
KINDS = {"BALANCE", "INVOICE", "PAYABLE", "RECEIVABLE", "TRANSACTION"}


def parse_row(row: dict[str, str], received: str) -> Json:
    require(
        set(row) == set(COLUMNS) and None not in row.values(), "INVALID_ROW", "Missing CSV fields"
    )
    require(row["kind"] in KINDS, "INVALID_ROW", "Unsupported row kind")
    require(row["currency"] == "CNY", "UNSUPPORTED_CURRENCY", "Only CNY is supported")
    require(0 < len(row["external_id"]) <= 160, "INVALID_ROW", "External ID required")
    require(row["protected"] in ("true", "false"), "INVALID_ROW", "Protected must be true/false")
    require(
        row["status"] in ("CONFIRMED", "SETTLED", "SUBMITTED", "VOID", "CORRECTED"),
        "INVALID_ROW",
        "Unsupported financial status",
    )
    try:
        require(
            row["amount_minor"].lstrip("-").isdigit() and row["version"].isdigit(),
            "INVALID_ROW",
            "Amounts/versions must be integers",
        )
        value: Json = dict(row)
        value["amount_minor"] = minor(
            int(row["amount_minor"]),
            positive=row["kind"] in ("PAYABLE", "RECEIVABLE")
            or (row["kind"] == "INVOICE" and row["status"] != "CORRECTED"),
        )
        if row["status"] == "CORRECTED":
            require(
                row["kind"] == "INVOICE" and bool(row["reference"]),
                "INVALID_ROW",
                "Corrected invoice must reference its original",
            )
        value["version"] = int(row["version"])
        require(value["version"] > 0, "INVALID_ROW", "Version must be positive")
        value["protected"] = row["protected"] == "true"
        value["event_time"] = utc(row["event_time"])
        # Receiver controls knowledge time. A file cannot backdate its arrival.
        value["observed_time"] = max(utc(row["observed_time"]), utc(received))
        value["due_at"] = utc(row["due_at"]) if row["due_at"] else None
        if row["kind"] in ("PAYABLE", "RECEIVABLE"):
            require(value["due_at"] is not None, "INVALID_ROW", "Obligation due time required")
        return value
    except (ValueError, TypeError) as exc:
        raise FinanceError("INVALID_ROW", "Invalid row types") from exc


def import_csv(
    store: Store,
    ctx: AuthContext,
    content: bytes,
    provider: str,
    received: str,
    closing_balance_minor: int | None = None,
) -> Json:
    require(0 < len(content) <= 1_000_000, "INVALID_FILE", "CSV must be at most 1 MB")
    require(
        isinstance(provider, str) and 0 < len(provider) <= 80,
        "INVALID_ARGUMENTS",
        "Provider namespace required",
    )
    require(provider != "sandbox", "POLICY_DENIED", "Sandbox observations use a trusted receiver")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        require(
            reader.fieldnames == COLUMNS, "UNSUPPORTED_SCHEMA", "Expected synthetic-csv-v1 columns"
        )
        rows = list(reader)
    except UnicodeError as exc:
        raise FinanceError("UNSUPPORTED_SCHEMA", "Expected UTF-8 CSV") from exc
    require(len(rows) <= 5000, "INVALID_FILE", "CSV row limit exceeded")
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        source_id, fresh = store.source(db, ctx.tenant_id, provider, content, received)
        if not fresh:
            old = db.execute(
                "SELECT * FROM imports WHERE tenant_id=? AND source_id=?",
                (ctx.tenant_id, source_id),
            ).fetchone()
            return dict(old) | {"duplicate": True}
        import_id = uid("import")
        db.execute(
            "INSERT INTO imports VALUES(?,?,?,'PROCESSING',0,0)",
            (ctx.tenant_id, import_id, source_id),
        )
        accepted = rejected = 0
        for number, row in enumerate(rows, 2):
            try:
                value = parse_row(row, received)
                accepted += int(store.add_fact(db, ctx.tenant_id, provider, source_id, value))
            except FinanceError as exc:
                rejected += 1
                db.execute(
                    "INSERT INTO quarantine VALUES(?,?,?,?,?)",
                    (ctx.tenant_id, import_id, number, exc.code, canonical(row)),
                )
        status = "REVIEW_REQUIRED" if rejected else "IMPORTED"
        db.execute(
            "UPDATE imports SET status=?,accepted=?,rejected=? WHERE tenant_id=? AND import_id=?",
            (status, accepted, rejected, ctx.tenant_id, import_id),
        )
        store.audit(
            db,
            ctx,
            "source.imported",
            {
                "source_id": source_id,
                "import_id": import_id,
                "accepted": accepted,
                "rejected": rejected,
            },
        )
        if closing_balance_minor is not None:
            facts = store.facts(db, ctx.tenant_id, received, received)
            cash = sum(
                f["value"]["amount_minor"]
                for f in facts
                if f["kind"] == "BALANCE"
                or (f["kind"] == "TRANSACTION" and f["value"]["status"] == "SETTLED")
            )
            if cash != minor(closing_balance_minor):
                db.execute(
                    "UPDATE imports SET status='INCOMPLETE_STATEMENT' WHERE tenant_id=? AND import_id=?",
                    (ctx.tenant_id, import_id),
                )
                status = "INCOMPLETE_STATEMENT"
        return {
            "import_id": import_id,
            "source_id": source_id,
            "status": status,
            "accepted": accepted,
            "rejected": rejected,
            "duplicate": False,
        }


def allocate(
    store: Store,
    ctx: AuthContext,
    transaction_id: str,
    obligation_id: str,
    amount_minor: int,
    observed_at: str,
) -> str:
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        return allocate_in_transaction(
            db, ctx.tenant_id, transaction_id, obligation_id, amount_minor, observed_at
        )


def allocate_in_transaction(
    db: sqlite3.Connection,
    tenant: str,
    transaction_id: str,
    obligation_id: str,
    amount_minor: int,
    observed_at: str,
) -> str:
    amount_minor = minor(amount_minor, positive=True)
    tx = db.execute(
        "SELECT * FROM facts WHERE tenant_id=? AND fact_id=?", (tenant, transaction_id)
    ).fetchone()
    obligation = db.execute(
        "SELECT * FROM facts WHERE tenant_id=? AND fact_id=?", (tenant, obligation_id)
    ).fetchone()
    require(
        tx is not None and obligation is not None, "NOT_FOUND", "Scoped matching records required"
    )
    t, o = json.loads(tx["payload"]), json.loads(obligation["payload"])
    require(
        tx["kind"] == "TRANSACTION"
        and t["status"] == "SETTLED"
        and obligation["kind"] in ("PAYABLE", "RECEIVABLE"),
        "INVALID_ALLOCATION",
        "Settled money required",
    )
    require(t["currency"] == o["currency"], "CURRENCY_MISMATCH", "Allocation currency mismatch")
    require(
        (t["amount_minor"] > 0) == (obligation["kind"] == "RECEIVABLE"),
        "INVALID_ALLOCATION",
        "Allocation direction mismatch",
    )
    require(t["counterparty"] == o["counterparty"], "SOURCE_CONFLICT", "Counterparty mismatch")
    used = db.execute(
        "SELECT COALESCE(SUM(amount_minor),0) FROM allocations WHERE tenant_id=? AND transaction_id=?",
        (tenant, transaction_id),
    ).fetchone()[0]
    paid = db.execute(
        "SELECT COALESCE(SUM(a.amount_minor),0) FROM allocations a JOIN facts f "
        "ON a.tenant_id=f.tenant_id AND a.obligation_id=f.fact_id WHERE a.tenant_id=? "
        "AND f.kind=? AND f.provider=? AND f.external_id=?",
        (tenant, obligation["kind"], obligation["provider"], obligation["external_id"]),
    ).fetchone()[0]
    require(
        used + amount_minor <= abs(t["amount_minor"]) and paid + amount_minor <= o["amount_minor"],
        "OVER_ALLOCATION",
        "Allocation exceeds payment or outstanding obligation",
    )
    allocation_id = uid("allocation")
    db.execute(
        "INSERT INTO allocations VALUES(?,?,?,?,?,?,?)",
        (
            tenant,
            allocation_id,
            transaction_id,
            obligation_id,
            amount_minor,
            tx["effective_at"],
            utc(observed_at),
        ),
    )
    db.execute("UPDATE companies SET data_version=data_version+1 WHERE tenant_id=?", (tenant,))
    return allocation_id


def snapshot(
    store: Store, ctx: AuthContext, as_of: str | None = None, cutoff: str | None = None
) -> Json:
    with store.transaction() as db:
        store.authorize(db, ctx)
        company = db.execute(
            "SELECT * FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()
        as_of, cutoff = utc(as_of or company["clock"]), utc(cutoff or company["clock"])
        facts = store.facts(db, ctx.tenant_id, as_of, cutoff)
        allocations = [
            dict(r)
            for r in db.execute(
                "SELECT a.*,f.kind,f.provider,f.external_id FROM allocations a "
                "JOIN facts f ON a.tenant_id=f.tenant_id AND a.obligation_id=f.fact_id WHERE a.tenant_id=? "
                "AND a.effective_at<=? AND a.observed_at<=?",
                (ctx.tenant_id, as_of, cutoff),
            )
        ]
        obligations: list[Json] = []
        cash = 0
        for f in facts:
            v = f["value"]
            if f["kind"] == "BALANCE" or (f["kind"] == "TRANSACTION" and v["status"] == "SETTLED"):
                cash = minor(cash + v["amount_minor"])
            if f["kind"] in ("PAYABLE", "RECEIVABLE") and v["status"] != "VOID":
                paid = sum(
                    a["amount_minor"]
                    for a in allocations
                    if (a["kind"], a["provider"], a["external_id"])
                    == (f["kind"], f["provider"], f["external_id"])
                )
                obligations.append(
                    v
                    | {
                        "fact_id": f["fact_id"],
                        "provider": f["provider"],
                        "source_id": f["source_id"],
                        "outstanding_minor": max(0, v["amount_minor"] - paid),
                    }
                )
        quality = [
            r[0]
            for r in db.execute(
                "SELECT i.status FROM imports i JOIN sources s ON i.tenant_id=s.tenant_id AND i.source_id=s.source_id WHERE i.tenant_id=? AND i.status!='IMPORTED' AND s.observed_at<=? AND (i.status!='REVIEW_REQUIRED' OR EXISTS(SELECT 1 FROM quarantine q WHERE q.tenant_id=i.tenant_id AND q.import_id=i.import_id AND NOT EXISTS(SELECT 1 FROM review_decisions d WHERE d.tenant_id=q.tenant_id AND d.import_id=q.import_id AND d.row_number=q.row_number AND d.observed_at<=?)))",
                (ctx.tenant_id, cutoff, cutoff),
            )
        ]
        if not any(f["kind"] == "BALANCE" for f in facts):
            quality.append("MISSING_OPENING_BALANCE")
        value: Json = {
            "schema_version": 1,
            "as_of": as_of,
            "cutoff_observed_at": cutoff,
            "currency": "CNY",
            "business_timezone": "Asia/Shanghai",
            "data_mode": "synthetic",
            "data_version": observed_data_version(db, ctx.tenant_id, cutoff),
            "policy": store.policy(db, ctx.tenant_id, min(as_of, cutoff)),
            "profile": json.loads(company["profile"]),
            "confirmed_cash_minor": cash,
            "obligations": sorted(obligations, key=lambda o: (o["due_at"], o["external_id"])),
            "facts": facts,
            "quality_flags": quality,
            "calculation_version": "snapshot-v1",
            "evidence_refs": sorted({f["source_id"] for f in facts}),
        }
        catalog_row = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='product_catalog' ORDER BY created_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
        if catalog_row:
            observed_catalog = json.loads(catalog_row[0])
            if observed_catalog["observed_at"] <= cutoff:
                value["financing_products"] = observed_catalog["products"]
        value["content_hash"] = digest_snapshot(value)
        value["snapshot_id"] = "snap_" + value["content_hash"][:32]
        existing = db.execute(
            "SELECT 1 FROM objects WHERE tenant_id=? AND kind='snapshot' AND object_id=?",
            (ctx.tenant_id, value["snapshot_id"]),
        ).fetchone()
        if not existing:
            store.put_object(db, ctx.tenant_id, "snapshot", value["snapshot_id"], value)
        return value


def observed_data_version(db: sqlite3.Connection, tenant: str, cutoff: str) -> int:
    facts = db.execute(
        "SELECT COUNT(*) FROM facts WHERE tenant_id=? AND observed_at<=?", (tenant, cutoff)
    ).fetchone()[0]
    allocations = db.execute(
        "SELECT COUNT(*) FROM allocations WHERE tenant_id=? AND observed_at<=?", (tenant, cutoff)
    ).fetchone()[0]
    return int(facts) + int(allocations)

def digest_snapshot(value: Json) -> str:
    from finance.domain import digest

    return digest(value)
