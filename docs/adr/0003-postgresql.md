# ADR 0003 — PostgreSQL financial store and development lifecycle

2026-10-12. Supersedes the SQLite-only deployment choice in ADR 0001. The financial
kernel and contracts are shared by both stores; PostgreSQL is a real psycopg
backend, not a mirrored report or an unexecuted interface. FastAPI/worker select it
when the workspace has an admin-provisioned `postgres.secret.json`.

The explicit migration lives in `finance/postgres/001_core.sql`. Only the bootstrap
command has an admin connection. Each tenant receives a random-password login
with NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE and no schema creation rights.
FORCE RLS on every business table uses `session_user` mapped by a security-definer
function with a fixed search path. A caller-controlled tenant GUC is not used.
Sources, objects, documents, facts, ledger, audit and review events deny UPDATE/DELETE.
Application membership roles and exact approvals still apply above these DB rights.

The adapter translates only fixed repository parameter markers and conflict syntax.
Generated sequence columns preserve insertion order for version lookups. A database
advisory transaction lock preserves the existing serialized reserve/outbox/audit
semantics; this is intentionally low-throughput and must be profiled before scale.
API and worker use the tenant login, never the bootstrap admin. They currently
share that tenant role; a separate worker-only privilege set remains open.

LangGraph checkpoints remain per-tenant SQLite files in the observed workspace.
The independent simulator retains its separate SQLite truth database and process.
This is a documented mixed-storage deployment, not a claim of a PostgreSQL graph
checkpointer or OS isolation. Existing SQLite workspaces are not auto-migrated.

Actual local PostgreSQL 18.6 tests cover complete lost-response golden execution,
restart, graph persistence, parallel reservations and cross-tenant direct SQL/DDL
denial. See `artifacts/postgres-tests.json`. PostgreSQL is a portable process bound
to 127.0.0.1 with SCRAM; no Windows service was installed.

Sources: [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html),
[official EDB binary page](https://www.enterprisedb.com/download-postgresql-binaries).
