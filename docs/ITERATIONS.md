# Iteration evidence

## S0 — inspected handoff

Read CODEX_START_HERE.md, MASTER_SPEC.md sections 0–30, clarification register,
R1/R2/R3 text sources, checklists, contracts and reference-link context. No external
research claims were promoted to current facts. No external datasets loaded.

Commands: `rg --files`, `git status --short`, `git log -5 --oneline`,
`python --version`, `python -m pip list --format=freeze`, `py -0p`.
Results: handoff only; Git commands failed because this is not a Git repository;
Python 3.11.9 available; Python launcher had no registered runtimes. No application
tests existed. S0 application test status: NOT_RUN before implementation.

Added: IMPLEMENTATION_PLAN.md, ADR 0001 and this log. AGENTS.md unchanged.

## S1–S3 — observed financial core, independent world and computation

Added finance/domain.py, store.py, migrations/001_core.sql, ingestion.py,
compute.py, validation.py, contracts.py; sandbox/world.py and server.py;
adapter.py; scripts/runtime.py and demo.py; tests/test_domain.py; golden CSV.
Typed int64 CNY, explicit rounding, immutable fact/source versions, current role
checks, tenant FKs, quarantine, partial allocations, unmatched cash, bitemporal
snapshots, DEMO F0/F1/catalog, complete debt flows, finite search and independent
validation are implemented. Original contracts remain byte-identical.

Executed: `python -m compileall -q finance sandbox`; a fresh temporary DB/migration
smoke command; `python -m scripts.demo`; `python -m unittest tests.test_domain -v`.
Results: syntax/migration passed; 50 domain tests passed in the initial domain run;
independent demo had 2,800,000 final / 2,000,000 minimum minor units, zero remaining
payables/debt, six movements and zero reconciliation discrepancy. These are DEMO
fixture outcomes, not live model/bank metrics.

The first loopback run failed WinError 10013 under the restricted execution sandbox.
Re-running the same local-only task with the reviewed loopback permission passed.
No external network, real data, bank or paid service was used.

Remaining: CSV only; no empirical calibration; merchant/factoring arithmetic helpers
are not provider execution adapters; no CP-SAT or production database roles.

## S4 — approval, durable execution and recovery

Added execution.py, agents.py and tests/test_execution.py. Exact canonical
approvals bind current snapshot/plan/amount/recipient/terms. Approval expiry/revoke,
membership changes, same-obligation reserve conflicts, funds/hold semantics,
transactional reservation/action/outbox, stable keys, attempt status, polling/inbox,
balanced append-only ledger, kill switch, partial execution and cancellation all
have actual tests. Missing approval or timeout never produces fake settlement.

Executed `python -m unittest tests.test_execution -v`: initial 41 tests passed.
Later regressions cover current remaining-plan validation, corrupted debt arithmetic,
future quality/data-version leakage, stale status caches and compute-only tools.

Remaining: no signed webhook, distributed lease scheduler, global external exactly
once guarantee, supported cancellation of sent operations or LangGraph integration.

## S5 — working HTTP/UI, bounded mock workflow and evidence

Added api.py, web/index.html/app.js/style.css, scripts/serve.py, tests/test_api.py,
runtime execution schema and English domain/security/model/data/runbook docs.
The registry has READ/COMPUTE/PROPOSE tools only. Mock intent is static and labelled;
live inference is explicitly unsupported. Caches include tenant/role/policy/data/
time versions; operation status is never served from a stale cache.

Executed: `node --check web/app.js`, actual local HTTP golden tests, browser automation
through the in-app browser. The browser performed all five approvals/sends, injected
a lost payroll response, observed UNKNOWN + an 80,000 CNY reservation, recovered
without duplicates, then finished at 28,000 CNY, zero active reserves and RECONCILED
with zero discrepancy. Desktop and 390×844 layouts visibly rendered English labels,
Chinese names and CNY. Evidence: browser-smoke.json and three screenshots. The
temporary viewport was reset. One Chromium browser is not a cross-browser audit.

## S6 — actual consolidated checks and repeatability

Added scripts/test.py, check.py, benchmark.py, report.py, rehearse.py, task.py,
Makefile, optional tool pins, CI configuration, governance tests, open register,
backlog progress and traceability. README is English; the old README is preserved.
HANDOFF_INVENTORY.json hashes 29 original files; the governance test checks every
one, including AGENTS.md and R1–R3. No Git commit/tag/publication was attempted.

