# Architecture and trust boundaries

The ten-route browser calls FastAPI through authenticated, bounded JSON requests.
Pydantic validates task/policy contracts; domain contracts validate money/actions.
Membership selects tenant and role. Browser financial data comes from persistent
repositories; localStorage is not used for financial state or tokens.

`store.py` implements SQLite; `postgres.py` implements the same repository protocol
with psycopg. PostgreSQL tenant logins have FORCE RLS using session_user, no schema
mutation or cross-tenant access; immutable source/ledger tables also deny mutation.
Explicit admin provisioning is outside HTTP/model tools. See ADR 0003. Serialized
reservation transactions use BEGIN IMMEDIATE or a PostgreSQL advisory lock.

`ingestion.py` builds immutable fact/source snapshots and allocations. `workspace.py`
adds quarantine decisions, versioned documents, lexical permission-aware retrieval,
settings and reports. `parser.py` is a bounded text-PDF subprocess. `compute.py`
calculates deterministic metrics and scenarios; `planner.py` compiles constraints
into actual OR-Tools CP-SAT. `validation.py` independently checks the plan. The old
finite enumeration remains a test oracle and deterministic benchmark baseline.

`workflows.py` is actual LangGraph with persistent per-tenant SQLite checkpoints,
run leases, typed registry tools, clarification interrupts, exact-approval pause,
worker submission, observation, reconciliation and replan. `gateway.py` supports
explicit mock or opt-in local Ollama with context/step/token/time budgets. Real
usage/cost quality is never inferred from mock. Context exposes bounded factual
results; complete tool events are stored for evidence. Model tools have no SQL,
shell, secret, policy-write, approval or payment capability.

`execution.py` checks current membership, exact canonical hash, beneficiary, policy,
source versions, dependencies and fresh observed funds. A transaction reserves and
records action/outbox/job. Separate `worker.py` leases jobs, rechecks authority and
uses stable-key lookup before any resend. UNKNOWN keeps its reserve. Reconciliation
inserts one inbox event, fact, allocation and balanced ledger pair. `hooks.py`
accepts optional HMAC-signed wakeups and reads actual external status; a webhook
body is not authority for balance, approval or settlement.

`sandbox/server.py` owns a separate world database and math, with observe/execute/
admin capabilities. Only observed balances/holds/events are visible through tools.
`scripts/runtime.py` is a synthetic admin harness, not model context. It seeds the
world once, persists capabilities, reopens state and controls synthetic time. The
independent evaluator reconstructs cash from movements, checks reserve, debt,
payables and deadlines. `contingency.py` accepts observed counterparty decisions;
a requested extension alone changes no obligation.

Original handoff files remain outside model retrieval. Egress is limited to local
sandbox/Ollama/PostgreSQL and no paid service is configured. This development
process separation is not OS access control; private truth isolation is explicitly
incomplete. See SECURITY.md and KNOWN_LIMITATIONS.md for remaining boundaries.
