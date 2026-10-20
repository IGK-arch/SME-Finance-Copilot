# Technical documentation

SME Finance Copilot · International Track, Topic E · version 0.3.0.

A finance copilot for a small-business owner. It finds the coming cash gap,
explains why it happens, compares ways to cover it (including financing), lets
the owner approve exact actions, executes them against a simulated bank and
proves the result through reconciliation.

**Mode of this submission:** synthetic data, sandbox bank, deterministic MOCK model
by default; an optional self-hosted LLM can be switched on (see §6).

## 1. Problem and scope

A typical SME owner sees cash only in the bank app. Payroll, rent and supplier
bills arrive before the customer pays, and the owner finds out when a payment
bounces. Our copilot covers the three capabilities in the Topic E statement:

| Topic E capability | What the product does | Where |
|---|---|---|
| Financing-option matching | Screens DEMO financing products for eligibility (PASS/FAIL/UNKNOWN), prices them exactly (net proceeds, fees, interest, annualised cost) and picks the cheapest one that closes the gap under a cost cap | `finance/compute.py` `financing`, `finance/planner.py` |
| Cash-flow management and alerts | Forecast on contract dates plus delay scenarios, reserve line, what-if for one receivable, alerts: cash gap, stress gap, overdue payables/receivables, offer or approval expiring, unknown payment, reconciliation mismatch, sends stopped | `finance/compute.py` `forecast`, `finance/cases.py` `alerts` |
| Business financial analysis | Confirmed cash, receivables, payables, overdue, reserve; business health: days until cash gap, liquidity buffer, cash vs bills due in 30 days, net working position, ageing buckets, customer and payee concentration, settled inflow/outflow | `finance/compute.py` `metrics`, `analysis` |
| Execution (beyond advice) | Exact owner approval, worker, sandbox bank, reconciliation, recovery from lost responses | `finance/execution.py`, `finance/worker.py`, `sandbox/` |

## 2. System architecture

```
 Browser cabinet (web/)          Copilot panel
 Home · Money · Plans ·    ──►   LangGraph agent  ──►  ModelGateway
 Documents · Activity ·          (typed tools)          mock | Ollama | llama.cpp | Strata
 Settings                              │
        │  HttpOnly session            ▼
        ▼                        Tool registry (read / compute / propose only)
 FastAPI (finance/asgi.py, api.py)     │
        │                              ▼
        ├─► Ingestion + mapping ─► facts (versioned) ─► snapshot
        ├─► Compute: metrics, forecast, scenarios, financing, analysis
        ├─► Planner: OR-Tools CP-SAT  ─►  independent Validator
        ├─► Execution: command → exact approval → reserve + outbox + job (one transaction)
        │                                                   │
        │                                   Worker process (lease, re-check, stable key)
        │                                                   ▼
        └─► Reconciliation  ◄──── observe ────  Sandbox bank (separate process + DB)
 Storage: SQLite (default) or PostgreSQL with FORCE row-level security
```

| Component | File(s) | Responsibility |
|---|---|---|
| HTTP API | `finance/asgi.py`, `finance/api.py` | FastAPI, session cookie, CSP, role checks |
| Domain | `finance/domain.py` | Integer minor units, UTC time, canonical SHA-256 digest, typed errors |
| Storage | `finance/store.py`, `finance/postgres.py` | Same repository protocol on SQLite and PostgreSQL, append-only objects, hash-chained audit |
| Ingestion | `finance/ingestion.py`, `finance/mapping.py`, `finance/parser.py` | CSV/XLSX import with column mapping, quarantine, versioned facts, bounded PDF text parsing |
| Compute | `finance/compute.py` | Metrics, forecast F0/F1, financing quotes, business analysis, oracle optimiser |
| Planner | `finance/planner.py` | OR-Tools CP-SAT model |
| Validator | `finance/validation.py` | Independent re-check of every plan |
| Owner read models | `finance/cases.py` | Home, financial case, options, review, activity, alerts, what-if |
| Agent | `finance/workflows.py`, `finance/agents.py`, `finance/agent_data.py`, `finance/gateway.py` | LangGraph graph, typed tools, model providers |
| Execution | `finance/execution.py`, `finance/digest_check.py`, `finance/worker.py` | Command compilation, approval, reservation, queue, delivery |
| Sandbox bank | `sandbox/world.py`, `sandbox/server.py` | Separate process and database; settles, delays and loses responses on request |
| UI | `web/` | Vanilla JS, no third-party scripts |

