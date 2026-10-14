# Local PostgreSQL runtime

The financial store supports real PostgreSQL through psycopg. Existing SQLite
workspaces remain readable; no destructive migration or automatic copying occurs.
Checkpoints and the independent simulator remain separate SQLite databases.

This Windows workspace uses the portable archive linked by the
[official EDB binary page](https://www.enterprisedb.com/download-postgresql-binaries):
PostgreSQL 18.6, downloaded from
`https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip`.
Observed SHA256: `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2`.
This is a locally computed integrity hash, not a claim of a vendor signature.
The ignored archive was extracted to `.runtime/postgres/binaries/pgsql`.

Run once, then preserve the cluster:

```powershell
.venv\Scripts\python.exe -m scripts.postgres init
.venv\Scripts\python.exe -m scripts.postgres start
.venv\Scripts\python.exe -m scripts.postgres provision --workspace .runtime/pg-workspace
.venv\Scripts\python.exe -m scripts.serve --port 8080 --directory .runtime/pg-workspace
```

The existing cluster is already initialized/provisioned. For subsequent sessions
use `status`, `start` only if stopped, and the same `serve --directory`. `init` and
`provision` refuse to overwrite existing state. `stop` uses pg_ctl fast shutdown,
retains files and only targets this cluster. No system service is installed.

The cluster binds 127.0.0.1 on a port saved in `cluster.secret.json`, uses SCRAM,
and holds only synthetic data. The admin DSN is for migrations/provisioning/tests.
API/worker receive a restricted tenant DSN from the workspace secret file. Do not
print, export or publish these files. SQL RLS uses the login identity; a tenant
request parameter cannot change it. Windows administrator/OS isolation is separate.

Actual integration command (requires the running local cluster):

```powershell
$env:SME_POSTGRES_TEST_CONFIG = '.runtime/postgres/cluster.secret.json'
.venv\Scripts\python.exe -m scripts.test --pattern test_postgres.py --output artifacts/postgres-tests.json
```

Tests create uniquely named synthetic companies and restricted roles. They do not
drop existing databases or truncate user data. The full test suite includes these
tests only when this explicit configuration is present; otherwise it records SKIPPED.
Use an isolated test cluster for sustained runs. Portable binaries are not bundled
as application source and are not downloaded automatically by application startup.

Forward migrations for an existing cluster: `.venv\Scripts\python.exe -m scripts.postgres migrate`.
Migration 002 adds nullable policy observation time. Unknown legacy times are not
backfilled with guessed values; current operation remains supported, historical
recomputation fails explicitly when the policy cannot be established.
