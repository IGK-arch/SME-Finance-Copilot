"""Private simulator database and arithmetic. No finance.compute/store imports."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


def packed(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


class WorldError(Exception):
    pass


class World:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS worlds(tenant TEXT PRIMARY KEY, clock TEXT NOT NULL,
              initial_cash INTEGER NOT NULL, cash INTEGER NOT NULL, private_schedule TEXT NOT NULL,
              obligations TEXT NOT NULL, products TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations(tenant TEXT NOT NULL, ref TEXT NOT NULL,
              stable_key TEXT NOT NULL, request_hash TEXT NOT NULL, command TEXT NOT NULL,
              status TEXT NOT NULL, fault TEXT NOT NULL, PRIMARY KEY(tenant,ref), UNIQUE(tenant,stable_key));
            CREATE TABLE IF NOT EXISTS movements(tenant TEXT NOT NULL, ref TEXT NOT NULL,
              at TEXT NOT NULL, delta INTEGER NOT NULL, reference TEXT NOT NULL, counterparty TEXT NOT NULL,
              PRIMARY KEY(tenant,ref));
            CREATE TABLE IF NOT EXISTS debts(tenant TEXT NOT NULL, ref TEXT NOT NULL,
              principal INTEGER NOT NULL, repayment INTEGER NOT NULL, due_at TEXT NOT NULL,
              paid INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(tenant,ref));
            CREATE TABLE IF NOT EXISTS decisions(tenant TEXT NOT NULL, request_id TEXT NOT NULL,
              payload TEXT NOT NULL, PRIMARY KEY(tenant,request_id));
            """)

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def seed(self, value: dict[str, Any]) -> None:
        with self.db() as db:
            db.execute(
                "INSERT INTO worlds VALUES(?,?,?,?,?,?,?)",
                (
                    value["tenant"],
                    value["clock"],
                    value["cash_minor"],
                    value["cash_minor"],
                    packed(value["private_schedule"]),
                    packed(value["obligations"]),
                    packed(value["products"]),
                ),
            )

    def observation(self, tenant: str) -> dict[str, Any]:
        with self.db() as db:
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            if world is None:
                raise WorldError("Unknown scoped world")
            pending = db.execute(
                "SELECT command FROM operations WHERE tenant=? AND status='SUBMITTED'", (tenant,)
            ).fetchall()
            holds = sum(max(0, -json.loads(row[0])["cash_delta_minor"]) for row in pending)
            return {
                "schema_version": 1,
                "clock": world["clock"],
                "cash_minor": world["cash"],
                "available_minor": world["cash"] - holds,
                "holds_minor": holds,
                "movements": [
                    dict(r)
                    for r in db.execute(
                        "SELECT m.*,o.stable_key FROM movements m LEFT JOIN operations o ON m.tenant=o.tenant AND m.ref=o.ref WHERE m.tenant=? ORDER BY m.at,m.ref",
                        (tenant,),
                    )
                ],
                "pending_operations": [
                    dict(r)
                    for r in db.execute(
                        "SELECT ref,stable_key,status FROM operations WHERE tenant=? AND status='SUBMITTED'",
                        (tenant,),
                    )
                ],
                "decisions": [
                    json.loads(r[0])
                    for r in db.execute("SELECT payload FROM decisions WHERE tenant=?", (tenant,))
                ],
                "capabilities": {
                    "supports_idempotency": True,
                    "idempotency_retention": "entire_world_lifetime",
                    "supports_status_lookup": True,
                    "supports_cancel": False,
                    "supports_external_hold": True,
                    "balance_semantics": "available excludes holds",
                    "time_semantics": "UTC event ordering",
                    "settlement_finality_semantics": "final synthetic settlement",
                    "webhook_verification": "polling_only",
                    "rate_limits": "local test service, no external bank",
                },
            }

    def status(self, tenant: str, stable_key: str) -> dict[str, Any]:
        with self.db() as db:
            row = db.execute(
                "SELECT ref,status FROM operations WHERE tenant=? AND stable_key=?",
                (tenant, stable_key),
            ).fetchone()
            return dict(row) if row else {"status": "NOT_FOUND", "ref": None}

    def extension_decision(
        self, tenant: str, request_id: str, obligation_id: str, due_at: str, accepted: bool
    ) -> dict[str, Any]:
        from datetime import datetime

        if type(accepted) is not bool or datetime.fromisoformat(due_at).tzinfo is None:
            raise WorldError("Invalid decision")
        with self.db() as db:
            existing = db.execute(
                "SELECT payload FROM decisions WHERE tenant=? AND request_id=?",
                (tenant, request_id),
            ).fetchone()
            if existing:
                return json.loads(existing[0])
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            obligations = json.loads(world["obligations"])
            if obligation_id not in obligations or due_at <= obligations[obligation_id]["due_at"]:
                raise WorldError("Invalid extension target/date")
            event = {
                "event_id": "extension_" + request_id,
                "request_id": request_id,
                "obligation_id": obligation_id,
                "due_at": due_at,
                "accepted": accepted,
                "observed_at": world["clock"],
                "kind": "SYNTHETIC_COUNTERPARTY_DECISION",
            }
            if accepted:
                obligations[obligation_id]["due_at"] = due_at
                db.execute(
                    "UPDATE worlds SET obligations=? WHERE tenant=?", (packed(obligations), tenant)
                )
            db.execute("INSERT INTO decisions VALUES(?,?,?)", (tenant, request_id, packed(event)))
            return event

    def submit(self, tenant: str, command: dict[str, Any], fault: str = "none") -> dict[str, Any]:
        fingerprint = hashlib.sha256(packed(command).encode()).hexdigest()
        with self.db() as db:
            old = db.execute(
                "SELECT * FROM operations WHERE tenant=? AND stable_key=?",
                (tenant, command["idempotency_key"]),
            ).fetchone()
            if old:
                if old["request_hash"] != fingerprint:
                    raise WorldError("IDEMPOTENCY_CONFLICT")
                return {"status": old["status"], "ref": old["ref"]}
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            if (
                command["currency"] != "CNY"
                or type(command["amount_minor"]) is not int
                or command["amount_minor"] <= 0
            ):
                raise WorldError("Invalid money")
            if command["at"] > world["clock"]:
                raise WorldError("Action is not due")
            if command["kind"] == "DRAW_LOAN":
                quote = command["quote"]
                terms = next(
                    (
                        p
                        for p in json.loads(world["products"])
                        if p["product_id"] == quote["product_version"]
                    ),
                    None,
                )
                if terms is None or terms != quote["terms"] or world["clock"] > terms["expires_at"]:
                    raise WorldError("Unregistered or expired terms")
                principal = command["amount_minor"]
                if not terms["min_minor"] <= principal <= terms["max_minor"]:
                    raise WorldError("Amount outside product range")
                expected_net = principal - terms["upfront_fee_minor"]
                if (
                    command["cash_delta_minor"] != expected_net
                    or quote["net_minor"] != expected_net
                ):
                    raise WorldError("Wrong net proceeds")
            elif command["kind"] in ("PAY_OBLIGATION", "REPAY_LOAN"):
                if command["cash_delta_minor"] != -command["amount_minor"]:
                    raise WorldError("Wrong payment delta")
                if command["kind"] == "PAY_OBLIGATION":
                    obligations = json.loads(world["obligations"])
                    target = obligations.get(command["obligation_id"])
                    if target is None or target["outstanding_minor"] < command["amount_minor"]:
                        raise WorldError("No payable amount remains")
                else:
                    debt = db.execute(
                        "SELECT * FROM debts WHERE tenant=? AND ref=?",
                        (tenant, command["obligation_id"]),
                    ).fetchone()
                    if debt is None or debt["paid"] or debt["repayment"] != command["amount_minor"]:
                        raise WorldError("Debt mismatch")
            else:
                raise WorldError("Unsupported command")
            holds = sum(
                max(0, -json.loads(r[0])["cash_delta_minor"])
                for r in db.execute(
                    "SELECT command FROM operations WHERE tenant=? AND status='SUBMITTED'",
                    (tenant,),
                )
            )
            if world["cash"] - holds + min(0, command["cash_delta_minor"]) < 0:
                raise WorldError("Insufficient external funds")
            ref = "sim_" + uuid4().hex
            status = "FAILED" if fault == "reject" else "SUBMITTED"
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                (
                    tenant,
                    ref,
                    command["idempotency_key"],
                    fingerprint,
                    packed(command),
                    status,
                    fault,
                ),
            )
            result = {"status": status, "ref": ref}
        if fault == "lost_response":
            raise TimeoutError("Synthetic lost response after durable acceptance")
        return result

    def advance(self, tenant: str, clock: str) -> dict[str, Any]:
        with self.db() as db:
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            if clock < world["clock"]:
                raise WorldError("Clock cannot move backward")
            events = []
            for event in json.loads(world["private_schedule"]):
                if (
                    event["at"] <= clock
                    and not db.execute(
                        "SELECT 1 FROM movements WHERE tenant=? AND ref=?", (tenant, event["ref"])
                    ).fetchone()
                ):
                    events.append((event["at"], "receipt", event))
            for op in db.execute(
                "SELECT * FROM operations WHERE tenant=? AND status='SUBMITTED'", (tenant,)
            ).fetchall():
                command = json.loads(op["command"])
                if command["at"] <= clock and op["fault"] != "pending":
                    events.append((max(world["clock"], command["at"]), "operation", dict(op)))
            cash = world["cash"]
            obligations = json.loads(world["obligations"])
            for at, kind, event in sorted(events, key=lambda e: (e[0], e[1])):
                if kind == "receipt":
                    delta, reference, counterparty, ref = (
                        event["delta"],
                        event["reference"],
                        event["counterparty"],
                        event["ref"],
                    )
                else:
                    command = json.loads(event["command"])
                    delta, reference, counterparty, ref = (
                        command["cash_delta_minor"],
                        command["obligation_id"] or "loan",
                        command.get("counterparty", "lender"),
                        event["ref"],
                    )
                    if cash + delta < 0:
                        db.execute(
                            "UPDATE operations SET status='FAILED' WHERE tenant=? AND ref=?",
                            (tenant, ref),
                        )
                        continue
                    if command["kind"] == "PAY_OBLIGATION":
                        obligations[reference]["outstanding_minor"] -= command["amount_minor"]
                    elif command["kind"] == "DRAW_LOAN":
                        q = command["quote"]
                        # Separate arithmetic, including fractional ACT/365 days.
                        from datetime import datetime

                        days = (
                            datetime.fromisoformat(q["repay_at"])
                            - datetime.fromisoformat(q["disburse_at"])
                        ).days
                        interest = int(
                            (
                                Decimal(command["amount_minor"])
                                * Decimal(q["terms"]["rate"])
                                * Decimal(days)
                                / Decimal(365)
                            ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
                        )
                        repayment = (
                            command["amount_minor"] + interest + q["terms"]["repayment_fee_minor"]
                        )
                        db.execute(
                            "INSERT INTO debts VALUES(?,?,?,?,?,0)",
                            (
                                tenant,
                                command["action_id"] + "_debt",
                                command["amount_minor"],
                                repayment,
                                q["repay_at"],
                            ),
                        )
                    elif command["kind"] == "REPAY_LOAN":
                        db.execute(
                            "UPDATE debts SET paid=1 WHERE tenant=? AND ref=?", (tenant, reference)
                        )
                    db.execute(
                        "UPDATE operations SET status='SETTLED' WHERE tenant=? AND ref=?",
                        (tenant, ref),
                    )
                db.execute(
                    "INSERT INTO movements VALUES(?,?,?,?,?,?)",
                    (tenant, ref, at, delta, reference, counterparty),
                )
                cash += delta
            db.execute(
                "UPDATE worlds SET clock=?,cash=?,obligations=? WHERE tenant=?",
                (clock, cash, packed(obligations), tenant),
            )
        return self.observation(tenant)

    def external_movement(self, tenant: str, delta: int, reference: str) -> None:
        with self.db() as db:
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            if type(delta) is not int or world["cash"] + delta < 0:
                raise WorldError("Invalid external movement")
            db.execute(
                "INSERT INTO movements VALUES(?,?,?,?,?,?)",
                (tenant, "external_" + uuid4().hex, world["clock"], delta, reference, "external"),
            )
            db.execute("UPDATE worlds SET cash=cash+? WHERE tenant=?", (delta, tenant))

    def evaluate(self, tenant: str, reserve: int) -> dict[str, Any]:
        with self.db() as db:
            world = db.execute("SELECT * FROM worlds WHERE tenant=?", (tenant,)).fetchone()
            movements = list(
                db.execute("SELECT * FROM movements WHERE tenant=? ORDER BY at,rowid", (tenant,))
            )
            balance = minimum = world["initial_cash"]
            for movement in movements:
                balance += movement["delta"]
                minimum = min(minimum, balance)
            obligations = json.loads(world["obligations"])
            remaining = sum(v["outstanding_minor"] for v in obligations.values())
            debt = db.execute(
                "SELECT COALESCE(SUM(repayment),0) FROM debts WHERE tenant=? AND paid=0", (tenant,)
            ).fetchone()[0]
            missed = []
            for reference, obligation in obligations.items():
                paid = [m for m in movements if m["reference"] == reference and m["delta"] < 0]
                original = obligation["outstanding_minor"] - sum(m["delta"] for m in paid)
                on_time = -sum(m["delta"] for m in paid if m["at"] <= obligation["due_at"])
                if world["clock"] >= obligation["due_at"] and on_time < original:
                    missed.append(reference)
            for loan in db.execute("SELECT * FROM debts WHERE tenant=?", (tenant,)):
                on_time = -sum(
                    m["delta"]
                    for m in movements
                    if m["reference"] == loan["ref"]
                    and m["delta"] < 0
                    and m["at"] <= loan["due_at"]
                )
                if world["clock"] >= loan["due_at"] and on_time < loan["repayment"]:
                    missed.append(loan["ref"])
            return {
                "evaluator_version": "world-ledger-oracle-v2",
                "data_mode": "synthetic",
                "final_cash_minor": world["cash"],
                "arithmetic_cash_minor": balance,
                "minimum_cash_minor": minimum,
                "remaining_payables_minor": remaining,
                "remaining_debt_minor": debt,
                "movement_count": len(movements),
                "missed_deadlines": sorted(missed),
                "success": balance == world["cash"]
                and minimum >= reserve
                and remaining == 0
                and debt == 0
                and not missed,
            }
