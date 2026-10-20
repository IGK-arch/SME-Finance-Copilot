# Developer notes (previous README)

> Kept for continuity of the development history. Reviewers should start from the
> [README](../README.md). Counters and dates below are historical; links are relative to the repository root.


> **Reviewers start here:** [submission index](submission/README.md) maps every
> submission-checklist item and scoring criterion to documents, code and evidence:
> [technical documentation](submission/TECHNICAL_DOCUMENTATION.md),
> [security self-assessment](submission/SECURITY_SELF_ASSESSMENT.md),
> [sandbox operation logs](submission/EXECUTION_EVIDENCE.md).
>
> **On-chain proof:** the audit trail's chain head is anchored on a public testnet;
> see `python -m scripts.anchor_audit` and [the submission index](submission/README.md#challenge-bonus-on-chain-exploration-05).

A persistent local financial workspace: source import and review → observed facts
and allocations → F0/F1 forecasts → OR-Tools plan → independent validation → exact
owner approval → separate execution worker → independent sandbox → reconciliation.
**DATA: SYNTHETIC · EXECUTION: SANDBOX · MODEL: MOCK by default.**

Version **0.3.0** has six English sections: Home, Money, Plans, Documents, Activity
and Settings, with Copilot as a context panel. The previous ten-section cabinet
is available at `/legacy` only with explicit development opt-in (disabled by default).
Chinese text and CNY are supported. Financial values come
from backend calculations, not frontend fixtures or localStorage.

Reviewers can skip [CLAUDE.md](../CLAUDE.md) and [AGENTS.md](../AGENTS.md): they hold navigation
and machine-specific notes for coding assistants on the owner's development machine.
The [current Russian overview](CURRENT_STATE_RU.md) records the v0.3 changes,
verification scope and remaining work.

The agent's current data/tool coverage and approval boundaries are documented in
[AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md). It can page through authorized
records and full details, inspect existing plans and prepare a selected action.
Human approvals and execution checks remain separate server controls.

An opt-in Strata adapter connects to the owner's existing self-hosted model through
an authenticated SSH bridge. Setup: [Strata runbook](runbooks/strata.md).
Measured scenarios and observed answer errors: [Strata results](STRATA_RESULTS_RU.md).
The default remains MOCK; financial tool success is not proof that model prose is correct.

The detailed Russian [technical report](TECHNICAL_REPORT_RU.md) preserves
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
is disabled by default; see the explicit opt-in below. See [the v0.3 plan](V03_PLAN.md),
[V03 acceptance](ACCEPTANCE_MATRIX_V03.md) and [ADR 0005](adr/0005-v03-owner-main-path.md).
Version 0.3.0 (14 Oct 2026) adds a UX pass: loading/error states, a bottom tab bar on phones and
tablets, charts sized to the screen and the owner's logo; layout checked at 390/768/1366/1440 px.

```powershell
.venv\Scripts\python.exe -m scripts.e2e_v03     # product path over server + worker + sandbox
.venv\Scripts\python.exe -m scripts.report_v03  # regenerate docs/ACCEPTANCE_MATRIX_V03.md
```

## Start or resume

Use CPython 3.11+ (Windows CPython 3.11.9 was tested; MSYS Python cannot use these
Windows OR-Tools wheels). The setup commands below create a **new demo workspace** with synthetic data.
On the owner's development machine the workspace already exists and must not be
reseeded (see CLAUDE.md). From the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.lock
.venv\Scripts\python.exe -m scripts.task setup
.venv\Scripts\python.exe -m scripts.task migrate
.venv\Scripts\python.exe -m scripts.task seed-demo
.venv\Scripts\python.exe -m scripts.serve --port 8080
```

If pip reports `No matching distribution found for numpy==2.4.6 (from versions: none)`,
pip is reading a mirror (`pip.ini`/`PIP_INDEX_URL`) without the pinned wheels; the
`--index-url https://pypi.org/simple` above overrides it (`pip config list -v` shows the
source). Do not run `seed-demo` until the install finished without errors.

Security controls you will meet in the cabinet:

- Sign in at `http://localhost:8080` with the `OWNER` value from
  `.runtime/workspace/local-login.secret.json`. Approving a payment asks for that token
  again (step-up); 5 wrong confirmations in 15 minutes lock approvals for that user.
- Only OWNER can resume sends after a stop, and only when cash reconciles.
- Settings → *Data & integrity* shows where model prompts go and the audit-chain status.
  Read-only check: `.venv\Scripts\python.exe -m scripts.verify_audit`.
- The pre-v0.3 cabinet (`/legacy`) is off; `SME_ENABLE_LEGACY=1` re-enables it for
  development only (it approves without step-up).
- `?demo=1` in the URL shows sandbox fault-injection controls in the approval dialog.
- For a submission copy without infrastructure details (GPU host IP, SSH ports):
  `.venv\Scripts\python.exe -m scripts.submission_copy --out ..\SME-Finance-Copilot-submission`.

The default `.runtime/workspace` uses SQLite for an easy local start. Reuse the
same directory to preserve data. Startup refuses to silently reseed an incomplete
workspace. Ctrl+C stops API, worker and simulator; files remain. No reset/delete
command is run automatically. Do not run two runtimes on the same workspace.

To publish the cabinet on your own domain (HTTPS, VPS), follow
[the deploy runbook](runbooks/deploy.md).

For the real PostgreSQL backend, follow [the runbook](runbooks/postgres.md).
Once the cluster and its workspace are provisioned as the runbook describes:

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

Latest full run (19 Oct 2026, Windows, CPython 3.11.9): regression **366 PASSED / 4 SKIPPED**
(the four PostgreSQL integration tests; no test database was configured), HTTP product E2E
**23/23 PASSED** (MOCK model, sandbox), static checks **9/9 PASSED**, original acceptance
T001–T100 **95 PASSED / 5 NOT_RUN** (T023, T031, T032, T094, T097; reasons in
[the report](BUSINESS_HEALTH_MIXED_FIX_20261019_RU.md)). Raw results:
`artifacts/health-challenge-fix-20261019/`. Counters in older documents are historical.

[Actual status](IMPLEMENTATION_STATUS.md) · [I/T/W matrix](ACCEPTANCE_MATRIX.md)
· [v0.3 release regression](../artifacts/v03/regression-v03.json) · [results](RESULTS.md)
· [v0.3 plan](V03_PLAN.md) · [continuation](CONTINUATION.md).
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
[platform results](AGENT_PLATFORM_RESULTS.md), with
[20 scenario definitions](LOCAL_14B_SCENARIOS.md) and
[completed 14B results](LOCAL_14B_RESULTS.md): 8/20 strict passes, with narrative
omissions, timeouts and RAM interruptions recorded separately. See the
[model card](model_cards/local-gateway.md) for revision and resource limits.
OS isolation of private simulator files, OCR/OFD/XML, production identity/secrets,
broader synthetic benchmark diversity and some event/notification features remain.
No paid service, real payment, bank integration or real-data egress is enabled.
See [limitations](KNOWN_LIMITATIONS.md), [security](SECURITY.md),
[architecture](architecture/README.md) and [ADRs](adr/0003-postgresql.md).
