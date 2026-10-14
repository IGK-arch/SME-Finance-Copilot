# SME Finance Copilot · Topic E

A persistent local financial workspace: source import and review → observed facts
and allocations → F0/F1 forecasts → OR-Tools plan → independent validation → exact
owner approval → separate execution worker → independent sandbox → reconciliation.
**DATA: SYNTHETIC · EXECUTION: SANDBOX · MODEL: MOCK by default.**

The ten linked English sections are Overview, Imports & Data Quality,
Receivables/Payables, Cash Flow, Financing, Plans, Copilot, Approvals & Operations,
Evidence & Reports and Settings. Chinese text and CNY are supported. Financial
values come from backend calculations, not frontend fixtures or localStorage.

The agent's current data/tool coverage and approval boundaries are documented in
[AGENT_CAPABILITIES.md](docs/AGENT_CAPABILITIES.md). It can page through authorized
records and full details, inspect existing plans and prepare a selected action.
Human approvals and execution checks remain separate server controls.

The detailed Russian [technical report](docs/TECHNICAL_REPORT_RU.md) covers the
implemented architecture, data model, workflow/payment transitions, tools,
operational controls, measured results and remaining limitations.

## v0.3 owner cabinet (13 Oct 2026)

The cabinet is reorganised around one task: problem → cause → options → choice → exact
approval → execution → reconciled result. Sections: **Home** (one main problem, metrics,
forecast with the reserve line, tasks), **Plans** (the financial task: why the gap exists,
validated options — executable, infeasible with reasons, conditional — and the selected plan),
an **exact-approval dialog** per action, **Activity** (observed operation timeline), **Money**
(scenarios and a what-if for one receivable), **Documents** (CSV/XLSX import with column mapping,
preview and review) and **Settings**. Copilot is a context panel over the real workflow graph.
Sign-in creates a server session cookie, so a reload keeps you signed in. The previous cabinet
remains at `/legacy`. See [the v0.3 plan](docs/V03_PLAN.md),
[V03 acceptance](docs/ACCEPTANCE_MATRIX_V03.md) and [ADR 0005](docs/adr/0005-v03-owner-main-path.md).
Version 0.3.0 (14 Oct 2026) adds a UX pass: loading/error states, a bottom tab bar on phones and
tablets, charts sized to the screen and the owner's logo; layout checked at 390/768/1366/1440 px.

```powershell
.venv\Scripts\python.exe -m scripts.e2e_v03     # product path over server + worker + sandbox
.venv\Scripts\python.exe -m scripts.report_v03  # regenerate docs/ACCEPTANCE_MATRIX_V03.md
```

## Start or resume

Use CPython 3.11+ (Windows CPython 3.11.9 was tested; MSYS Python cannot use these
Windows OR-Tools wheels). From this project directory:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m scripts.task setup
.venv\Scripts\python.exe -m scripts.task migrate
.venv\Scripts\python.exe -m scripts.task seed-demo
.venv\Scripts\python.exe -m scripts.serve --port 8080
```

The default `.runtime/workspace` uses SQLite for an easy local start. Reuse the
same directory to preserve data. Startup refuses to silently reseed an incomplete
workspace. Ctrl+C stops API, worker and simulator; files remain. No reset/delete
command is run automatically. Do not run two runtimes on the same workspace.

For the real PostgreSQL backend, follow [the runbook](docs/runbooks/postgres.md).
The current installed cluster and `.runtime/pg-workspace` are already provisioned:

```powershell
.venv\Scripts\python.exe -m scripts.postgres status
.venv\Scripts\python.exe -m scripts.serve --port 8080 --directory .runtime/pg-workspace
```

Open [the local cabinet](http://127.0.0.1:8080). Copy the `OWNER` value from that
workspace's `local-login.secret.json` into **Membership token**. The terminal prints
its full path. ACCOUNTANT imports/proposes, AUDITOR reads, ADMIN controls the kill
switch but cannot approve payments. Tokens remain only in page memory; reload
requires sign-in. Never publish `.runtime`, DSNs, tokens or private world files.

## Use the workflow

Import the documented CSV schema; correct quarantined rows with a review reason.
Inspect actual cash separately from expected receipts. Compare financing terms,
F0/F1 scenarios and isolated what-if plans. Start Copilot in explicit MOCK mode to
exercise the real graph with a deterministic tool fixture. Advance the demo clock
to a contract date, resume, inspect the exact amount/recipient and approve it.
The worker submits; advance/refresh observes settlement. UNKNOWN retains reserves
and recovers using the original key. A material change requires a refreshed command
and a new approval. A supplier extension changes facts only after its separate
sandbox counterparty confirmation. No real counterparty is contacted.

The original golden fixture computes 91,000 CNY gross / 90,000 net financing,
92,000 repayment, 28,000 final cash and a 20,000 minimum. The independent evaluator
also checks remaining debt/payables and missed deadlines. These are synthetic
fixture outcomes, not real lender terms or business/model-quality metrics.

## Verify

```powershell
.venv\Scripts\python.exe -m scripts.test
.venv\Scripts\python.exe -m scripts.check
.venv\Scripts\python.exe -m scripts.demo --lost-response
.venv\Scripts\python.exe -m scripts.benchmark
.venv\Scripts\python.exe -m scripts.rehearse
.venv\Scripts\python.exe -m scripts.licenses
.venv\Scripts\python.exe -m scripts.doctor --live
.venv\Scripts\python.exe -m scripts.report
```

Set `SME_POSTGRES_TEST_CONFIG=.runtime/postgres/cluster.secret.json` in PowerShell
before the suite to include actual PostgreSQL integration; otherwise those tests
are SKIPPED. Tests need loopback networking. Rehearsal uses pinned local wheels if
`.runtime/wheelhouse` exists. Browser E2E was run through Codex's browser tools;
`artifacts/browser-smoke.json` identifies its scope and screenshot/source hashes.
`make e2e` checks that recorded evidence and does not pretend to launch a new browser.

[Actual status](docs/IMPLEMENTATION_STATUS.md) · [I/T/W matrix](docs/ACCEPTANCE_MATRIX.md)
· [test evidence](artifacts/test-results.json) · [results](docs/RESULTS.md)
· [plan](docs/IMPLEMENTATION_PLAN.md) · [continuation](docs/CONTINUATION.md).
The source checklists, AGENTS.md and R1–R3 remain unchanged; their handoff statuses
are not rewritten to fabricate progress. Original README: docs/HANDOFF_README.original.md.

## Scope still open

Full acceptance is **PARTIAL**. Actual FastAPI/Pydantic, OR-Tools, LangGraph,
PostgreSQL RLS, persistent worker and document retrieval exist. Guarded local
Ollama inference has run on synthetic tasks; tool use and financial prose still
have measured failures. The expanded 14B evaluation is recorded in
[platform results](docs/AGENT_PLATFORM_RESULTS.md), with
[20 scenario definitions](docs/LOCAL_14B_SCENARIOS.md) and
[completed 14B results](docs/LOCAL_14B_RESULTS.md): 8/20 strict passes, with narrative
omissions, timeouts and RAM interruptions recorded separately. See the
[model card](docs/model_cards/local-gateway.md) for revision and resource limits.
OS isolation of private simulator files, OCR/OFD/XML, production identity/secrets,
broader synthetic benchmark diversity and some event/notification features remain.
No paid service, real payment, bank integration or real-data egress is enabled.
See [limitations](docs/KNOWN_LIMITATIONS.md), [security](docs/SECURITY.md),
[architecture](docs/architecture/README.md) and [ADRs](docs/adr/0003-postgresql.md).
