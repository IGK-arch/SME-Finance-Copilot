# Architecture and trust boundaries

The v0.3 six-page cabinet and Copilot panel call FastAPI through authenticated,
bounded JSON requests. The former ten-route cabinet remains at `/legacy`.
Pydantic validates task/policy contracts; domain contracts validate money/actions.
Membership selects tenant and role. Browser financial data comes from persistent
repositories; localStorage is not used for financial state or tokens. `/session`
exchanges membership credentials for an 8-hour HttpOnly session cookie, stored
as a hash with real-time expiry and revocation. Membership is rechecked per request.

`cases.py` projects the owner path from existing snapshots and services: financial
case, options, review, timeline, activity, alerts and per-obligation what-if. Case
events are append-only objects; resolved means completed plan plus matched
reconciliation. `mapping.py` normalizes bounded CSV/XLSX uploads with explicit
column/date/decimal choices into the existing versioned ingestion contract.

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
`objective_scope()` shares scenario/cash-floor semantics with that oracle:
HIGHER_RESERVE minimizes cost at an explicit target; PRESERVE_LIQUIDITY requires
the reserve across its scenario set (all DEMO scenarios by default).

`workflows.py` is actual LangGraph with persistent per-tenant SQLite checkpoints,
run leases, typed registry tools, clarification interrupts, exact-approval pause,
worker submission, observation, reconciliation and replan. `gateway.py` supports
explicit mock, opt-in local Ollama, or opt-in Strata through an authenticated SSH
bridge, with context/step/token/time budgets. `strata.py` translates native function
calls and preserves call IDs; `scripts/strata_bridge.py` exposes only the required
chat/status paths and gives no financial tools to the remote server. Real
usage/cost quality is never inferred from mock. Context exposes bounded factual
results; complete tool events are stored for evidence. Model tools have no SQL,
shell, secret, policy-write, approval or payment capability. `copilot.py` starts
background graph runs and projects typed cards from saved tool events; those
results remain distinct from unvalidated model narrative. UI plan/action/obligation
references have scoped checks; generic case context is not a validated case lookup.

`digest_check.py` recompiles the reviewed command and checks the browser-supplied
hash before calling approve/enqueue; each action requires OWNER confirmation.
New approvals also expire after 24 real hours. Legacy approvals without a TTL
object retain their business-clock expiry.

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
