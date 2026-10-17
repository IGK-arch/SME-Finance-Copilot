"""Server authorization, exact approval, atomic reserves, outbox and reconciliation."""

from __future__ import annotations

import json
import sqlite3
import time

from finance.adapter import SandboxAdapter
from finance.compute import shift
from finance.contracts import execution_contract
from finance.domain import (
    AuthContext,
    FinanceError,
    Json,
    available,
    canonical,
    digest,
    minor,
    require,
    uid,
    utc,
)
from finance.ingestion import allocate_in_transaction, observed_data_version, snapshot
from finance.store import Store
from finance.validation import validate_plan


APPROVAL_REAL_TTL_SECONDS = 24 * 3600

OBSERVE_ROLES = {"OWNER", "ACCOUNTANT", "ADMIN"}


class ExecutionService:
    def __init__(self, store: Store, adapter: SandboxAdapter) -> None:
        self.store, self.adapter = store, adapter

    def make_plan(
        self,
        ctx: AuthContext,
        objective: str = "MIN_COST",
        scenario_set: list[Json] | None = None,
        reserve_target_minor: int | None = None,
    ) -> Json:
        with self.store.connect() as db:
            self.store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        snap = snapshot(self.store, ctx)
        from finance.planner import solve

        result = solve(
            snap, objective, scenario_set=scenario_set, reserve_target_minor=reserve_target_minor
        )
        if result["plan"]:
            plan = result["plan"]
            with self.store.transaction() as db:
                if not db.execute(
                    "SELECT 1 FROM objects WHERE tenant_id=? AND kind='plan' AND object_id=?",
                    (ctx.tenant_id, plan["plan_id"]),
                ).fetchone():
                    self.store.put_object(db, ctx.tenant_id, "plan", plan["plan_id"], plan)
                    self.store.audit(
                        db,
                        ctx,
                        "plan.validated",
                        {"plan_id": plan["plan_id"], "snapshot_id": snap["snapshot_id"]},
                    )
        return result

    def action(self, ctx: AuthContext, action_id: str) -> Json:
        with self.store.connect() as db:
            self.store.authorize(db, ctx)
            row = db.execute(
                "SELECT * FROM actions WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            ).fetchone()
            require(row is not None, "NOT_FOUND", "Scoped action not found")
            value = dict(row)
            value["payload"] = json.loads(value["payload"])
            value["attempts"] = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM attempts WHERE tenant_id=? AND action_id=?",
                    (ctx.tenant_id, action_id),
                )
            ]
            return value

    def command(self, ctx: AuthContext, plan_id: str, action_id: str) -> Json:
        plan = self.store.get_object(ctx, "plan", plan_id)
        target = next((a for a in plan["actions"] if a["action_id"] == action_id), None)
        if target is None:
            raise FinanceError("NOT_FOUND", "Action does not belong to this scoped plan")
        snap = snapshot(self.store, ctx)
        with self.store.connect() as db:
            self.store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
            existing = db.execute(
                "SELECT payload FROM actions WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            ).fetchone()
            if existing:
                return json.loads(existing[0])
            require(
                not db.execute(
                    "SELECT 1 FROM objects WHERE tenant_id=? AND kind='cancelled_plan' AND object_id=?",
                    (ctx.tenant_id, plan_id),
                ).fetchone(),
                "PLAN_CANCELLED",
                "Plan cancelled",
            )
            require(
                target["at"] <= snap["as_of"],
                "PRECONDITION_FAILED",
                "Action is not due in the sandbox clock",
            )
            for dependency in target["dependencies"]:
                dependency_row = db.execute(
                    "SELECT status FROM actions WHERE tenant_id=? AND action_id=?",
                    (ctx.tenant_id, dependency),
                ).fetchone()
                require(
                    dependency_row is not None and dependency_row[0] == "SETTLED",
                    "PRECONDITION_FAILED",
                    "Dependency is not settled and reconciled",
                )
            settled_ids = {
                r[0]
                for r in db.execute(
                    "SELECT action_id FROM actions WHERE tenant_id=? AND status='SETTLED'",
                    (ctx.tenant_id,),
                )
            }
        remaining = json.loads(canonical(plan))
        remaining["actions"] = [
            a for a in remaining["actions"] if a["action_id"] not in settled_ids
        ]
        for action in remaining["actions"]:
            action["dependencies"] = [
                dep for dep in action["dependencies"] if dep not in settled_ids
            ]
            if action["kind"] == "REPAY_LOAN" and any(
                o["external_id"] == action["obligation_id"] and o["provider"] == "sandbox"
                for o in snap["obligations"]
            ):
                action["obligation_provider"] = "sandbox"
        if not any(a["kind"] == "DRAW_LOAN" for a in remaining["actions"]):
            remaining["quote"] = None
        scenario_set = plan.get("scenario_set") or [
            {"scenario_id": path["scenario_id"], "delay_days": path["delay_days"]}
            for path in plan["paths"]
        ]
        current_validation = validate_plan(snap, remaining, scenario_set)
        require(
            current_validation["valid"],
            "STALE_PLAN",
            "Remaining plan no longer passes current independent checks; replan and approve again",
        )
        # Current snapshot is explicitly bound per action, after prior actions settle.
        approval_id = "approval_" + digest([action_id, snap["snapshot_id"]])[:32]
        value: Json = {
            "schema_version": 1,
            "action_id": action_id,
            "plan_id": plan_id,
            "plan_version": plan["plan_version"],
            "snapshot_id": snap["snapshot_id"],
            "kind": target["kind"],
            "obligation_id": target["obligation_id"],
            "account_id": "operating",
            "beneficiary_version_id": target["beneficiary_version_id"],
            "amount_minor": target["amount_minor"],
            "currency": "CNY",
            "required_approval_id": approval_id,
            "policy_version": snap["policy"]["version"],
            "idempotency_key": ctx.tenant_id + "_" + action_id,
            "precondition_refs": [
                "current_membership",
                "exact_approval",
                "settled_funds",
                "verified_beneficiary",
            ],
            "at": target["at"],
            "cash_delta_minor": target["cash_delta_minor"],
            "dependencies": target["dependencies"],
            "completion_predicate": target["completion_predicate"],
        }
        if "quote" in target:
            value["quote"] = target["quote"]
        if target["kind"] == "PAY_OBLIGATION":
            value["obligation_provider"] = target["obligation_provider"]
            o = next(
                (
                    o
                    for o in snap["obligations"]
                    if o["external_id"] == target["obligation_id"]
                    and o["provider"] == target["obligation_provider"]
                ),
                None,
            )
            if o is None:
                raise FinanceError("STALE_PLAN", "Confirmed obligation no longer exists")
            require(
                o["outstanding_minor"] == value["amount_minor"]
                and o["beneficiary_version"] == value["beneficiary_version_id"]
                and o["due_at"] == target["at"],
                "STALE_PLAN",
                "Confirmed obligation changed; replan remaining actions",
            )
            value["counterparty"] = o["counterparty"]
        else:
            value["counterparty"] = "lender"
        require(
            not snap["quality_flags"],
            "INSUFFICIENT_DATA",
            "Resolve import quality issues before execution",
        )
        return value

    def approve(self, ctx: AuthContext, command: Json, expires_at: str | None = None) -> Json:
        execution_contract(command)
        expected = self.command(ctx, command["plan_id"], command["action_id"])
        require(
            command == expected, "INVALID_COMMAND", "Command differs from current compiled action"
        )
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, {"OWNER"})
            self._current_checks(db, ctx, command)
            company = db.execute(
                "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
            ).fetchone()
            expiry = utc(expires_at) if expires_at else shift(company[0], 1)
            require(
                company[0] < expiry <= shift(company[0], 2),
                "INVALID_APPROVAL",
                "Approval expiry must be within two days",
            )
            approval_id = command["required_approval_id"]
            old = db.execute(
                "SELECT * FROM approvals WHERE tenant_id=? AND approval_id=?",
                (ctx.tenant_id, approval_id),
            ).fetchone()
            if old:
                require(
                    old["payload_hash"] == digest(command)
                    and not old["revoked"]
                    and old["expires_at"] > company[0],
                    "APPROVAL_INVALID",
                    "Previous approval cannot be reused",
                )
                if not self._ttl_ok(db, ctx, approval_id):
                    self._grant_ttl(db, ctx, approval_id)
                    self.store.audit(db, ctx, "approval.renewed", {"approval_id": approval_id})
                return {
                    "approval_id": approval_id,
                    "payload_hash": old["payload_hash"],
                    "expires_at": old["expires_at"],
                }
            db.execute(
                "INSERT INTO approvals VALUES(?,?,?,?,?,?,0)",
                (
                    ctx.tenant_id,
                    approval_id,
                    ctx.user_id,
                    digest(command),
                    canonical(command),
                    expiry,
                ),
            )
            # Security TTL in real time, independent of the synthetic business clock (V03-20).
            self._grant_ttl(db, ctx, approval_id)
            self.store.audit(
                db,
                ctx,
                "approval.created",
                {
                    "approval_id": approval_id,
                    "action_id": command["action_id"],
                    "payload_hash": digest(command),
                },
            )
            return {
                "approval_id": approval_id,
                "payload_hash": digest(command),
                "expires_at": expiry,
            }

    def _current_checks(self, db: sqlite3.Connection, ctx: AuthContext, command: Json) -> None:
        minor(command["amount_minor"], positive=True)
        require(
            command["currency"] == "CNY" and command["schema_version"] == 1,
            "INVALID_COMMAND",
            "Unsupported command contract",
        )
        company = db.execute(
            "SELECT * FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()
        require(not company["stopped"], "KILL_SWITCH", "New sends are stopped")
        require(command["at"] <= company["clock"], "PRECONDITION_FAILED", "Action not yet due")
        policy = self.store.policy(db, ctx.tenant_id)
        require(
            policy["version"] == command["policy_version"],
            "POLICY_CHANGED",
            "Policy version changed",
        )
        stored = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='snapshot' AND object_id=?",
            (ctx.tenant_id, command["snapshot_id"]),
        ).fetchone()
        require(stored is not None, "STALE_SNAPSHOT", "Scoped snapshot missing")
        snap = json.loads(stored[0])

        require(
            snap["as_of"] == company["clock"]
            and snap["data_version"] == observed_data_version(db, ctx.tenant_id, company["clock"]),
            "STALE_SNAPSHOT",
            "Material state changed; compile and approve a fresh command",
        )
        beneficiary = db.execute(
            "SELECT * FROM beneficiaries WHERE tenant_id=? AND version_id=?",
            (ctx.tenant_id, command["beneficiary_version_id"]),
        ).fetchone()
        require(
            beneficiary is not None and beneficiary["verified"],
            "BENEFICIARY_UNVERIFIED",
            "Verified beneficiary required",
        )
        latest = db.execute(
            "SELECT version_id FROM beneficiaries WHERE tenant_id=? AND logical_id=? ORDER BY rowid DESC LIMIT 1",
            (ctx.tenant_id, beneficiary["logical_id"]),
        ).fetchone()
        require(
            latest[0] == beneficiary["version_id"],
            "BENEFICIARY_CHANGED",
            "Beneficiary version changed; approval invalid",
        )
        require(
            not db.execute(
                "SELECT 1 FROM objects WHERE tenant_id=? AND kind='cancelled_plan' AND object_id=?",
                (ctx.tenant_id, command["plan_id"]),
            ).fetchone(),
            "PLAN_CANCELLED",
            "Plan cancelled",
        )
        for dependency in command["dependencies"]:
            row = db.execute(
                "SELECT status FROM actions WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, dependency),
            ).fetchone()
            require(
                row is not None and row[0] == "SETTLED",
                "PRECONDITION_FAILED",
                "Dependency not settled",
            )
        if command["kind"] == "DRAW_LOAN":
            require(
                company["clock"] < command["quote"]["expires_at"],
                "QUOTE_EXPIRED",
                "Fresh quote/approval required",
            )
        elif command["kind"] == "PAY_OBLIGATION":
            o = next(
                (
                    o
                    for o in snap["obligations"]
                    if o["external_id"] == command["obligation_id"]
                    and o["provider"] == command["obligation_provider"]
                ),
                None,
            )
            require(
                o is not None
                and o["outstanding_minor"] == command["amount_minor"]
                and o["beneficiary_version"] == command["beneficiary_version_id"],
                "STALE_PLAN",
                "Obligation changed",
            )
        elif command["kind"] == "REPAY_LOAN":
            o = next(
                (
                    o
                    for o in snap["obligations"]
                    if o["external_id"] == command["obligation_id"] and o["provider"] == "sandbox"
                ),
                None,
            )
            require(
                o is not None and o["outstanding_minor"] == command["amount_minor"],
                "STALE_PLAN",
                "Debt changed",
            )
        else:
            raise FinanceError("INVALID_COMMAND", "Unsupported action kind")

    def _grant_ttl(self, db: sqlite3.Connection, ctx: AuthContext, approval_id: str) -> None:
        stamp = time.time()
        self.store.put_object(
            db,
            ctx.tenant_id,
            "approval_ttl",
            f"{approval_id}@{stamp:.6f}",
            {"approval_id": approval_id, "real_expires_at": stamp + APPROVAL_REAL_TTL_SECONDS},
        )

    def _ttl_ok(self, db: sqlite3.Connection, ctx: AuthContext, approval_id: str) -> bool:
        rows = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM objects WHERE tenant_id=? AND kind='approval_ttl' AND object_id LIKE ?",
                (ctx.tenant_id, approval_id + "@%"),
            )
        ]
        mine = [r for r in rows if r["approval_id"] == approval_id]
        # Approvals created before v0.3 have no record; they keep the business-clock expiry only.
        return not mine or max(r["real_expires_at"] for r in mine) > time.time()

    def _approval_checks(self, db: sqlite3.Connection, ctx: AuthContext, command: Json) -> None:
        row = db.execute(
            "SELECT a.*,m.role,m.active FROM approvals a JOIN memberships m ON "
            "a.tenant_id=m.tenant_id AND a.actor=m.user_id WHERE a.tenant_id=? AND a.approval_id=?",
            (ctx.tenant_id, command["required_approval_id"]),
        ).fetchone()
        clock = db.execute(
            "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
        ).fetchone()[0]
        require(
            row is not None
            and row["active"]
            and row["role"] == "OWNER"
            and not row["revoked"]
            and row["expires_at"] > clock,
            "APPROVAL_INVALID",
            "Current unexpired owner approval required",
        )
        require(
            row["payload_hash"] == digest(command),
            "APPROVAL_HASH_MISMATCH",
            "Exact approved payload required",
        )
        require(
            self._ttl_ok(db, ctx, command["required_approval_id"]),
            "APPROVAL_INVALID",
            "Approval expired in real time; review and approve again",
        )

    def prepare(self, ctx: AuthContext, command: Json, job_fault: str | None = None) -> Json:
        require(
            job_fault in {None, "none", "lost_response"}, "INVALID_ARGUMENTS", "Invalid queue fault"
        )
        execution_contract(command)
        # Refresh outside the reserve transaction; provider itself separately enforces funds/holds.
        observation = self.adapter.observation()
        self.refresh(ctx, observation)
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, {"OWNER"})
            old = db.execute(
                "SELECT * FROM actions WHERE tenant_id=? AND idempotency_key=?",
                (ctx.tenant_id, command["idempotency_key"]),
            ).fetchone()
            if old:
                require(
                    old["payload_hash"] == digest(command),
                    "IDEMPOTENCY_CONFLICT",
                    "Same key has a different payload",
                )
                return {"action_id": old["action_id"], "status": old["status"], "duplicate": True}
            self._current_checks(db, ctx, command)
            self._approval_checks(db, ctx, command)
            if command["kind"] in {"PAY_OBLIGATION", "REPAY_LOAN"}:
                queued = [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT payload FROM actions WHERE tenant_id=? AND status IN ('RESERVED','SUBMITTED','UNKNOWN')",
                        (ctx.tenant_id,),
                    )
                ]
                require(
                    not any(
                        p["obligation_id"] == command["obligation_id"]
                        and p.get("obligation_provider", "sandbox")
                        == command.get("obligation_provider", "sandbox")
                        for p in queued
                    ),
                    "OBLIGATION_RESERVED",
                    "Outstanding obligation is already reserved by another logical action",
                )
            reservations = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM reservations WHERE tenant_id=? AND account_id=?",
                    (ctx.tenant_id, command["account_id"]),
                )
            ]
            cash_required = max(0, -command["cash_delta_minor"])
            free = available(observation["available_minor"], reservations)
            require(
                free - cash_required >= self.store.policy(db, ctx.tenant_id)["reserve_minor"],
                "INSUFFICIENT_FUNDS",
                "Current settled available cash cannot preserve hard reserve",
            )
            db.execute(
                "INSERT INTO actions(tenant_id,action_id,idempotency_key,payload_hash,payload,status,approval_id) "
                "VALUES(?,?,?,?,?,'RESERVED',?)",
                (
                    ctx.tenant_id,
                    command["action_id"],
                    command["idempotency_key"],
                    digest(command),
                    canonical(command),
                    command["required_approval_id"],
                ),
            )
            db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?, 'ACTIVE',0)",
                (ctx.tenant_id, command["action_id"], command["account_id"], cash_required),
            )
            db.execute("INSERT INTO outbox VALUES(?,?,0,0)", (ctx.tenant_id, command["action_id"]))
            if job_fault is not None:
                db.execute(
                    "INSERT INTO execution_jobs(tenant_id,action_id,actor,fault) VALUES(?,?,?,?)",
                    (ctx.tenant_id, command["action_id"], ctx.user_id, job_fault),
                )
            self.store.audit(
                db,
                ctx,
                "action.reserved",
                {"action_id": command["action_id"], "amount_minor": cash_required},
            )
        return {"action_id": command["action_id"], "status": "RESERVED", "duplicate": False}

    def deliver(
        self, ctx: AuthContext, action_id: str, fault: str = "none", crash_after_send: bool = False
    ) -> Json:
        action = self.action(ctx, action_id)
        command = action["payload"]
        if action["status"] in ("SETTLED", "FAILED"):
            return action
        with self.store.connect() as db:
            self.store.authorize(db, ctx, OBSERVE_ROLES)

        external = self.adapter.status(command["idempotency_key"])
        if external["status"] != "NOT_FOUND":
            self._record_result(ctx, action_id, external)
            self.refresh(ctx)
            return self.action(ctx, action_id)
        observation = self.adapter.observation()
        self.refresh(ctx, observation)
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, {"OWNER"})
            self._current_checks(db, ctx, command)
            self._approval_checks(db, ctx, command)
            reservations = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM reservations WHERE tenant_id=?", (ctx.tenant_id,)
                )
            ]
            require(
                available(observation["available_minor"], reservations)
                >= self.store.policy(db, ctx.tenant_id)["reserve_minor"],
                "INSUFFICIENT_FUNDS",
                "Available cash changed before send",
            )
            attempt_id = uid("attempt")
            clock = db.execute(
                "SELECT clock FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,'SEND_INTENT',?)",
                (ctx.tenant_id, attempt_id, action_id, clock, digest(command)),
            )
            db.execute(
                "UPDATE actions SET status='SUBMITTED',state_version=state_version+1 WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            )
            db.execute(
                "UPDATE outbox SET attempts=attempts+1 WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            )
        try:
            result = self.adapter.submit(command, fault)
        except FinanceError as exc:
            result = {"status": "UNKNOWN" if exc.retryable else "FAILED", "ref": None}
            self._record_result(ctx, action_id, result)
            if not exc.retryable:
                raise
            return self.action(ctx, action_id)
        if crash_after_send:
            raise FinanceError("INJECTED_WORKER_CRASH", "Test crash after external acceptance")
        self._record_result(ctx, action_id, result)
        return self.action(ctx, action_id)

    def _record_result(self, ctx: AuthContext, action_id: str, result: Json) -> None:
        status = result["status"]
        require(
            status in {"SUBMITTED", "UNKNOWN", "SETTLED", "FAILED"},
            "UNSUPPORTED_STATUS",
            "Unknown sandbox status",
        )
        # SETTLED becomes local SETTLED only when its movement is reconciled.
        local = "SUBMITTED" if status == "SETTLED" else status
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, OBSERVE_ROLES)
            row = db.execute(
                "SELECT status FROM actions WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            ).fetchone()
            if row[0] == "SETTLED":
                return
            db.execute(
                "UPDATE actions SET status=?,provider_ref=COALESCE(?,provider_ref),state_version=state_version+1 WHERE tenant_id=? AND action_id=?",
                (local, result.get("ref"), ctx.tenant_id, action_id),
            )
            db.execute(
                "UPDATE outbox SET delivered=? WHERE tenant_id=? AND action_id=?",
                (int(status != "UNKNOWN"), ctx.tenant_id, action_id),
            )
            db.execute(
                "UPDATE attempts SET status=? WHERE tenant_id=? AND action_id=? AND attempt_id=(SELECT attempt_id FROM attempts WHERE tenant_id=? AND action_id=? ORDER BY rowid DESC LIMIT 1)",
                (local, ctx.tenant_id, action_id, ctx.tenant_id, action_id),
            )
            # Hold flag is set only after a fresh provider observation in refresh.
            if status == "FAILED":
                db.execute(
                    "UPDATE reservations SET status='RELEASED' WHERE tenant_id=? AND action_id=?",
                    (ctx.tenant_id, action_id),
                )
            self.store.audit(
                db,
                ctx,
                "action." + local.lower(),
                {"action_id": action_id, "provider_ref": result.get("ref")},
            )

    def refresh(self, ctx: AuthContext, observation: Json | None = None) -> Json:
        with self.store.connect() as db:
            self.store.authorize(db, ctx, OBSERVE_ROLES)
        observation = observation or self.adapter.observation()
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, OBSERVE_ROLES)
            clock = utc(observation["clock"])
            db.execute(
                "UPDATE companies SET clock=? WHERE tenant_id=? AND clock<=?",
                (clock, ctx.tenant_id, clock),
            )
            from finance.contingency import observe_decisions

            observe_decisions(
                self.store, db, ctx.tenant_id, observation.get("decisions", []), clock
            )
            for movement in observation["movements"]:
                already = db.execute(
                    "SELECT 1 FROM inbox WHERE tenant_id=? AND provider='sandbox' AND event_id=?",
                    (ctx.tenant_id, movement["ref"]),
                ).fetchone()
                if already:
                    continue
                source_id, _ = self.store.source(
                    db, ctx.tenant_id, "sandbox", canonical(movement).encode(), clock
                )
                value: Json = {
                    "kind": "TRANSACTION",
                    "external_id": movement["ref"],
                    "version": 1,
                    "event_time": utc(movement["at"]),
                    "observed_time": clock,
                    "amount_minor": minor(movement["delta"]),
                    "currency": "CNY",
                    "status": "SETTLED",
                    "reference": movement["reference"],
                    "counterparty": movement["counterparty"],
                    "due_at": None,
                    "beneficiary_version": "",
                    "protected": False,
                }
                self.store.add_fact(db, ctx.tenant_id, "sandbox", source_id, value)
                tx_id = db.execute(
                    "SELECT fact_id FROM facts WHERE tenant_id=? AND kind='TRANSACTION' AND provider='sandbox' AND external_id=?",
                    (ctx.tenant_id, movement["ref"]),
                ).fetchone()[0]
                action = db.execute(
                    "SELECT * FROM actions WHERE tenant_id=? AND (provider_ref=? OR idempotency_key=?)",
                    (ctx.tenant_id, movement["ref"], movement.get("stable_key", "")),
                ).fetchone()
                command = json.loads(action["payload"]) if action else None
                if command and command["kind"] == "DRAW_LOAN":
                    quote = command["quote"]
                    debt = value | {
                        "kind": "PAYABLE",
                        "external_id": command["action_id"] + "_debt",
                        "amount_minor": quote["repayment_minor"],
                        "due_at": quote["repay_at"],
                        "counterparty": "lender",
                        "status": "CONFIRMED",
                        "beneficiary_version": "lender_v1",
                        "protected": True,
                    }
                    debt["loan_quote"] = quote
                    self.store.add_fact(db, ctx.tenant_id, "sandbox", source_id, debt)
                else:
                    target_provider = (
                        command.get("obligation_provider", "sandbox") if command else None
                    )
                    choices = [
                        f
                        for f in self.store.facts(db, ctx.tenant_id, clock, clock)
                        if f["kind"] == ("PAYABLE" if movement["delta"] < 0 else "RECEIVABLE")
                        and f["external_id"] == movement["reference"]
                        and f["value"]["counterparty"] == movement["counterparty"]
                        and (target_provider is None or f["provider"] == target_provider)
                    ]
                    if len(choices) == 1:
                        target = choices[0]
                        paid = db.execute(
                            "SELECT COALESCE(SUM(a.amount_minor),0) FROM allocations a JOIN facts f ON a.tenant_id=f.tenant_id AND a.obligation_id=f.fact_id "
                            "WHERE a.tenant_id=? AND f.kind=? AND f.provider=? AND f.external_id=?",
                            (
                                ctx.tenant_id,
                                target["kind"],
                                target["provider"],
                                target["external_id"],
                            ),
                        ).fetchone()[0]
                        amount = min(
                            abs(movement["delta"]), max(0, target["value"]["amount_minor"] - paid)
                        )
                        if amount:
                            allocate_in_transaction(
                                db, ctx.tenant_id, tx_id, target["fact_id"], amount, clock
                            )
                if movement["delta"]:
                    db.execute(
                        "INSERT INTO ledger VALUES(?,?,1,'cash',?,'CNY',?)",
                        (ctx.tenant_id, movement["ref"], movement["delta"], movement["at"]),
                    )
                    db.execute(
                        "INSERT INTO ledger VALUES(?,?,2,'clearing',?,'CNY',?)",
                        (ctx.tenant_id, movement["ref"], -movement["delta"], movement["at"]),
                    )
                db.execute(
                    "INSERT INTO inbox VALUES(?,'sandbox',?)", (ctx.tenant_id, movement["ref"])
                )
                if action:
                    db.execute(
                        "UPDATE actions SET status='SETTLED',provider_ref=?,state_version=state_version+1 WHERE tenant_id=? AND action_id=?",
                        (movement["ref"], ctx.tenant_id, action["action_id"]),
                    )
                    db.execute(
                        "UPDATE reservations SET status='RELEASED' WHERE tenant_id=? AND action_id=?",
                        (ctx.tenant_id, action["action_id"]),
                    )
                    db.execute(
                        "UPDATE outbox SET delivered=1 WHERE tenant_id=? AND action_id=?",
                        (ctx.tenant_id, action["action_id"]),
                    )
                    db.execute(
                        "UPDATE attempts SET status='SETTLED' WHERE tenant_id=? AND action_id=?",
                        (ctx.tenant_id, action["action_id"]),
                    )
                    self.store.audit(
                        db,
                        ctx,
                        "action.settled_reconciled",
                        {"action_id": action["action_id"], "transaction_id": tx_id},
                    )
            # All accepted pending holds are reflected in this same fresh available observation.
            for accepted in observation.get("pending_operations", []):
                db.execute(
                    "UPDATE actions SET provider_ref=? WHERE tenant_id=? AND idempotency_key=? AND status IN ('SUBMITTED','UNKNOWN')",
                    (accepted["ref"], ctx.tenant_id, accepted["stable_key"]),
                )
            db.execute(
                "UPDATE reservations SET included_in_provider_available=1 WHERE tenant_id=? AND action_id IN "
                "(SELECT action_id FROM actions WHERE tenant_id=? AND status IN ('SUBMITTED','UNKNOWN') AND provider_ref IS NOT NULL)",
                (ctx.tenant_id, ctx.tenant_id),
            )
            facts = self.store.facts(db, ctx.tenant_id, clock, clock)
            local_cash = sum(
                f["value"]["amount_minor"]
                for f in facts
                if f["kind"] == "BALANCE"
                or (f["kind"] == "TRANSACTION" and f["value"]["status"] == "SETTLED")
            )
            result = {
                "reconciliation_id": uid("reconciliation"),
                "at": clock,
                "local_cash_minor": local_cash,
                "provider_cash_minor": observation["cash_minor"],
                "matched": local_cash == observation["cash_minor"],
                "discrepancy_minor": local_cash - observation["cash_minor"],
                "status": "RECONCILED"
                if local_cash == observation["cash_minor"]
                else "NEEDS_RECONCILIATION",
            }
            self.store.put_object(
                db, ctx.tenant_id, "reconciliation", result["reconciliation_id"], result
            )
            if not result["matched"]:
                db.execute("UPDATE companies SET stopped=1 WHERE tenant_id=?", (ctx.tenant_id,))
                self.store.audit(db, ctx, "reconciliation.mismatch", result)
            return result

    def revoke(self, ctx: AuthContext, approval_id: str) -> None:
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, {"OWNER"})
            count = db.execute(
                "UPDATE approvals SET revoked=1 WHERE tenant_id=? AND approval_id=?",
                (ctx.tenant_id, approval_id),
            ).rowcount
            require(count == 1, "NOT_FOUND", "Scoped approval not found")
            self.store.audit(db, ctx, "approval.revoked", {"approval_id": approval_id})

    def stop(self, ctx: AuthContext, enabled: bool, reason: str) -> None:
        require(
            type(enabled) is bool and bool(reason),
            "INVALID_ARGUMENTS",
            "Explicit stop state and reason required",
        )
        roles = {"OWNER", "ADMIN"} if enabled else {"OWNER"}
        reconciliation_id = None
        if not enabled:
            with self.store.connect() as db:
                self.store.authorize(db, ctx, roles)
            recon = self.refresh(ctx)
            require(
                recon["matched"],
                "RECONCILIATION_REQUIRED",
                "Cash does not reconcile with the sandbox; resolve the difference before resuming",
            )
            reconciliation_id = recon["reconciliation_id"]
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, roles)
            db.execute(
                "UPDATE companies SET stopped=? WHERE tenant_id=?", (int(enabled), ctx.tenant_id)
            )
            self.store.audit(
                db,
                ctx,
                "control.stop",
                {
                    "enabled": enabled,
                    "reason": reason,
                    "actor": ctx.user_id,
                    "role": ctx.role,
                    "reconciliation_id": reconciliation_id,
                },
            )

    def cancel_plan(self, ctx: AuthContext, plan_id: str) -> Json:
        self.store.get_object(ctx, "plan", plan_id)
        with self.store.transaction() as db:
            self.store.authorize(db, ctx, {"OWNER"})
            db.execute(
                "INSERT OR IGNORE INTO objects VALUES(?,'cancelled_plan',?,?,?)",
                (
                    ctx.tenant_id,
                    plan_id,
                    canonical({"reason": "owner cancelled future sends"}),
                    self.store.company(ctx)["clock"],
                ),
            )
            self.store.audit(db, ctx, "plan.cancelled", {"plan_id": plan_id})
        return {
            "status": "CANCELLED",
            "sent_operations": "Continue status lookup and reconciliation",
        }

    def plan_status(self, ctx: AuthContext, plan_id: str) -> Json:
        plan = self.store.get_object(ctx, "plan", plan_id)
        with self.store.connect() as db:
            self.store.authorize(db, ctx)
            states = {
                r["action_id"]: r["status"]
                for r in db.execute(
                    "SELECT action_id,status FROM actions WHERE tenant_id=?", (ctx.tenant_id,)
                )
            }
        settled = sum(states.get(a["action_id"]) == "SETTLED" for a in plan["actions"])
        pending = [states.get(a["action_id"], "AWAITING_APPROVAL") for a in plan["actions"]]
        return {
            "status": "COMPLETED"
            if settled == len(plan["actions"])
            else "PARTIALLY_EXECUTED"
            if settled
            else "AWAITING_APPROVAL",
            "settled_actions": settled,
            "total_actions": len(plan["actions"]),
            "action_states": pending,
        }
