CREATE TABLE IF NOT EXISTS review_decisions(
 tenant_id TEXT NOT NULL, import_id TEXT NOT NULL, row_number INTEGER NOT NULL,
 actor TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
 corrected_source_id TEXT, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,import_id,row_number),
 FOREIGN KEY(tenant_id,import_id) REFERENCES imports,
 FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS documents(
 tenant_id TEXT NOT NULL, document_id TEXT NOT NULL, version INTEGER NOT NULL,
 source_id TEXT NOT NULL, title TEXT NOT NULL, text_content TEXT NOT NULL,
 read_roles TEXT NOT NULL, observed_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,document_id,version), FOREIGN KEY(tenant_id,source_id) REFERENCES sources);
CREATE TABLE IF NOT EXISTS execution_jobs(
 tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, actor TEXT NOT NULL,
 fault TEXT NOT NULL DEFAULT 'none', lease_owner TEXT, lease_until REAL NOT NULL DEFAULT 0,
 next_attempt REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT, finished INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,action_id), FOREIGN KEY(tenant_id,action_id) REFERENCES actions,
 FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS worker_health(
 tenant_id TEXT PRIMARY KEY REFERENCES companies, worker_id TEXT NOT NULL, heartbeat REAL NOT NULL);
CREATE TABLE IF NOT EXISTS workflow_runs(
 tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, actor TEXT NOT NULL, task TEXT NOT NULL,
 provider TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 status TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant_id,run_id), FOREIGN KEY(tenant_id,actor) REFERENCES memberships(tenant_id,user_id));
CREATE TABLE IF NOT EXISTS workflow_events(
 tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 at TEXT NOT NULL, node TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(tenant_id,run_id) REFERENCES workflow_runs);
CREATE TABLE IF NOT EXISTS extension_requests(
 tenant_id TEXT NOT NULL, request_id TEXT NOT NULL, obligation_fact_id TEXT NOT NULL,
 proposed_due_at TEXT NOT NULL, status TEXT NOT NULL, decision_source_id TEXT,
 PRIMARY KEY(tenant_id,request_id), FOREIGN KEY(tenant_id,obligation_fact_id) REFERENCES facts(tenant_id,fact_id));
