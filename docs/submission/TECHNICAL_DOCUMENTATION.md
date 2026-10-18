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
   operation is found. No second payment is possible.

State machine: `RESERVED → SUBMITTED → SETTLED | FAILED`, with
`SUBMITTED ↔ UNKNOWN` on lost responses.

### 3.7 Reconciliation and case closure

`refresh` observes the sandbox, records each new movement once (inbox
deduplication), allocates it to the obligation and writes a balanced ledger
pair. Local cash is compared with bank cash; a discrepancy stops new sends and
only the OWNER can resume after a matching reconciliation. The financial case is
marked RESOLVED only when the plan is complete and the reconciliation matches.

### 3.8 Business health analysis

`compute.analysis(snapshot)` derives descriptive ratios from observed facts only:
days until the first gap, liquidity buffer (lowest projected cash − reserve),
cash versus payables due in 30 days (basis points), net working position,
ageing buckets (overdue, 0–30, 31–60, 61–90, 90+ days) for receivables and
payables, top-3 customer and payee concentration, and settled inflow/outflow over
the last 30 days. Profit and loss is explicitly `INSUFFICIENT_DATA` because a
bank statement is not an income statement.

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
  actor role and a verification script.
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
| Unit + integration regression | `python -m scripts.test` | 274 run, 0 failed, 7 skipped (PostgreSQL, Windows-only) on Linux, 18 Oct |
| Static checks | `python -m scripts.check` | ruff, mypy, format, JS syntax PASSED |
| Product path E2E (server + worker + sandbox) | `python -m scripts.e2e_v03` | 21/21 checks PASSED |
| Golden scenario with lost response | `python -m scripts.demo --lost-response` | 5/5 actions settled, reconciled, 0 discrepancy |
| Acceptance matrix | `python -m scripts.report` | Last recorded: T001–T100 96 PASSED / 4 NOT_RUN |
| CI | GitHub Actions `.github/workflows/ci.yml` | check, tests, demo, benchmark, report |

Sandbox operation logs: [EXECUTION_EVIDENCE.md](EXECUTION_EVIDENCE.md).

## 8. Limitations

Synthetic data and DEMO financing terms only; no real bank or lender. Scenarios
are uncalibrated. Live-model prose still has measured errors. Production
isolation, secret vault, TLS/SSO and external anchoring of the audit chain are not
implemented. See [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).