## 3. Core algorithms

### 3.1 Money and time model

All money is integer minor units (fen), never floats. Every fact has a version,
an observed time and an effective time, so a forecast can be reproduced "as of"
any moment. An invoice or expected receipt is never counted as cash: only a
settled bank movement changes confirmed cash.

### 3.2 Cash-flow forecast

`forecast(snapshot)` builds a calendar trajectory from open obligations for each
scenario: `f0` (contract dates), `delay_5`, and `delay_25` (stress). At equal
timestamps outflows are applied before inflows, so a same-day receipt cannot hide
an intraday shortfall. Output per scenario: minimum balance, first date below the
reserve, final balance and net need (`reserve − minimum`). The what-if tool can
delay or partially pay a single receivable (0–365 days, 0–10000 basis points)
without changing the stored facts.

### 3.3 Financing matching and pricing

Each DEMO product has versioned terms: amount range and grid step, disbursement
date, repayment date, rate, upfront and repayment fees, legal form, documents and
jurisdiction. Eligibility returns PASS / FAIL / UNKNOWN; missing data is never
treated as PASS. The calculator returns principal, net proceeds, interest, fees,
total cost, repayment and annualised cost in basis points, so "we need 90,000 net"
correctly becomes "borrow 91,000 gross" when a 1,000 fee is withheld.

### 3.4 Plan optimisation (OR-Tools CP-SAT)

`planner.solve` builds a real `cp_model.CpModel`:

- candidates = no new debt + every eligible product × every grid principal;
- boolean `choose[c]` with `exactly_one(choose)`;
- for every prefix of the dated cash path and every scenario in the objective's
  scope: `balance ≥ reserve` (hard);
- annualised cost ≤ policy cap (hard);
- objective by strategy: `MIN_COST` (cost, then principal), `NO_NEW_DEBT`,
  `HIGHER_RESERVE` (minimum cost at an explicit higher cash target),
  `PRESERVE_LIQUIDITY` / stress-resilient (minimum cost that survives all DEMO
  delay scenarios).

One search worker, fixed seed, 5 s default limit. The result status is reported
honestly as OPTIMAL, FEASIBLE, INFEASIBLE or UNKNOWN; infeasible options carry a
diagnostic reason. This is a finite-grid model; it does not claim a global
optimum over arbitrary payment calendars. A brute-force oracle with the same
objective semantics is kept as a test cross-check.

The chosen plan compiles to dated actions (`DRAW_LOAN`, `PAY_OBLIGATION`,
`REPAY_LOAN`) with dependencies, recipients and the completion predicate
`SETTLED_AND_RECONCILED`.

### 3.5 Independent validation

`validation.validate_plan` never calls the solver. It recomputes the action DAG,
coverage of obligations, duplicates, amounts, dates, recipients, fees, interest,
cash deltas, debt repayment and the cash path in every scenario, and orders ties
exactly as the planner does. It runs again before every command is compiled, so a
plan that became unsafe after data changed cannot be executed.

### 3.6 Exact approval and execution

1. `command()` compiles the next action from current data: amount, recipient
   version, policy version, snapshot, dependencies, quote and a stable
   idempotency key.
2. The owner reviews it; the browser sends only the payload hash and a step-up
   re-entry of the owner token. The server recompiles and compares the hash.
3. `prepare()` in one transaction checks the approval and fresh funds, creates
   the reservation, the outbox record and the job.
4. The worker leases the job, re-checks authority and preconditions, looks up
   the status by the stable key before any resend, and only then calls the bank.
5. A lost response becomes `UNKNOWN`; the reserve stays until the original
   operation is found. Injected-loss tests observed one economic operation per
   stable key; this guarantee depends on the provider's idempotency contract.

State machine: `RESERVED → SUBMITTED → SETTLED | FAILED`, with
`SUBMITTED ↔ UNKNOWN` on lost responses.

### 3.7 Reconciliation and case closure

`refresh` observes the sandbox and records each new movement once (inbox
deduplication), including a balanced ledger pair. Before completing a Copilot
action or allocating its cash, it requires an unambiguous stable key, the known
provider reference, signed amount, counterparty and obligation reference to match
the approved command. External cash remains observable even without an allocation.

