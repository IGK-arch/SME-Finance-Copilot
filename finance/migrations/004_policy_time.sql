ALTER TABLE policies ADD COLUMN observed_at TEXT;
CREATE INDEX IF NOT EXISTS policy_cutoff ON policies(tenant_id,observed_at);
