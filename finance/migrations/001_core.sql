PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies(
 tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, profile TEXT NOT NULL,
 clock TEXT NOT NULL, data_version INTEGER NOT NULL DEFAULT 0,
 stopped INTEGER NOT NULL DEFAULT 0 CHECK(stopped IN (0,1)));
CREATE TABLE IF NOT EXISTS memberships(
 tenant_id TEXT NOT NULL REFERENCES companies, user_id TEXT NOT NULL, role TEXT NOT NULL
 CHECK(role IN ('OWNER','ACCOUNTANT','AUDITOR','ADMIN')), active INTEGER NOT NULL DEFAULT 1,
 token_hash TEXT NOT NULL UNIQUE, PRIMARY KEY(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS accounts(
 tenant_id TEXT NOT NULL REFERENCES companies, account_id TEXT NOT NULL,
 currency TEXT NOT NULL CHECK(currency='CNY'), PRIMARY KEY(tenant_id,account_id));
CREATE TABLE IF NOT EXISTS policies(
 tenant_id TEXT NOT NULL REFERENCES companies, version TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,version));
CREATE TABLE IF NOT EXISTS beneficiaries(
 tenant_id TEXT NOT NULL REFERENCES companies, version_id TEXT NOT NULL, logical_id TEXT NOT NULL,
 verified INTEGER NOT NULL CHECK(verified IN (0,1)), payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,version_id));
CREATE TABLE IF NOT EXISTS sources(
 tenant_id TEXT NOT NULL REFERENCES companies, source_id TEXT NOT NULL, provider TEXT NOT NULL,
 content_hash TEXT NOT NULL, content BLOB NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,source_id), UNIQUE(tenant_id,provider,content_hash));
CREATE TABLE IF NOT EXISTS imports(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, source_id TEXT NOT NULL,
 status TEXT NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,import_id), FOREIGN KEY(tenant_id,source_id) REFERENCES sources);
CREATE TABLE IF NOT EXISTS quarantine(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, row_number INTEGER NOT NULL,
 code TEXT NOT NULL, raw TEXT NOT NULL,
 FOREIGN KEY(tenant_id,import_id) REFERENCES imports);
CREATE TABLE IF NOT EXISTS facts(
 tenant_id TEXT NOT NULL REFERENCES companies, fact_id TEXT NOT NULL, kind TEXT NOT NULL,
 provider TEXT NOT NULL, external_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 effective_at TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL,
 source_id TEXT NOT NULL, supersedes_id TEXT,
 PRIMARY KEY(tenant_id,fact_id), UNIQUE(tenant_id,kind,provider,external_id,version),
 FOREIGN KEY(tenant_id,source_id) REFERENCES sources,
 FOREIGN KEY(tenant_id,supersedes_id) REFERENCES facts);
CREATE INDEX IF NOT EXISTS facts_cutoff ON facts(tenant_id,observed_at,effective_at);
CREATE TABLE IF NOT EXISTS allocations(
 tenant_id TEXT NOT NULL, allocation_id TEXT NOT NULL, transaction_id TEXT NOT NULL,
 obligation_id TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
 effective_at TEXT NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,allocation_id), UNIQUE(tenant_id,transaction_id,obligation_id),
 FOREIGN KEY(tenant_id,transaction_id) REFERENCES facts(tenant_id,fact_id),
 FOREIGN KEY(tenant_id,obligation_id) REFERENCES facts(tenant_id,fact_id));
CREATE TABLE IF NOT EXISTS objects(
 tenant_id TEXT NOT NULL REFERENCES companies, kind TEXT NOT NULL, object_id TEXT NOT NULL,
 payload TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,kind,object_id));
CREATE TABLE IF NOT EXISTS approvals(
 tenant_id TEXT NOT NULL, approval_id TEXT NOT NULL, actor TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload TEXT NOT NULL, expires_at TEXT NOT NULL,
 revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 PRIMARY KEY(tenant_id,approval_id), FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS actions(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('RESERVED','SUBMITTED','UNKNOWN','SETTLED','FAILED')),
 approval_id TEXT NOT NULL, provider_ref TEXT, state_version INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(tenant_id,action_id), UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES approvals);
CREATE TABLE IF NOT EXISTS reservations(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, account_id TEXT NOT NULL,
 amount_minor INTEGER NOT NULL CHECK(amount_minor>=0), status TEXT NOT NULL
 CHECK(status IN ('ACTIVE','RELEASED')), included_in_provider_available INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,action_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions,
 FOREIGN KEY(tenant_id,account_id) REFERENCES accounts);
CREATE TABLE IF NOT EXISTS outbox(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(tenant_id,action_id),
 FOREIGN KEY(tenant_id,action_id) REFERENCES actions);
CREATE TABLE IF NOT EXISTS attempts(
 tenant_id TEXT NOT NULL, attempt_id TEXT NOT NULL, action_id TEXT NOT NULL,
 sent_at TEXT NOT NULL, status TEXT NOT NULL, request_hash TEXT NOT NULL,
 PRIMARY KEY(tenant_id,attempt_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions);
CREATE TABLE IF NOT EXISTS inbox(
 tenant_id TEXT NOT NULL REFERENCES companies, provider TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,provider,event_id));
CREATE TABLE IF NOT EXISTS ledger(
 tenant_id TEXT NOT NULL, entry_id TEXT NOT NULL, line INTEGER NOT NULL,
 account TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor<>0),
 currency TEXT NOT NULL CHECK(currency='CNY'), effective_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,entry_id,line), FOREIGN KEY(tenant_id) REFERENCES companies);
CREATE TABLE IF NOT EXISTS audit(
 tenant_id TEXT NOT NULL REFERENCES companies, audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
 occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_facts_update BEFORE UPDATE ON facts
 BEGIN SELECT RAISE(ABORT,'facts are append only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_facts_delete BEFORE DELETE ON facts
 BEGIN SELECT RAISE(ABORT,'facts are append only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_ledger_update BEFORE UPDATE ON ledger
 BEGIN SELECT RAISE(ABORT,'ledger is append only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_ledger_delete BEFORE DELETE ON ledger
 BEGIN SELECT RAISE(ABORT,'ledger is append only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_update BEFORE UPDATE ON audit
 BEGIN SELECT RAISE(ABORT,'audit is append only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_delete BEFORE DELETE ON audit
 BEGIN SELECT RAISE(ABORT,'audit is append only'); END;
