"""PostgreSQL repository for the same domain, with per-tenant restricted login roles.

Only this adapter translates the small, fixed repository SQL dialect. No SQL or
connection credentials are exposed through model tools or browser responses.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, cast

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from finance.domain import Json, digest, require
from finance.store import Store


class Row(dict):
    def __getitem__(self, key: Any) -> Any:
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def row_factory(cursor: Any) -> Any:
    names = [c.name for c in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values))


class Connection:
    def __init__(self, dsn: str) -> None:
        self.db = psycopg.connect(dsn, autocommit=True, row_factory=row_factory)

    def execute(self, statement: str, params: tuple = ()) -> Any:
        if statement == "BEGIN IMMEDIATE":
            self.db.execute("BEGIN")
            # Preserve the existing financial kernel's serial reservation/audit
            # semantics. Deliberately one writer at a time across this small DB.
            return self.db.execute("SELECT pg_advisory_xact_lock(823904173)")
        statement = statement.replace("?", "%s")
        if "INSERT OR IGNORE INTO" in statement:
            statement = statement.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            statement += " ON CONFLICT DO NOTHING"
        return self.db.execute(statement, params)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class PostgresStore(Store):
    backend = "postgresql"

    def __init__(self, dsn: str, checkpoint_directory: Path) -> None:
        config = conninfo_to_dict(dsn)
        require(
            config.get("host") == "127.0.0.1",
            "DATABASE_EGRESS_DENIED",
            "This development runtime supports loopback PostgreSQL only",
        )
        self.dsn = dsn
        # Existing workflow checkpoint files remain explicitly SQLite, scoped to
        # this workspace/tenant. Financial state is in PostgreSQL.
        checkpoint_directory.mkdir(parents=True, exist_ok=True)
        self.path = str(checkpoint_directory / "postgres-observed")

    def connect(self) -> sqlite3.Connection:
        # Shared methods use this structural execute/transaction interface.
        # The cast keeps old annotated callers source-compatible, not an SQLite DB.
        return cast(sqlite3.Connection, Connection(self.dsn))

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise


def migrate(admin_dsn: str) -> None:
    """Admin-only explicit migration; never called by an HTTP request or worker."""
    with psycopg.connect(admin_dsn) as db:
        db.execute("SELECT pg_advisory_xact_lock(823904173)")
        db.execute((Path(__file__).parent / "postgres/001_core.sql").read_text(encoding="utf-8"))
        db.execute(
            (Path(__file__).parent / "postgres/002_policy_time.sql").read_text(encoding="utf-8")
        )


def provision(
    admin_dsn: str, tenant: str, profile: Json, clock: str, directory: Path
) -> tuple[PostgresStore, dict[str, str]]:
    require(bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", tenant)), "INVALID_TENANT", "Invalid tenant")
    admin = PostgresStore(admin_dsn, directory)
    tokens = admin.create_company(tenant, profile, clock)
    role = "sme_" + digest(tenant)[:20]
    password = secrets.token_urlsafe(40)
    with psycopg.connect(admin_dsn) as db:
        db.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        db.execute("INSERT INTO tenant_login_scopes VALUES(%s,%s)", (role, tenant))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        tables = db.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename NOT IN ('schema_migrations','tenant_login_scopes')"
        ).fetchall()
        for (table,) in tables:
            db.execute(
                sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON {} TO {}").format(
                    sql.Identifier(table), sql.Identifier(role)
                )
            )
        for table in (
            "facts",
            "ledger",
            "audit",
            "sources",
            "objects",
            "review_decisions",
            "documents",
            "workflow_events",
        ):
            db.execute(
                sql.SQL("REVOKE UPDATE,DELETE ON {} FROM {}").format(
                    sql.Identifier(table), sql.Identifier(role)
                )
            )
        db.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                sql.Identifier(role)
            )
        )
    values = conninfo_to_dict(admin_dsn) | {"user": role, "password": password}
    return PostgresStore(
        make_conninfo(**{key: str(value) for key, value in values.items() if value is not None}),
        directory,
    ), tokens
