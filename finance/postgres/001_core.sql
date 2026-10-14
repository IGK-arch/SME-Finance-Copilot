
CREATE TABLE IF NOT EXISTS schema_migrations(version BIGINT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies(
 tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, profile TEXT NOT NULL,
 clock TEXT NOT NULL, data_version BIGINT NOT NULL DEFAULT 0,
 stopped BIGINT NOT NULL DEFAULT 0 CHECK(stopped IN (0,1)));
CREATE TABLE IF NOT EXISTS memberships(
 tenant_id TEXT NOT NULL REFERENCES companies, user_id TEXT NOT NULL, role TEXT NOT NULL
 CHECK(role IN ('OWNER','ACCOUNTANT','AUDITOR','ADMIN')), active BIGINT NOT NULL DEFAULT 1,
 token_hash TEXT NOT NULL UNIQUE, PRIMARY KEY(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS accounts(
 tenant_id TEXT NOT NULL REFERENCES companies, account_id TEXT NOT NULL,
 currency TEXT NOT NULL CHECK(currency='CNY'), PRIMARY KEY(tenant_id,account_id));
CREATE TABLE IF NOT EXISTS policies(
 tenant_id TEXT NOT NULL REFERENCES companies, version TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,version));
CREATE TABLE IF NOT EXISTS beneficiaries(
 tenant_id TEXT NOT NULL REFERENCES companies, version_id TEXT NOT NULL, logical_id TEXT NOT NULL,
 verified BIGINT NOT NULL CHECK(verified IN (0,1)), payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,version_id));
CREATE TABLE IF NOT EXISTS sources(
 tenant_id TEXT NOT NULL REFERENCES companies, source_id TEXT NOT NULL, provider TEXT NOT NULL,
 content_hash TEXT NOT NULL, content BYTEA NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,source_id), UNIQUE(tenant_id,provider,content_hash));
CREATE TABLE IF NOT EXISTS imports(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, source_id TEXT NOT NULL,
 status TEXT NOT NULL, accepted BIGINT NOT NULL, rejected BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,import_id), FOREIGN KEY(tenant_id,source_id) REFERENCES sources);
CREATE TABLE IF NOT EXISTS quarantine(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, row_number BIGINT NOT NULL,
 code TEXT NOT NULL, raw TEXT NOT NULL,
 FOREIGN KEY(tenant_id,import_id) REFERENCES imports);
CREATE TABLE IF NOT EXISTS facts(
 tenant_id TEXT NOT NULL REFERENCES companies, fact_id TEXT NOT NULL, kind TEXT NOT NULL,
 provider TEXT NOT NULL, external_id TEXT NOT NULL, version BIGINT NOT NULL CHECK(version>0),
 effective_at TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL,
 source_id TEXT NOT NULL, supersedes_id TEXT,
 PRIMARY KEY(tenant_id,fact_id), UNIQUE(tenant_id,kind,provider,external_id,version),
 FOREIGN KEY(tenant_id,source_id) REFERENCES sources,
 FOREIGN KEY(tenant_id,supersedes_id) REFERENCES facts);
CREATE INDEX IF NOT EXISTS facts_cutoff ON facts(tenant_id,observed_at,effective_at);
CREATE TABLE IF NOT EXISTS allocations(
 tenant_id TEXT NOT NULL, allocation_id TEXT NOT NULL, transaction_id TEXT NOT NULL,
 obligation_id TEXT NOT NULL, amount_minor BIGINT NOT NULL CHECK(amount_minor>0),
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
 revoked BIGINT NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 PRIMARY KEY(tenant_id,approval_id), FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS actions(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('RESERVED','SUBMITTED','UNKNOWN','SETTLED','FAILED')),
 approval_id TEXT NOT NULL, provider_ref TEXT, state_version BIGINT NOT NULL DEFAULT 1,
 PRIMARY KEY(tenant_id,action_id), UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES approvals);
CREATE TABLE IF NOT EXISTS reservations(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, account_id TEXT NOT NULL,
 amount_minor BIGINT NOT NULL CHECK(amount_minor>=0), status TEXT NOT NULL
 CHECK(status IN ('ACTIVE','RELEASED')), included_in_provider_available BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,action_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions,
 FOREIGN KEY(tenant_id,account_id) REFERENCES accounts);
CREATE TABLE IF NOT EXISTS outbox(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, delivered BIGINT NOT NULL DEFAULT 0,
 attempts BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(tenant_id,action_id),
 FOREIGN KEY(tenant_id,action_id) REFERENCES actions);
CREATE TABLE IF NOT EXISTS attempts(
 tenant_id TEXT NOT NULL, attempt_id TEXT NOT NULL, action_id TEXT NOT NULL,
 sent_at TEXT NOT NULL, status TEXT NOT NULL, request_hash TEXT NOT NULL,
 PRIMARY KEY(tenant_id,attempt_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions);
CREATE TABLE IF NOT EXISTS inbox(
 tenant_id TEXT NOT NULL REFERENCES companies, provider TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,provider,event_id));
CREATE TABLE IF NOT EXISTS ledger(
 tenant_id TEXT NOT NULL, entry_id TEXT NOT NULL, line BIGINT NOT NULL,
 account TEXT NOT NULL, amount_minor BIGINT NOT NULL CHECK(amount_minor<>0),
 currency TEXT NOT NULL CHECK(currency='CNY'), effective_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,entry_id,line), FOREIGN KEY(tenant_id) REFERENCES companies);
