# SME Finance Copilot · Topic E

> **Reviewers start here:** [submission index](docs/submission/README.md) maps every
> submission-checklist item and scoring criterion to documents, code and evidence:
> [technical documentation](docs/submission/TECHNICAL_DOCUMENTATION.md),
> [security self-assessment](docs/submission/SECURITY_SELF_ASSESSMENT.md),
> [sandbox operation logs](docs/submission/EXECUTION_EVIDENCE.md).

A persistent local financial workspace: source import and review → observed facts
and allocations → F0/F1 forecasts → OR-Tools plan → independent validation → exact
owner approval → separate execution worker → independent sandbox → reconciliation.
**DATA: SYNTHETIC · EXECUTION: SANDBOX · MODEL: MOCK by default.**

Version **0.3.0** has six English sections: Home, Money, Plans, Documents, Activity
and Settings, with Copilot as a context panel. The previous ten-section cabinet
remains at `/legacy`. Chinese text and CNY are supported. Financial values come
from backend calculations, not frontend fixtures or localStorage.

Read [CLAUDE.md](CLAUDE.md) first for navigation and machine-specific instructions.
The [current Russian overview](docs/CURRENT_STATE_RU.md) records the v0.3 changes,
verification scope and remaining work.

The agent's current data/tool coverage and approval boundaries are documented in
[AGENT_CAPABILITIES.md](docs/AGENT_CAPABILITIES.md). It can page through authorized
records and full details, inspect existing plans and prepare a selected action.
Human approvals and execution checks remain separate server controls.

An opt-in Strata adapter connects to the owner's existing self-hosted model through
an authenticated SSH bridge. Setup: [Strata runbook](docs/runbooks/strata.md).
Measured scenarios and observed answer errors: [Strata results](docs/STRATA_RESULTS_RU.md).
The default remains MOCK; financial tool success is not proof that model prose is correct.

The detailed Russian [technical report](docs/TECHNICAL_REPORT_RU.md) preserves
the v0.2 architecture and measurements, with a v0.3 addendum. Its older UI, Git,
strategy and runtime descriptions are historical; use the current overview above.

## v0.3 owner cabinet (14 Oct 2026)

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
Windows OR-Tools wheels). The setup commands below are for a **new demo workspace**.
On this machine the environment already exists: follow CLAUDE.md and resume the
intended workspace. The owner's `.runtime/pg-workspace` must not be seeded or reset.
From this project directory:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.lock
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
switch but cannot approve payments. The new cabinet exchanges the token for an
8-hour server session in an HttpOnly, SameSite=Strict cookie; reload preserves a
valid session and logout revokes it. Bearer authentication remains for scripts and
the legacy cabinet. Never publish `.runtime`, DSNs, tokens or private world files.

On Linux or macOS the same steps are:

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock
python -m scripts.task setup && python -m scripts.task migrate && python -m scripts.task seed-demo
python -m scripts.serve --port 8080
```

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

The original golden fixture computes 91,000 CNY gross / 90,000 net financing
(1,000 upfront fee, no repayment fee since the 18 Oct cost-cap fix), 91,000 repayment,
29,000 final cash and a 20,000 minimum. The independent evaluator
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
`.runtime/wheelhouse` exists. Current cabinet browser evidence is
`artifacts/v03/browser-v03.json`; `artifacts/browser-smoke.json` describes the older
cabinet. Recorded browser evidence counts only while its web hashes match.
`make e2e` checks recorded evidence and does not launch a new browser.

Release full regression: **177 PASSED / 4 SKIPPED** (PostgreSQL unavailable in that
shell), original acceptance **96 PASSED / 4 NOT_RUN**. The 14 Oct Codex refresh
reran the product E2E: **21/21 PASSED**. Focused v0.3 tests: **11 PASSED / 1 FAILED**
(Windows temporary database cleanup); an isolated rerun passed. The failure is
retained, not declared fixed. See [current status](docs/IMPLEMENTATION_STATUS.md).

[Actual status](docs/IMPLEMENTATION_STATUS.md) · [I/T/W matrix](docs/ACCEPTANCE_MATRIX.md)
· [v0.3 release regression](artifacts/v03/regression-v03.json) · [results](docs/RESULTS.md)
· [v0.3 plan](docs/V03_PLAN.md) · [continuation](docs/CONTINUATION.md).
Source checklists and R1–R3 retain their handoff statuses. The owner-approved
AGENTS.md orientation header was re-hashed in HANDOFF_INVENTORY.json on 14 Oct.
Original README: docs/HANDOFF_README.original.md.

## Scope still open

Full acceptance is **PARTIAL**. Actual FastAPI/Pydantic, OR-Tools, LangGraph,
PostgreSQL RLS, persistent worker and document retrieval exist. Guarded local
Ollama inference has run on synthetic tasks; tool use and financial prose still
have measured failures. The current priority is the owner path; 14B is a temporary
integration model. LIVE quality work waits for the target model (DEFERRED_MODEL).
The historical expanded 14B evaluation is recorded in
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
