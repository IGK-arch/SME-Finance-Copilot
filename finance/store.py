"""Scoped durable observed-state repository. No simulator truth access."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Iterator, Literal

from finance.domain import AuthContext, Json, canonical, digest, now, require, uid, utc

READ_ROLES = {"OWNER", "ACCOUNTANT", "AUDITOR", "ADMIN"}


class ClosingConnection(sqlite3.Connection):
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> Literal[False]:
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


class Store:
    backend = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript((Path(__file__).parent / "migrations/001_core.sql").read_text())
            db.execute("INSERT OR IGNORE INTO schema_migrations VALUES(1,?)", (now(),))
            for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                version = int(migration.name.split("_")[0])
                if not db.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                ).fetchone():
                    db.executescript(migration.read_text(encoding="utf-8"))
                    db.execute("INSERT INTO schema_migrations VALUES(?,?)", (version, now()))

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_company(self, tenant: str, profile: Json, clock: str) -> dict[str, str]:
        """Bootstrap-only local setup; not exposed to tools or public HTTP."""
        tokens: dict[str, str] = {}
        with self.transaction() as db:
            db.execute(
                "INSERT INTO companies(tenant_id,name,profile,clock) VALUES(?,?,?,?)",
                (tenant, profile["name"], canonical(profile), utc(clock)),
            )
            db.execute("INSERT INTO accounts VALUES(?, 'operating', 'CNY')", (tenant,))
            policy = {
                "schema_version": 1,
                "version": "policy_demo_07",
                "reserve_minor": 2000000,
                "currency": "CNY",
                "sandbox_only": True,
                "protected": ["salary", "rent"],
                "new_beneficiary_requires_approval": True,
            }
            db.execute(
                "INSERT INTO policies(tenant_id,version,payload,observed_at) VALUES(?,?,?,?)",
                (tenant, policy["version"], canonical(policy), utc(clock)),
            )
            for role in sorted(READ_ROLES):
                token = secrets.token_urlsafe(32)
                tokens[role] = token
                db.execute(
                    "INSERT INTO memberships(tenant_id,user_id,role,token_hash) VALUES(?,?,?,?)",
                    (tenant, role.lower(), role, self.token_hash(token)),
                )
            for logical, name in (
                ("salary", "Payroll"),
                ("rent", "Landlord"),
                ("supplier", "苏州合成供应商"),
                ("lender", "DEMO lender"),
            ):
                db.execute(
                    "INSERT INTO beneficiaries VALUES(?,?,?,1,?)",
                    (
                        tenant,
                        logical + "_v1",
                        logical,
                        canonical(
                            {
                                "name": name,
                                "fingerprint": digest([tenant, logical]),
                                "source": "SYNTHETIC",
                                "verified_by": "owner",
                            }
                        ),
                    ),
                )
            self.audit(db, tenant, "company.created", {"data_mode": "synthetic"})
        return tokens

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def authenticate(self, token: str) -> AuthContext:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM memberships WHERE token_hash=? AND active=1",
                (self.token_hash(token),),
            ).fetchone()
        require(row is not None, "UNAUTHORIZED", "Valid local membership token required")
        return AuthContext(row["tenant_id"], row["user_id"], row["role"])

    def authorize(
        self, db: sqlite3.Connection, ctx: AuthContext, roles: set[str] | None = None
    ) -> None:
        row = db.execute(
            "SELECT * FROM memberships WHERE tenant_id=? AND user_id=? AND active=1",
            (ctx.tenant_id, ctx.user_id),
        ).fetchone()
        require(
            row is not None and row["role"] == ctx.role and ctx.role in (roles or READ_ROLES),
            "POLICY_DENIED",
            "Current membership does not permit this operation",
        )

    def company(self, ctx: AuthContext) -> Json:
        with self.connect() as db:
            self.authorize(db, ctx)
            row = db.execute(
                "SELECT * FROM companies WHERE tenant_id=?", (ctx.tenant_id,)
            ).fetchone()
            return dict(row)

    def policy(self, db: sqlite3.Connection, tenant: str, cutoff: str | None = None) -> Json:
        if cutoff is None:
            row = db.execute(
                "SELECT payload FROM policies WHERE tenant_id=? ORDER BY rowid DESC LIMIT 1",
                (tenant,),
            ).fetchone()
        else:
            # New policy changes are effective when observed by the server. Old
            # migrated rows have unknown times; do not assign invented timestamps.
            clock = db.execute(
                "SELECT clock FROM companies WHERE tenant_id=?", (tenant,)
            ).fetchone()[0]
            row = db.execute(
                "SELECT payload,rowid FROM policies WHERE tenant_id=? AND observed_at<=? ORDER BY rowid DESC LIMIT 1",
                (tenant, utc(cutoff)),
            ).fetchone()
            legacy = db.execute(
                "SELECT payload,rowid FROM policies WHERE tenant_id=? AND observed_at IS NULL ORDER BY rowid DESC LIMIT 1",
                (tenant,),
            ).fetchone()
            if legacy and (row is None or legacy["rowid"] > row["rowid"]):
                require(
                    utc(cutoff) >= clock,
                    "POLICY_HISTORY_UNVERIFIED",
                    "Legacy policy observation time is unknown; historical recomputation is unavailable",
                )
                row = legacy
        require(row is not None, "INSUFFICIENT_DATA", "No policy observed by this cutoff")
        return json.loads(row[0])

    @staticmethod
    def audit(
        db: sqlite3.Connection, tenant: str | AuthContext, event_type: str, payload: Json
    ) -> None:
        if isinstance(tenant, AuthContext):
            payload = {"actor": tenant.user_id, "actor_role": tenant.role} | payload
            tenant = tenant.tenant_id
        row = db.execute(
            "SELECT event_hash FROM audit WHERE tenant_id=? ORDER BY audit_id DESC LIMIT 1",
            (tenant,),
        ).fetchone()
        previous = row[0] if row else "0" * 64
        timestamp = now()
        value = digest([previous, timestamp, event_type, payload])
        db.execute(
            "INSERT INTO audit(tenant_id,occurred_at,event_type,payload,previous_hash,event_hash) "
            "VALUES(?,?,?,?,?,?)",
            (tenant, timestamp, event_type, canonical(payload), previous, value),
        )

    def put_object(
        self, db: sqlite3.Connection, tenant: str, kind: str, object_id: str, payload: Json
    ) -> None:
        db.execute(
            "INSERT INTO objects VALUES(?,?,?,?,?)",
            (tenant, kind, object_id, canonical(payload), now()),
        )

    def get_object(self, ctx: AuthContext, kind: str, object_id: str) -> Json:
        with self.connect() as db:
            self.authorize(db, ctx)
            row = db.execute(
                "SELECT payload FROM objects WHERE tenant_id=? AND kind=? AND object_id=?",
                (ctx.tenant_id, kind, object_id),
            ).fetchone()
            require(row is not None, "NOT_FOUND", "Scoped object not found")
            return json.loads(row[0])

    def facts(self, db: sqlite3.Connection, tenant: str, as_of: str, cutoff: str) -> list[Json]:
        rows = db.execute(
            "SELECT * FROM facts WHERE tenant_id=? AND effective_at<=? AND observed_at<=? "
            "ORDER BY version,observed_at,fact_id",
            (tenant, utc(as_of), utc(cutoff)),
        )
        current: dict[tuple[str, str, str], Json] = {}
        for row in rows:
            item = dict(row)
            item["value"] = json.loads(item.pop("payload"))
            current[(row["kind"], row["provider"], row["external_id"])] = item
        return list(current.values())

    def add_fact(
        self, db: sqlite3.Connection, tenant: str, provider: str, source_id: str, value: Json
    ) -> bool:
        key = (tenant, value["kind"], provider, value["external_id"], value["version"])
        existing = db.execute(
            "SELECT payload FROM facts WHERE tenant_id=? AND kind=? AND provider=? "
            "AND external_id=? AND version=?",
            key,
        ).fetchone()
        if existing:
            require(
                existing[0] == canonical(value),
                "SOURCE_CONFLICT",
                "Conflicting fact requires review",
            )
            return False
        previous = db.execute(
            "SELECT fact_id,version FROM facts WHERE tenant_id=? AND kind=? "
            "AND provider=? AND external_id=? ORDER BY version DESC LIMIT 1",
            key[:4],
        ).fetchone()
        require(
            previous is None or value["version"] > previous["version"],
            "SOURCE_CONFLICT",
            "Older correction requires review",
        )
        db.execute(
            "INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant,
                uid("fact"),
                value["kind"],
                provider,
                value["external_id"],
                value["version"],
                utc(value["event_time"]),
                utc(value["observed_time"]),
                canonical(value),
                source_id,
                previous["fact_id"] if previous else None,
            ),
        )
        db.execute("UPDATE companies SET data_version=data_version+1 WHERE tenant_id=?", (tenant,))
        return True

    def source(
        self, db: sqlite3.Connection, tenant: str, provider: str, content: bytes, observed_at: str
    ) -> tuple[str, bool]:
        hashed = hashlib.sha256(content).hexdigest()
        old = db.execute(
            "SELECT source_id FROM sources WHERE tenant_id=? AND provider=? AND content_hash=?",
            (tenant, provider, hashed),
        ).fetchone()
        if old:
            return old[0], False
        source_id = uid("source")
        db.execute(
            "INSERT INTO sources VALUES(?,?,?,?,?,?)",
            (tenant, source_id, provider, hashed, content, utc(observed_at)),
        )
        return source_id, True

    def evidence(self, ctx: AuthContext, source_id: str) -> Json:
        with self.connect() as db:
            self.authorize(db, ctx)
            restricted = db.execute(
                "SELECT read_roles FROM documents WHERE tenant_id=? AND source_id=?",
                (ctx.tenant_id, source_id),
            ).fetchall()
            require(
                all(ctx.role in json.loads(r[0]) for r in restricted),
                "POLICY_DENIED",
                "Document evidence access denied",
            )
            row = db.execute(
                "SELECT * FROM sources WHERE tenant_id=? AND source_id=? AND observed_at<=(SELECT clock FROM companies WHERE tenant_id=?)",
                (ctx.tenant_id, source_id, ctx.tenant_id),
            ).fetchone()
            require(row is not None, "NOT_FOUND", "Scoped source not found")
            return {
                "source_id": row["source_id"],
                "provider": row["provider"],
                "hash": row["content_hash"],
                "observed_at": row["observed_at"],
                "trust": "SYNTHETIC_UNTRUSTED_DATA",
                "text": bytes(row["content"]).decode("utf-8", errors="replace"),
            }

    def verify_audit(self, ctx: AuthContext) -> Json:
        with self.connect() as db:
            self.authorize(db, ctx)
            previous = "0" * 64
            count = 0
            for row in db.execute(
                "SELECT audit_id,occurred_at,event_type,payload,previous_hash,event_hash "
                "FROM audit WHERE tenant_id=? ORDER BY audit_id",
                (ctx.tenant_id,),
            ):
                expected = digest(
                    [previous, row["occurred_at"], row["event_type"], json.loads(row["payload"])]
                )
                if row["previous_hash"] != previous or row["event_hash"] != expected:
                    return {
                        "valid": False,
                        "checked": count,
                        "first_bad_audit_id": row["audit_id"],
                        "reason": "LINK_BROKEN"
                        if row["previous_hash"] != previous
                        else "HASH_MISMATCH",
                    }
                previous = row["event_hash"]
                count += 1
        return {"valid": True, "checked": count, "head_hash": previous}

    def audit_log(self, ctx: AuthContext) -> list[Json]:
        with self.connect() as db:
            self.authorize(db, ctx)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM audit WHERE tenant_id=? ORDER BY audit_id", (ctx.tenant_id,)
                )
            ]