An identity mismatch records a durable tenant-scoped `settlement_issue`, stops
sends and leaves the unresolved action UNKNOWN with its reserve active. It cannot
close another bill or create the approved loan debt. Replay, provider statuses,
restart and repeated approval cannot erase the issue. A previously completed
historical action is not rolled back by a later conflicting movement.

Reconciliation v2 distinguishes `cash_matched` from `matched`; matching balances
are insufficient while a settlement issue remains. Only the OWNER can resume,
after a fresh fully matched reconciliation. The case is RESOLVED only when the
plan is complete and reconciliation matches. No automatic dispute-resolution or
force-clear endpoint exists. Old accepted inbox records are not retroactively
revalidated. See [K15 fix and evidence](../SETTLEMENT_FIX_20261019_RU.md),
[ADR 0006](../adr/0006-settlement-identity.md) and the
[versioned runtime contract](../../contracts/RUNTIME.md). This symbolic CNY
sandbox contract does not verify real bank account details.

### 3.8 Business health analysis

`compute.analysis(snapshot)` derives descriptive ratios from observed facts only:
days until the first gap, liquidity buffer (lowest projected cash − reserve),
cash versus payables due in 30 days (basis points), net working position,
ageing buckets (overdue, 0–30, 31–60, 61–90, 90+ days) for receivables and
payables, top-3 customer and payee concentration, and settled inflow/outflow over
the last 30 days. Profit and loss is explicitly `INSUFFICIENT_DATA` because a
bank statement is not an income statement.

The Money page and agent use the same calculation (`analysis-v2`). The agent's
`calculate_business_metrics` returns the typed `business-health-v1` contract;
`forecast_cashflow` includes baseline health and `what_if_cashflow` includes
explicitly scoped hypothetical health. Only forecast-derived buffer/gap change
in a what-if; observed cash, ageing and concentration stay observed facts.
Capabilities describe this coverage, saved calculations retain source/snapshot
lineage and are readable through the existing paginated record tools. The
Copilot renders a server-formatted Business health card. Calculation contracts
are now `compute-v3` / `agent-tools-v5`; old saved results are not rewritten.

Money uses integer CNY minor units, percentages use integer basis points, and
zero-denominator coverage or an absent forecast gap use explicit null statuses.
Combined top-three shares are calculated before rounding. The legacy
`supplier_concentration` field covers all payable counterparties, including
salary, rent and lenders. Settled cashflow only counts observed SETTLED events
inside the declared open-left/closed-right window; it is not profit.
Health cannot approve a payment or bypass observed-ID, role or tenant checks.
See [ADR 0007](../adr/0007-agent-business-health.md), the
[contract](../../contracts/business-health.schema.json) and the dated
[implementation and EN/ZH evaluation report](../BUSINESS_HEALTH_AGENT_20261019_RU.md).

For bounded EN/ZH health reports, `health-answer-v1` now asks the model to select
report sections and observed result/source IDs using strict JSON. The server
renders field-bound labels and values through the unchanged reference guard.
Current/saved snapshots, null versus zero, P&L versus coverage and forecast scope
cannot be relabelled by model prose. Missing reads and invalid selections still
fail closed; no new tool authority or approval path exists. This is explicitly
marked server-rendered presentation, not an evaluation of free-form financial
writing. The same selected-Qwen development suite completed **20/20 strict PASS**,
with all twenty delivered answers reviewed; p50 full-case latency was **24.135 s**.
Regression: **344 PASS / 4 PostgreSQL SKIP**; HTTP E2E **23/23 MOCK**. Independent
holdout, broader language routing and LIVE payment lifecycle were not rerun.
See [ADR 0008](../adr/0008-typed-health-answers.md) and the
[measured correction report](../BUSINESS_HEALTH_FIX_20261019_RU.md).

### 3.9 On-chain proof of the audit trail

Every audit record already stores `previous_hash` and `event_hash`, so changing
one record breaks the chain. A database administrator, however, could rewrite a
record and recompute every later hash. `finance/anchor.py` detects changes to an
anchored prefix when compared with a trusted saved transaction reference:

1. Recompute the chain locally and refuse to anchor a broken chain.
2. Build a 65-byte payload: tag `SMEAUDIT1`, a deterministic 16-byte tenant tag, the
   number of records covered (uint64) and the 32-byte chain head.
3. Sign a zero-value EIP-1559 transaction to the wallet's own address with that
   payload as data and send it to a public testnet. The chain id must be
   Ethereum Sepolia (11155111) or Base Sepolia (84532); mainnet is refused.