CREATE TABLE IF NOT EXISTS audit(
 tenant_id TEXT NOT NULL REFERENCES companies, audit_id BIGSERIAL PRIMARY KEY,
 occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS review_decisions(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, row_number BIGINT NOT NULL,
 actor TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
 corrected_source_id TEXT, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,import_id,row_number),
 FOREIGN KEY(tenant_id,import_id) REFERENCES imports,
 FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS documents(
 tenant_id TEXT NOT NULL, document_id TEXT NOT NULL, version BIGINT NOT NULL,
 source_id TEXT NOT NULL, title TEXT NOT NULL, text_content TEXT NOT NULL,
 read_roles TEXT NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,document_id,version), FOREIGN KEY(tenant_id,source_id) REFERENCES sources);
CREATE TABLE IF NOT EXISTS execution_jobs(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, actor TEXT NOT NULL,
 fault TEXT NOT NULL DEFAULT 'none', lease_owner TEXT, lease_until DOUBLE PRECISION NOT NULL DEFAULT 0,
 next_attempt DOUBLE PRECISION NOT NULL DEFAULT 0, attempts BIGINT NOT NULL DEFAULT 0,
 last_error TEXT, finished BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,action_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions,
 FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS worker_health(
 tenant_id TEXT PRIMARY KEY REFERENCES companies, worker_id TEXT NOT NULL, heartbeat DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS workflow_runs(
 tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, actor TEXT NOT NULL, task TEXT NOT NULL,
 provider TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 status TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,run_id), FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS workflow_events(
 tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, event_id BIGSERIAL PRIMARY KEY,
 at TEXT NOT NULL, node TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(tenant_id,run_id) REFERENCES workflow_runs);
CREATE TABLE IF NOT EXISTS extension_requests(
 tenant_id TEXT NOT NULL, request_id TEXT NOT NULL, obligation_fact_id TEXT NOT NULL,
 proposed_due_at TEXT NOT NULL, status TEXT NOT NULL, decision_source_id TEXT,
 PRIMARY KEY(tenant_id,request_id), FOREIGN KEY(tenant_id,obligation_fact_id) REFERENCES facts(tenant_id,fact_id));

ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS lease_until DOUBLE PRECISION NOT NULL DEFAULT 0;

ALTER TABLE policies ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
ALTER TABLE actions ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
ALTER TABLE attempts ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
ALTER TABLE imports ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
ALTER TABLE approvals ADD COLUMN IF NOT EXISTS rowid BIGSERIAL;
CREATE TABLE IF NOT EXISTS tenant_login_scopes(login_name TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES companies);
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
CREATE OR REPLACE FUNCTION finance_tenant() RETURNS TEXT LANGUAGE SQL STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT tenant_id FROM public.tenant_login_scopes WHERE login_name=session_user $$;
REVOKE ALL ON FUNCTION finance_tenant() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION finance_tenant() TO PUBLIC;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON companies;
CREATE POLICY tenant_scope ON companies USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON memberships;
CREATE POLICY tenant_scope ON memberships USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON accounts;
CREATE POLICY tenant_scope ON accounts USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON policies;
CREATE POLICY tenant_scope ON policies USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE beneficiaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE beneficiaries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON beneficiaries;
CREATE POLICY tenant_scope ON beneficiaries USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON sources;
CREATE POLICY tenant_scope ON sources USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE imports FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON imports;
CREATE POLICY tenant_scope ON imports USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE quarantine ENABLE ROW LEVEL SECURITY;
ALTER TABLE quarantine FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON quarantine;
CREATE POLICY tenant_scope ON quarantine USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE facts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON facts;
CREATE POLICY tenant_scope ON facts USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON allocations;
CREATE POLICY tenant_scope ON allocations USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE objects FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON objects;
CREATE POLICY tenant_scope ON objects USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON approvals;
CREATE POLICY tenant_scope ON approvals USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON actions;
CREATE POLICY tenant_scope ON actions USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON reservations;
CREATE POLICY tenant_scope ON reservations USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON outbox;
CREATE POLICY tenant_scope ON outbox USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE attempts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON attempts;
CREATE POLICY tenant_scope ON attempts USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON inbox;
CREATE POLICY tenant_scope ON inbox USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON ledger;
CREATE POLICY tenant_scope ON ledger USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON audit;
CREATE POLICY tenant_scope ON audit USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_decisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON review_decisions;
CREATE POLICY tenant_scope ON review_decisions USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON documents;
CREATE POLICY tenant_scope ON documents USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE execution_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON execution_jobs;
CREATE POLICY tenant_scope ON execution_jobs USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE worker_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_health FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON worker_health;
CREATE POLICY tenant_scope ON worker_health USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON workflow_runs;
CREATE POLICY tenant_scope ON workflow_runs USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON workflow_events;
CREATE POLICY tenant_scope ON workflow_events USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
ALTER TABLE extension_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE extension_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_scope ON extension_requests;
CREATE POLICY tenant_scope ON extension_requests USING (tenant_id=finance_tenant()) WITH CHECK (tenant_id=finance_tenant());
INSERT INTO schema_migrations VALUES(1, 'postgres-v1') ON CONFLICT DO NOTHING;
