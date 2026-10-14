# Security self-assessment — synthetic local workspace

Assets: observed sources/facts, exact approvals, membership/DB tokens, command keys,
reserves, operational ledger, private simulator future and audit evidence.

Implemented and locally tested: typed integer money/time, source/version hashes,
quarantine review, current role authorization, API/evidence/tool/cache scoping,
PostgreSQL FORCE RLS and restricted tenant logins, immutable financial/source rows,
exact canonical approvals with expiry/revocation, beneficiary version checks,
current funds/preconditions, atomic reserve/outbox/job, durable worker leases,
stable-key status-before-retry, inbox deduplication, signed sandbox wakeup webhook,
terminal-state protection, kill switch, safe partial execution and independent
world-ledger/deadline evaluation. PDF injection cannot add a payment/policy tool.

Trust boundary: model receives approved tools and bounded observed context; no
shell, SQL, execution secret, approve/send tool or simulator admin route. Live
Ollama is opt-in loopback only with no proxy/redirect or silent mock fallback.
Mock injection tests are not empirical evidence of real-model robustness.

PostgreSQL API/worker use a scoped tenant login, not the migration admin. They
currently share that role; a worker-only grant set is not implemented. The RLS
scope derives from session_user, not a caller-settable tenant field. Host/OS
administrators remain trusted. LangGraph and simulator SQLite files are not in
separately permissioned containers. T097 and full filesystem/process isolation
remain open. Parser has resource/time bounds but no OS memory sandbox.

Credentials live in ignored local files, not a production secret vault. HTTP binds
127.0.0.1; no production TLS/SSO/external hosting. Hash-linked audit is not proof
against an administrator replacing the database. No generic unsafe reserve-clear
or external-operation cancellation endpoint exists. Back up both observed and
private world state together before maintenance; never publish secrets/private truth.

Evidence: artifacts/test-results.json, postgres-tests.json, gateway-contract-tests.json,
quality-results.json, golden-latest.json and browser evidence. These checks assert
local observed behavior only; no legal compliance, bank certification, zero-risk
claim or production authorization follows. Real payments/data/notifications and
paid services require explicit user approval and remain disabled.