4. Store the transaction hash and explorer link and write an `audit.anchored`
   audit event; the Activity page shows the latest anchor.
5. `verify` reads the transaction back from the chain, recomputes the first N
   local records and checks that the head matches. Records added after the anchor
   do not invalidate it.

No business amount or document text is published. The tenant tag is pseudonymous,
derived using a public constant prefix (not a secret/random salt), and the count
and transaction metadata are public. Verification requires local records; later
unanchored records are outside this commitment. Test `tests/test_anchor.py` rewrites
history with recomputed hashes: the local check passes, the anchor check fails.

## 4. Agent design

The agent is a LangGraph `StateGraph` with persistent per-tenant checkpoints,
run leases, clarification interrupts and an approval pause. Tools are typed and
grouped into read, compute and propose tiers (see the security report). The model
receives bounded factual results; full tool events are stored as evidence. UI
result cards are rendered from tool results, not from model prose, so a wrong
sentence cannot change a number on screen. Answers must quote exact server
amounts, dates and IDs; unbound numbers are rejected and repaired once.

Languages: English and Chinese (UI data, counterparty names, agent scenarios).

## 5. Security design (summary)

Full details and the known-risk list: [SECURITY_SELF_ASSESSMENT.md](SECURITY_SELF_ASSESSMENT.md).

- The model has no approve, send, SQL, shell, secret or policy-write capability.
- One exact OWNER approval per action, bound to a payload hash, with step-up
  re-authentication, expiry and revocation.
- Freshness checks invalidate approvals when data, policy or recipients change.
- Reservations, stable idempotency keys and status-before-resend prevent double
  payment.
- Role tiers OWNER / ACCOUNTANT / AUDITOR / ADMIN with separation of duties.
- PostgreSQL row-level security for tenant isolation; hash-chained audit with
  actor role, a verification script and a public-testnet anchor of the chain head.
- Kill switch; resume only after matched reconciliation.

## 6. Models

| Mode | Use |
|---|---|
| MOCK (default) | Deterministic tool fixture; exercises the real graph for tests and demo |
| Ollama / llama.cpp | Opt-in local models, loopback only, resource-guarded |
| Strata | Opt-in self-hosted model through an authenticated SSH bridge that exposes chat only |

A failing live model is recorded as a failed run; there is no silent fallback to
MOCK. Measured multi-model and reasoning evaluations (100 EN/ZH scenarios per
model) are in `docs/MULTIMODEL_100_RESULTS_RU.md` and
`docs/REASONING_100_RESULTS_RU.md` (Russian working reports; raw data in
`artifacts/`).

## 7. Testing and evidence

| Check | Command | Latest result |
|---|---|---|
| Unit + integration regression | `python -m scripts.test` | 19 Oct, Windows: 370 run, 366 PASS, 4 PostgreSQL SKIP, 0 FAIL |
| Static checks | compileall, ruff, mypy, JS syntax, pip check | 9/9 PASS (`scripts.check`) |
| Product path E2E (server + worker + sandbox) | `python -m scripts.e2e_v03` | 23/23 checks PASSED; MOCK decisions |
| Golden scenario with lost response | `python -m scripts.demo --lost-response` | 5/5 actions settled, reconciled, 0 discrepancy |
| Acceptance from fresh test report | `python -m scripts.test` | T001–T100: 95 PASSED / 5 NOT_RUN; historical matrix not regenerated |
| Browser smoke | `python -m analysis.submission_browser_runner` | 18 route/width renders; 7 assertions PASS; not full browser E2E |
| CI | GitHub Actions `.github/workflows/ci.yml` | security scan, check, tests, demo, benchmark, report; no HTTP E2E/browser/PG job |

Sandbox operation logs: [EXECUTION_EVIDENCE.md](EXECUTION_EVIDENCE.md).

Fresh measurements, the reproduced open defect and release limitations:
[readiness review](READINESS_REVIEW_20261019.md). Historical LIVE results are not
a new test of this application commit; automatic PASS is not full prose accuracy.

## 8. Limitations

Synthetic data and DEMO financing terms only; no real bank or lender. Scenarios
are uncalibrated. Live-model prose still has measured errors. Production
isolation, secret vault and TLS/SSO are not implemented; on-chain anchoring uses a
testnet only. See [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).
