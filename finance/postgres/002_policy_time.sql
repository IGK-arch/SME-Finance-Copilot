ALTER TABLE policies ADD COLUMN IF NOT EXISTS observed_at TEXT;
CREATE INDEX IF NOT EXISTS policy_cutoff ON policies(tenant_id,observed_at);
INSERT INTO schema_migrations VALUES(2, 'postgres-policy-time-v2') ON CONFLICT DO NOTHING;