Actually executed final commands:

- `python -m scripts.test` — **109 tests passed**, 61.941 seconds in this run;
  acceptance **91 PASSED / 9 NOT_RUN**, including hash-verified browser evidence.
- `python -m scripts.check` — Python syntax, JavaScript syntax, Ruff lint, mypy and
  Ruff format all PASSED. Tool versions: Ruff 0.12.0, mypy 1.12.0.
- `python -m scripts.demo --lost-response` — independent world success, same
  28,000 CNY final / 20,000 minimum; five reconciled actions, no open debt/payables.
- `python -m scripts.benchmark` — three actual paired deterministic sensitivity
  comparisons saved. B1/B2/B3 live and empirical model-quality metrics NOT_RUN.
- `python -m scripts.rehearse` — copied fresh source directory, fresh venv with no
  installed third-party packages, fresh databases, golden lost-response path PASSED.
- `python -m scripts.task seed-demo` — generated fixtures/golden.csv.
- `python -m scripts.report` — reports derive from the artifacts, not preset KPIs.

Early lint/type runs found unused imports and annotation issues; those were fixed
and final checks passed. The first rehearsal expected Windows Scripts/python.exe,
but MSYS Python creates a bin layout; detection was corrected and the rerun passed.
No failed attempt is represented as a passing original run.

Remaining NOT_RUN: T023, T031, T032 (learned/holdout pipelines), T051 (contingent
branches), T058 (PDF injection), T065 (live time/token/cost budget), T083 (signed
webhooks), T086 (LangGraph), T097 (OS/container private-truth isolation). Full scope
and production blockers: KNOWN_LIMITATIONS.md, SECURITY.md, OPEN_REGISTER.md and
BACKLOG_PROGRESS.md. Final contest deck/video, remote CI and Git release remain open.


## Full-product continuation — stages A through G (2026-10-12)

The preceding S0–S6 sections are historical. They do not describe current missing
frameworks or the current test count. CODEX_BUILD_FULL_PRODUCT.md and the pasted
follow-up request were read. Audit baseline: 109 existing tests passed before
extending the useful kernel. No original handoff or AGENTS.md was overwritten.

A — Persistence and worker. Changed scripts/runtime.py, scripts/serve.py,
finance/worker.py, finance/execution.py, finance/migrations/002_workspace.sql,
003_workflow_leases.sql and tests/test_product.py. Runtime now reopens the same
observed/world databases and credentials. A separate process leases durable jobs;
reservation/outbox/job creation shares one transaction. Executed scripts.test
--pattern test_product.py: 3 passed (stage-a-tests.json). Restart/UNKNOWN/revocation
were checked; OS isolation and worker-specific DB role remain open.

B — Reviewed data and workspace operations. Changed finance/workspace.py,
finance/store.py, finance/ingestion.py, API routes and tests/test_workspace.py.
Source corrections/discards are append-only decisions, versioned facts and audit.
Added scoped documents/settings/reports, allocation UI and F1 partial/customer
shocks in compute.py/validation.py. Executed test_workspace.py: 3 passed
(stage-b-tests.json). Browser corrected a quarantined row and searched Chinese
source text. Arbitrary CSV mapping and async import jobs remain open.

C — Actual planner. Added finance/planner.py, routed execution.make_plan/API to it,
and tests/test_planner.py. CP-SAT compiles explicit candidates/prefix constraints;
independent validator remains mandatory. Executed test_planner.py: 2 passed
(stage-c-tests.json), including 27 input/objective comparisons and timeout/debt
conditions. An initial FEASIBLE/OPTIMAL mismatch was corrected by expressing the
minimum-balance objective as the selected candidate value. Finite-grid scope only.

D — Graph/model contract. Added finance/gateway.py, finance/workflows.py and graph
API/UI. Actual LangGraph checkpoints persist typed tool events and question,
approval, observation and replan interrupts. Old read/compute/propose registry is
reused. Executed initial test_workflows.py: 4 passed (stage-d-tests.json), later 5
passed after stale-payload refresh. test_gateway.py: 3 passed offline HTTP contract,
usage/egress/failure/budget tests. Live model remains BLOCKED, never silently mock.

