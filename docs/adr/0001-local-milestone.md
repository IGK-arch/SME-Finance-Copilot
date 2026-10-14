# ADR 0001 — reproducible local financial milestone

Accepted for the synthetic single-company milestone, 2026-10-12.

The handoff proposes Python/FastAPI/Pydantic/PostgreSQL/OR-Tools/LangGraph/React.
Inspection found Python 3.11.9 and no installed application dependencies. Network
installation is unnecessary for the first executable milestone. Use Python 3.11
standard library, SQLite (foreign keys, CHECKs, BEGIN IMMEDIATE), typed Python,
local HTTP/JSON and plain JavaScript. The dependency lock contains no third-party
runtime packages. SQLite serializes financial writers; this is not PostgreSQL RLS
or database-role isolation. HTTP servers bind loopback only and are development
servers, not production deployments.

Use UUID4 logical IDs, canonical UTF-8 JSON (sorted keys, compact separators,
no NaN), SHA-256 approval hashes, signed int64 minor units plus explicit CNY,
Decimal ROUND_HALF_UP for rates. UTC aware timestamps and explicit Shanghai
business timezone. No cross-currency aggregation or implicit FX.

Use exact enumeration of a documented finite product/amount grid with a search
budget; OPTIMAL means all candidates in that grid were examined. UNKNOWN means
the budget exhausted without a feasible incumbent; FEASIBLE means an incumbent
exists without a proof. Independently validate with a second arithmetic algorithm.
This is not CP-SAT and must not be reported as W18 complete.

Sandbox has a separate process/database and separate read/execute/admin tokens.
Agent tools receive observation data only. Hidden schedules and evaluator access
are available only to the local synthetic test runner. Local machine administrators
can read both files; this is not OS/container isolation and T097 remains limited
until a separately permissioned deployment exists.

The mock workflow is bounded and checkpointed in the finance database; it is not
LangGraph. Live inference fails UNSUPPORTED_MODEL_PROVIDER. No fallback egress.
Preserve supplied JSON Schema files; add runtime contracts without redefining them.

Move to the proposed frameworks before production or larger workloads. Those
changes require fresh migrations, role isolation tests, CP-SAT comparison and real
model evaluation, not renaming this prototype's implementations.