E — Product P1. Added finance/parser.py, finance/contingency.py, finance/hooks.py,
simulator decision observations, PDF/extension/webhook APIs, respective UI controls
and tests/test_documents.py, test_contingency.py, test_webhook.py. Text PDF injection
(1), conditional accept/decline (2) and signed real-endpoint webhook replay (1)
passed in their recorded runs. Confirmed extension supports a full no-debt 30,000
CNY outcome; requested extension alone changes nothing executable. OFD/XML/OCR,
OS parser limits and arbitrary branch graphs remain open.

F — FastAPI and workspace. Added finance/asgi.py, ten routes in web/index.html,
app.js and style.css. test_asgi.py passed. Browser used real APIs/independent sandbox:
five exact actions, one lost payroll response, backend/worker restart, reconciled
28,000 CNY ending cash, 20,000 minimum, no debt/payables. Saved workflow COMPLETE.
Additional PostgreSQL browser checks changed reserve (90,000→100,000 net need),
confirmed extension, imported/retrieved a Chinese source and corrected CSV review.
That exploratory workspace remains PAUSED, not claimed as a complete golden.
Browser found and fixed stale review-list refresh and added explicit stale approval
payload refresh. Current ten-route/390-width screenshots and hashes are saved.

G — Real PostgreSQL and operational proof. Added finance/postgres.py,
finance/postgres/*.sql, scripts/postgres.py, tests/test_postgres.py, ADR 0003 and
runbook. Downloaded the official portable PostgreSQL 18.6 archive into ignored
.runtime; no system service. Actual RLS/restricted-role, cross-tenant direct SQL/DDL,
full golden, restart/graph/worker and concurrent-reserve tests: 3 passed. Initial
assertion used the wrong evaluator field name; corrected and rerun. CPython venv
uses pinned packages; no paid services, real data or live model were used.

Final domain corrections: evaluator v2 now checks deadlines as well as balances
(sandbox/world.py, tests/test_evaluator_deadlines.py; late settled salary fails).
Historical policy selection uses server observation time (SQLite migration 004,
PostgreSQL 002, store.py/workspace.py/ingestion.py, test_policy_history.py). Two
policy-history tests passed; PostgreSQL forward migration preserves NULL legacy
times and historical queries fail explicitly rather than inventing timestamps.

Latest actual checks after these changes:

- `.venv\Scripts\python.exe -m scripts.test` with SME_POSTGRES_TEST_CONFIG:
  **136 tests PASSED**, 111.498 seconds; **96 acceptance PASSED / 4 NOT_RUN**.
- `scripts.check`: Python/JS syntax, Ruff, mypy and format all PASSED. Earlier
  unused-variable and metadata-typing errors were fixed; no failure is hidden.
- `scripts.demo --lost-response`: five SETTLED; oracle v2 success true, 28,000 CNY
  final, 20,000 minimum, zero debt/payables/discrepancy/missed deadlines.
- `scripts.benchmark`: 3 paired deterministic cases; live comparisons NOT_RUN.
- `scripts.rehearse`: fresh source + new venv + installed pinned local wheels +
  fresh databases; consult latest artifacts/rehearsal.json for completion/result.
- `scripts.task setup/migrate/seed-demo` on .runtime/commands-check succeeded;
  schema version 4; repeated seed preserved existing workspace.
- `scripts.doctor --live`: BLOCKED, no inference. `scripts.licenses`: 62 actual
  installed-distribution metadata records; unknown licenses remain UNKNOWN.
- `scripts.report` and `scripts.browser_evidence`: generate/verify actual I/T/W
  evidence; no fabricated runs, progress percentages or external CI results.

Remaining NOT_RUN: T023/T031/T032 research pipelines and T097 OS isolation.
Further product/deployment gaps and exact files are in CONTINUATION.md and the
requirement matrix. Full-product gate stays PARTIAL. No release tag without Git.

## Guarded local models on E: and resource preflight, 2026-10-12

User authorized free local models >=4B and continued work on E:, explicitly leaving
their separate Claude download alone. Claude files/processes and Windows pagefile
settings were not changed. Both Qwen2.5 7B and Granite 3.3 8B downloaded successfully;
offline manifests/blob sizes are in artifacts/local-model-resource-stop.json.
Portable Ollama plus both models occupy about 10.78 GiB on E:.

Changed implementation: scripts/resource_guard.py (Windows job and resource checks),
scripts/local_llm.py (pinned E: installation, singleton server, memory limit, local
TEMP/TMP and CUDA cache), scripts/serve.py (require guard for live startup),
finance/gateway.py (60-second keep-alive), finance/workflows.py (tool descriptions,
server-enforced snapshot prerequisites and forecast metric definitions),
scripts/live_compare.py (strict grading, interrupted-run evidence and unloading).
Tests: test_resource_guard.py, test_workflows.py, test_live_evaluation.py.
The final user-directed disk reserve adjustment changes C: floor from 12 to 4 GiB;
memory thresholds and the 6 GiB job limit are unchanged.

Report maintenance: scripts/report.py now accepts --tests to derive traceability
from an explicitly selected actual report without rewriting historical raw results.
Updated LIVE_MODEL_PLAN.md, CONTINUATION.md, IMPLEMENTATION_STATUS.md,
KNOWN_LIMITATIONS.md, model_cards/local-gateway.md, runbooks/local-llm.md and
implementation_catalog.json; regenerated RESULTS.md, ACCEPTANCE_MATRIX.md,
BACKLOG_PROGRESS.md, traceability.json and artifacts/acceptance-current.json.

Actually executed checks/evidence:

- `python -m scripts.test --output artifacts/regression-live-prerequisites.json`,
  with local PostgreSQL test config: 148 PASSED, 121.968 seconds; acceptance
  96 PASSED / 4 NOT_RUN. This preceded the C: disk-floor-only revision.
- `python -m unittest tests.test_resource_guard -v` after that revision:
  4 PASSED, 1.261 seconds, including real denied allocation and child termination.
- `python -m scripts.report --tests artifacts/regression-live-prerequisites.json`:
  generated I01-I36 / T001-T100 / W01-W36 traceability from actual records.
- `python -m scripts.check`: all five checks PASSED (Python/JS syntax, Ruff, mypy,
  format); artifacts/quality-results.json. Python commands used .venv/Scripts/python.exe.
- Qwen7 baseline: 4/10 structural cases. After prerequisite repair: 3/3 diagnostic
  cases, with narrative errors still found. Reports and manual review are linked
  in the model card. These different source revisions do not establish a winner.
- Latest startup preflight: BLOCKED before launching Ollama; about 6.8 GiB commit
  headroom, threshold 8 GiB. C: about 6.25 GiB free, E: 51.01 GiB. Exact byte values
  and timestamp: artifacts/local-model-preflight-after-user-resume.json.

Remaining in this model comparison: Granite inference, identical-current-source
full two-model comparison, narrative review, then live UI verification. A user
request to free memory is pending. Existing PostgreSQL UI remains MOCK and its
history is preserved. No new model download, live payment or paid call occurred
during the blocked preflight. Earlier completed golden evidence is unchanged.

## Completed CPU model comparison and regression, 2026-10-12

The user explicitly authorized stopping background Claude processes. The verified
Claude.exe root and its children exited; no Claude files were deleted. Available
commit recovered. The project API was stopped temporarily and later restarted
against the existing PostgreSQL workspace, without reseeding or deleting history.

Granite GPU loading failed; C: briefly reached 0.77 GiB and recovered after the
guard stopped the process tree. The exact temporary allocation source is unknown;
pagefile allocation stayed 8704 MiB and Windows settings were not changed. Preserved
evidence: live-granite8-gpu-failed.json. CPU attempts exposed a transient Windows
atomic-write sharing failure and a 3.6 GiB weight-repacking allocation. Bounded
status-write retry and disabled repacking resolved these; persistent errors still
stop the job. Current profile: CPU, mmap, batch 128, 2 GiB process-tree commit cap,
C: startup/runtime reserves 6/4 GiB. No additional model downloads occurred.

Changed implementation this stage:

- finance/gateway.py: CPU generation options, typed transport/disconnection errors,
  actual request hash, Granite-specific native tool protocol with app rules intact.
- scripts/local_llm.py and scripts/resource_guard.py: CPU environment, lower commit
  cap, disabled repacking, stronger startup disk reserve, 0.5-second monitoring,
  bounded atomic status-write retry.
- tests/test_gateway.py and tests/test_resource_guard.py: CPU options, transport
  failures, provider-specific formatting/Qwen unchanged, transient/persistent write
  failure handling. Prior financial and user changes preserved.
- docs/LIVE_MODEL_RESULTS.md, LIVE_MODEL_PLAN.md, CONTINUATION.md,
  IMPLEMENTATION_STATUS.md, KNOWN_LIMITATIONS.md, model_cards/local-gateway.md,
  runbooks/local-llm.md and implementation_catalog.json; derived RESULTS.md,
  ACCEPTANCE_MATRIX.md, BACKLOG_PROGRESS.md, traceability.json and acceptance-current.
- Raw comparison/smoke/failure reports, separate narrative reviews, protocol
  diagnosis and local-model-comparison-summary.json under artifacts/.

Actually run (Python commands use .venv/Scripts/python.exe):

- CPU smoke v3: real Granite response, 62 output tokens, 8.063 seconds.
- scripts.live_compare, first CPU run: Qwen 8/10 strict passes, median 64.063 s;
  Granite baseline 1/10 with no native tool calls. Diagnosed its installed official
  template, corrected only Granite formatting and reran all ten Granite cases:
  8/10, median 90.693 s. Qwen results reused with regression proof that its wire
  messages are unchanged. All selected cases created zero actions/approvals/jobs
  and preserved policy/world state. Narrative errors remain; full review and exact
  command/config/source hashes are in LIVE_MODEL_RESULTS.md and raw artifacts.
- Initial full scripts.test: 150 PASSED / 1 FAILED, 109.367 s. New offline test
  fixture lacked mandatory token counters; corrected and five gateway tests passed.
- Final `scripts.test --output artifacts/regression-cpu-protocol-fixed.json`, with
  SME_POSTGRES_TEST_CONFIG: **151 PASSED**, 110.739 s; **96 acceptance PASSED and
  4 NOT_RUN**. The failed earlier report is retained.
- scripts.check: five PASSED (Python/JS syntax, Ruff, mypy, formatting), exact
  commands/output in artifacts/quality-results.json.
- scripts.report --tests artifacts/regression-cpu-protocol-fixed.json: generated
  the original I01-I36/T001-T100/W01-W36 matrix from actual evidence.
- scripts.browser_evidence: PASSED hash validation of the earlier ten-route CUA
  record; this command itself does not run a browser. New LIVE UI evidence is
  recorded separately, so older observations are not relabelled as current runs.

Remaining: T023/T031/T032/T097 NOT_RUN; full product PARTIAL; live B1/B2/B3
ablations, independent narrative review, repeated/held-out model evaluation absent.
The 2 GiB commit limit does not bound all mapped physical RAM or provide OS security
isolation. Experimental Qwen selection reflects equal strict passes and the lower
observed median, not production readiness or reliable unrestricted financial prose.

Final actual browser run: restored existing PG UI with LIVE qwen2.5:7b and explicit
120/600-second budgets. New Russian cash query COMPLETE: 120,000 CNY as of 10 October,
all returned source IDs cited, one get_financial_snapshot, no plan/propose calls.
Provider usage: 2 calls, 3251 prompt + 167 completion tokens, 117.219 s model time.
Old paused MOCK workflow preserved. Saved browser-live-cpu.json, its raw workflow
and screenshot; no source/UI assets changed. Current C:/E: resource snapshot is
local-model-cpu-resource-final.json; no new download or system setting change.

## Agent business access and selected actions, 2026-10-13

Inspected AGENTS, CODEX_START_HERE, MASTER/clarifications and source requirements;
preserved the original handoff and user workspace. P0: scoped detail/history reads
and exact selected-action preparation. P1: remaining deterministic computations,
conditional proposals and actual local-model requests. P2: external integrations,
large-dataset query work, repeated/held-out evaluation and production isolation.

Implementation files: new finance/agent_data.py; finance/agents.py,
finance/workflows.py and finance/gateway.py; contracts/agent-tools-v2.json;
scripts/live_compare.py; new tests/test_agent_data.py; tests/test_postgres.py and
tests/test_gateway.py. Existing object storage handles saved calculation details;
no relational schema migration is needed. Existing approvals, worker, reserve,
idempotency and independent simulator controls remain authoritative.

Documentation: README, AGENT_CAPABILITIES, adr/0004-agent-business-access,
IMPLEMENTATION_STATUS, KNOWN_LIMITATIONS, CONTINUATION, implementation_catalog,
model_cards/local-gateway, LIVE_MODEL_RESULTS and runbooks/local-llm. Generated
requirement reports are refreshed from the final actual regression artifact.

Actual intermediate verification (all Python commands use .venv/Scripts/python.exe):

- `scripts.test --output artifacts/regression-agent-data-v1.json`: 160 PASSED,
  128.197 s, including PostgreSQL. Original acceptance 96 PASSED / 4 NOT_RUN.
- `scripts.test --output artifacts/regression-agent-data-v2.json`: 161 PASSED,
  147.509 s, including PostgreSQL and selected-action reconciliation after real
  explicit test-harness approval. Original acceptance unchanged.
- `scripts.check`: Python/JS syntax, Ruff, mypy and formatting all PASSED.
- `unittest tests.test_agent_data tests.test_workflows -v` after visible-record
  prerequisites: 17 PASSED, 18.461 s. `unittest tests.test_gateway -v` after bounded
  CPU timeout extension: 5 PASSED, 2.610 s. Offline fixtures are not LIVE results.
- First LIVE probe v1 stopped on the existing 3 GiB commit reserve; preserved raw
  live-platform-probe-v1.json and live-platform-resource-stop.json. User explicitly
  authorized stopping Claude again. Verified Claude.exe processes and its own
  CoworkVMService were stopped; VM commitment released, no files deleted. Protected
  CPU Ollama restarted only after the unchanged 8 GiB startup preflight passed.
- Probe v2: both cases FAILED. Supplier details used list arguments in a detail
  call, then asked the user for an internal ID. Saved-plan preparation timed out
  under 120 s/request after incorrect tool selection. Preserved the raw report.
  Added schema and server prerequisites for matching visible dataset/record IDs
  and known plan IDs. CPU per-request bound now permits an explicit 240 s setting;
  default stays 60 s and total task bound 600 s. Memory/disk guards are unchanged.

Final verification is recorded in AGENT_PLATFORM_RESULTS.md. No real payment,
paid API or real business-data transfer is part of this stage. Four original
research/deployment targets remain NOT_RUN; broader product acceptance is PARTIAL.

Further actual verification and larger-model request, October 13:

- `scripts.test --output artifacts/regression-agent-data-v3.json`, with PostgreSQL:
  **163 PASSED**, 144.756 s. Includes diagnosis with quarantined import rows, visible
  record prerequisites, deduplicated model plan projections and exact selected
  action approval/execution. Original acceptance: 96 PASSED / 4 NOT_RUN.
- `scripts.check`: all five checks PASSED; `scripts.report --tests
  artifacts/regression-agent-data-v3.json` regenerated requirement evidence.
- LIVE v3 was interrupted after five completed failures because it used the older
  workflow revision. Its raw report is preserved, with explicit interruption
  metadata in live-platform-qwen-v3-interruption.json. It is not a current run.
- The user requested a larger local model and explicitly asked to try the current
  memory. Downloading qwen2.5:14b-instruct-q3_K_S on E:; inference is still pending.
  Updated scripts/local_llm.py allowlist/reserve, scripts/resource_guard.py E:
  footprint cap 14 -> 20 GiB, tests/test_resource_guard.py and local-llm runbook.
  Startup/runtime memory, C: and E: free-space reserves and the 2 GiB job cap stay
  unchanged. The final 163-test run includes these changes.

During LIVE review, the long-document case exposed an over-specific grader: the
model read the entire source through search_documents/get_evidence and correctly
answered/cited 45 days, but the grader demanded the paginated list/read route.
Changed scripts/live_compare.py and tests/test_live_evaluation.py to accept full
evidence only when the model-visible source ID/text exactly matches the complete
tool result. Truncated text, a different source and changed world state still fail.
Actually ran `unittest tests.test_live_evaluation -v`: **7 PASSED**, 0.033 s.
This grader-only change follows the 163-test full regression; financial/model
runtime code is unchanged. Preserve raw LIVE scores and attach a separate regrade
with source/report hashes rather than relabel old inference as a new run.


## S30 — expanded 14B evaluation harness (2026-10-13)

User requested more varied local 14B tasks. Added ten exploratory cases to
`scripts/live_compare.py`, supplementing ten platform cases: forecasts, eligibility,
clarification/no-debt infeasibility, injected document instructions, approval bypass,
Chinese cash question, exact financing amount, saved-plan stress, literal search
and credential requests. Added argument-unit/literal-query/secret-exposure grading;
free-text assessment remains explicitly separate. Added scenario inventory in
`docs/LOCAL_14B_SCENARIOS.md` and three grader regression tests in
`tests/test_live_evaluation.py`. No finance/model behavior changed during evaluation.

Actually ran `.venv\Scripts\python.exe -m unittest tests.test_live_evaluation -v`:
10 PASSED, 0.030 s. Ran `python -m scripts.check`: all five checks PASSED.
These test the harness; they are not LIVE quality results. Full 163-test regression
predates these grader-only changes. LIVE 20-case outcomes remain in progress.


## S31 — RAM-constrained 14B cache profile

Two Q8 KV-cache runs stopped at the unchanged 5 GiB free-RAM threshold. Evidence:
qwen14-expanded-guard-stop-v1.json (5364383744 bytes) and v2.json (5232418816).
User explicitly chose continuation with current memory and protection. No unrelated
processes, browser tabs, files or Windows settings were changed.

Added validated SME_OLLAMA_KV_CACHE_TYPE=q4_0 opt-in to scripts/local_llm.py; default
remains q8_0. Disabled the bundled llama-server's additional idle prompt cache via
LLAMA_ARG_CACHE_RAM=0 (verified in installed --help). Model weights/context/CPU mode,
financial tools, approvals, RAM/disk/commit thresholds and Windows Job are unchanged.
Q4 KV cache may affect output precision; its live outcomes must remain a separate
profile, not silently pooled with Q8. Official reference: https://docs.ollama.com/faq

Actual commands: unittest tests.test_live_evaluation tests.test_resource_guard -v:
16 PASSED, 0.988 s, including real Windows allocation rejection and process cleanup.
`scripts.check`: all five PASSED; quality-qwen14-cache-v1.json. These focused checks
supplement, not replace or redate, the earlier 163-test full regression.


## S32 — truthful partial-tool diagnostics

A 14B financing simulation executed snapshot/screen/calculator successfully, but its
final model answer exceeded the cumulative600-second budget. Failed public workflow
state omitted outputs, causing the grader to also label those successful tools as
missing. Updated scripts/live_compare.py to use durable tool events when available;
completion/model failures still fail the task. Original LIVE reports stay immutable;
post-hoc grading is recorded separately and is not new inference. Added a regression
for this exact failure boundary in tests/test_live_evaluation.py.

Actually ran unittest tests.test_live_evaluation -v:11 PASSED,0.021s. Last recorded
Windows resource checks remain16 combined tests PASSED0.988s before this grader-only
change (six resource checks unchanged). Full financial regression remains the prior
163 PASSED artifact, not silently relabelled as a new run.


## S33 — completed expanded14B evidence and browser probe

Completed20 distinct cases/21 attempts across7 raw reports;8 strict passes.
Assistant narrative review6 complete/5 partial/7 failed/2 resource-interrupted
scenarios (3 attempts). Financial state/policy/world unchanged in all21; zero
payment actions/approvals/jobs. Token scan21 PASS, tokens not included in report.
All original financial-code hashes match across reports. Post-hoc durable-event
grading changes diagnostics only; raw statuses/reports preserved.

New artifacts:local-qwen14-expanded-summary.json, live-qwen14-assistant-review.json,
live-qwen14-expanded-regrade.json, live-qwen14-report-secret-scan.json,
quality-qwen14-final.json. Main readable report:docs/LOCAL_14B_RESULTS.md.
Updated scenario inventory, README, status/limitations/catalog/model card and
continuation. Acceptance/traceability derived from prior regression-agent-data-v3,
not a new regression run. Latest scripts.check all5 PASS; evaluator11 PASS and
preceding evaluator+resource16 PASS recorded in S31/S32.

Supplementary UI query COMPLETE after317.297s model time,2calls/4775tokens.
Cash120000CNY/as_ofOct10 correct; source_id erroneously replaced with snapshot_id,
three sentences instead of requested two. PARTIAL, excluded from20-case score.
Saved browser-qwen14-expanded.json, workflow JSON, screenshot. No UI code changes.
User consent retained current memory and protection; no foreign apps/settings
changed. Q4 KV cache432MiB observed; three RAM reserve stops remain in evidence.
