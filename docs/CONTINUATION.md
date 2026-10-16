# Precise continuation point

<!-- QUALITY-V5-RESUMED-START -->
Latest checkpoint, 16 Oct: all remaining 51 EN/ZH scenarios executed.
Combined 74 unique cases: 67 PASS / 7 FAIL.
New 51: 47 PASS / 4 FAIL. Original full5 failures preserved.
Two primary failures were transport-only; separate retries: {'PASSED': 1, 'FAILED': 1}, not substituted into the primary score.
Execution mode: SEGMENTED_RESUMPTION_AFTER_SERVICE_RESTART, two service identities;
same model/engine/context metadata and budgets, no weight-hash proof.
SSH port 40390 with unchanged pinned host key. No agent-initiated remote restart.
Successful coverage 18/18 tools, 29/29 datasets; recorded safety assertions passed.
Narrative review: {'COMPLETE': 54, 'PARTIAL': 4, 'FAILED': 7, 'MINOR_ISSUE': 9}; coding assistant, not independent. Errors remain.
All 22 measured Strata source files unchanged. Wider 85-file freeze differs only
in owner commit d1647af resource_guard.py (typing alias); six existing guard tests PASS.
No fresh full regression, PostgreSQL, UI test or cabinet 8092 restart this series.
Previous regression 230 PASS / 1 setup FAIL / 4 PG SKIP, isolated failed test PASS.
T001–T100 96 PASS / 4 NOT_RUN; V03 unchanged. No new production-quality claim.
Evidence: artifacts/strata-quality-v5-enzh-resumed-20261016.json and raw segments.
See STRATA_QUALITY_V5_RESUMED_RESULTS_RU.md and
STRATA_QUALITY_V5_RESUMED_ANSWERS_RU.md. Prior partial checkpoints are historical.
<!-- QUALITY-V5-RESUMED-END -->

<!-- QUALITY-V5-STATUS-START -->
## Latest checkpoint: 16 Oct 2026 — incomplete evaluation, SSH unavailable

Current contracts: agent-tools-v4 / answer-refs-v5 / answer-quality-v3.
Last complete EN/ZH run full2: 66 PASS / 8 FAIL (74), on earlier code.
Current frozen code full5: 20 PASS / 3 FAIL (23/74); transport stopped between cases.
51 cases remain NOT_RUN in this attempt. No new inference on 16 Oct.
All 23 available answers reviewed: 19 COMPLETE / 1 PARTIAL / 3 FAILED.
Review is by the coding assistant, not independent. Remaining failures include
needless clarification, rejected final formatting, off-topic document answers and
a missing title despite all 24 documents being read (strict PASS, prose PARTIAL).
Offline: 230 PASS / 1 sandbox-port setup FAIL / 4 PG SKIP; isolated failed test PASS.
Targeted tests: 29 PASS; quality: nine PASS. Never replace the recorded full failure.
85 frozen files verified unchanged; approval/execution/validation and original graders unchanged.
T001–T100: 96 PASS / 4 NOT_RUN; V03 unchanged. No production-quality claim.
SSH 195.208.16.1:45161 failed before authentication (missing protocol banner),
both bridge startup and independent read-only check. Remote model health UNKNOWN.
Local listeners 18443 and 8092 were absent. No remote restart or fallback.
After access is restored, continue the 51 remaining case IDs from
artifacts/quality-v5-enzh-status-20261016.json in explicit sequential segments,
preserving full5 outcomes and verifying same model/config/code/cases. This is a plan,
not completed evidence. Do not change runtime during the remaining evaluation.
See STRATA_QUALITY_V5_STATUS_RU.md, STRATA_QUALITY_V5_PARTIAL_ANSWERS_RU.md,
TECHNICAL_REPORT_RU.md and the immutable raw artifacts linked there.
Older dated checkpoints below are historical, including prior running-process claims.
<!-- QUALITY-V5-STATUS-END -->

## Expanded evaluation, 15 Oct — completed with remaining failures

Read `STRATA_CHALLENGE_RESULTS_RU.md`, `STRATA_CHALLENGE_FIXES_RU.md` and
`AGENT_CHALLENGE_DESIGN_RU.md`. Full 54 new + 20 original LIVE cases completed:
67 PASS / 7 FAIL; actual successful coverage 18 tools / 29 datasets. Baseline
51: 37 -> 46 PASS. Text review retained independent of the strict grader.
Source cutoff, retrieval, money/ID binding and history semantics have fixes.
Current answer-refs-v4 excludes raw non-document source text from numeric refs
and supplies repair diagnostics without a rejected draft. The draft variant
regressed (8/15), retained as evidence, and was replaced. Full v4 follow-up is
COMPLETED: 13 PASS / 2 FAIL in `strata-challenge-diagnostics-cases-20261015.json`.
Read `STRATA_CHALLENGE_FOLLOWUP_RU.md`: company/policies list omission and rejected
delivery final remain; all latest source hashes match. Cabinet 8092 runs v4 and
HTTP checks passed in `strata-cabinet-challenge-v4-20261015.json`.
Final4 offline regression 213 PASS / 4 SKIP, quality nine PASS. Do not upgrade
V03 or claim unrestricted semantic correctness. The full 74 run uses v2 refs;
latest v4 must be assessed using its own source hashes and affected-case run.

The sections below are historical checkpoints.


## Latest work — 15 Oct completed rerun, semantic limits remain

Read `STRATA_FINAL_SCENARIOS_20261015_RU.md` first: **20 PASS / 0 FAIL** on all
same 20 synthetic cases; text review **18 COMPLETE / 2 PARTIAL** (assistant review).
Technical changes and every failed/interrupted attempt: `STRATA_FIXES_20261015_RU.md`.
Exact-value references, observed IDs, bounded repair, tool-phase completion and
Strata final-writer protocol are implemented. Financial authorization/execution
modules and the original scenario grader were not changed.

Full regression 195 PASS / 4 PostgreSQL SKIP (199); target 47 PASS; quality nine PASS.
Latest raw run `strata-final4-20261015.json` and regression of the same suffix.
Next quality work: typed semantic claims/AnswerBundle, history version semantics,
independent holdout and LIVE approval-to-reconciliation acceptance. Do not equate
exact value substitution or strict PASS with unrestricted financial correctness.

Owner supplied SSH port 45161; pinned key verified. Existing synthetic cabinet
8092 resumed without seed/reset and health/home/auth checked; bridge 18443.
See `strata-cabinet-final-20261015.json`. Recheck listeners before reconnecting;
never print SSH or membership credentials. No weights downloaded, remote model
restart, owner data access or real payments. All earlier user changes preserved.

The following sections describe earlier checkpoints, not current test counts.

## Latest authorized work — Strata, 14 Oct 2026

The owner requested server inference and scenario tests. Connection and provider
implementation are complete; read `STRATA_RESULTS_RU.md` for measured outcomes
and `runbooks/strata.md` for safe restart instructions. The running remote model
already existed: engine 0.1.43.1 / `qwen3.8-flash-next-iq3_xxs`, RTX 3090, 64 GB.
Do not reinstall weights or restart the remote service merely to reconnect.

Local authenticated SSH bridge: 127.0.0.1:18443. New synthetic LIVE cabinet:
127.0.0.1:8092, `.runtime/strata-demo`; its membership file stays private.
Bridge configuration, PID/log files and optional Paramiko installation are in
`.runtime/strata-client`. Verify live processes before using a saved PID.
`SSH_key.txt` is ignored; never print it. No owner data or real payments were used.

Final regression: 184 PASSED / 4 PostgreSQL SKIPPED, nine quality checks PASSED;
final targeted adapter/gateway/governance tests 16 PASSED. New LIVE reports keep
all failures and a separate assistant review. Critical finding: model prose
repeatedly converts money by the wrong scale despite correct tool results.
Do not close V03-03/04/14 from these connection/reading/proposal tests.

The following documentation-sync checkpoint predates this work.

## Current state — v0.3.0, 14 Oct 2026

Read `../CLAUDE.md` first, then `CURRENT_STATE_RU.md` for the current Russian
summary, `V03_PLAN.md` and `ACCEPTANCE_MATRIX_V03.md` for scope and priorities.
Code baseline: `d3e24b6` on `main`; Git was clean before this documentation sync.
There is now a private origin; old statements below saying there is no Git are historical.

The main cabinet is Home / Money / Plans / Documents / Activity / Settings with
Copilot as a panel. Financial cases, option comparison, hash-bound action review,
CSV/XLSX mapping, per-receivable what-if, 8-hour cookie sessions and 24-hour
real-time TTL for new approvals are implemented. LangGraph, OR-Tools, independent
validation, queue worker and sandbox reconciliation remain the financial kernel.

Priority: finish the owner path. The 14B model is temporary; model optimisation,
CompletionGate, narrative validation and LIVE E2E wait for the target model.
Do not resume the old 14B evaluation merely because of a historical checkpoint.

Verification during this sync:

- `scripts.test --pattern test_v03.py --output artifacts/v03/codex-sync-tests-host-20261014.json`:
  11 PASSED / 1 FAILED. The background Copilot test encountered WinError 32 while
  removing its temporary SQLite database. One isolated rerun passed; the cleanup
  instability remains unresolved. Both reports are preserved.
- The first restricted-shell run failed all 12 during sandbox startup (loopback
  denied, WinError 10013); see `codex-sync-tests-20261014.json`, not product failures.
- `scripts.e2e_v03 --output artifacts/v03/codex-sync-e2e-20261014.json`: 21/21 PASSED,
  five settled operations, matched reconciliation, restart recovery without duplicates.
- Saved browser evidence: 6/6 current web hashes match; 11/11 screenshots exist.
  No new browser walkthrough, full regression, PostgreSQL suite or LIVE model run.

Last full release regression is still `artifacts/v03/regression-v03.json`:
177 PASSED / 4 SKIPPED (PostgreSQL not configured), T001–T100 96 PASSED / 4 NOT_RUN.
The release V03 matrix has 9 PASSED / 5 PARTIAL / 2 EVIDENCE_RECORDED /
6 DEFERRED_MODEL / 3 NOT_RUN. Partial refresh runs do not regenerate that matrix.

Open: V03-07 server read filters, V03-21 unrelated-change tolerance, V03-22
isolation/backup/roles, alerts ack/debounce, remaining legacy tools, usability,
background-test cleanup and complete validation of UI context references.

Use Windows `.venv` directly from Codex; devbridge is for the Linux VM. Keep
`.runtime/pg-workspace` read-only; never seed/reset it. Dev cabinet: v03-dev on 8090;
test E2E uses a fresh directory under `.runtime/v03-e2e`. Verify live processes
before relying on any port or PID. No app process or model was started for ongoing
use by this sync; only short-lived test processes were launched.

## Historical v0.2 checkpoints below

The following records preserve old commands, outcomes and resource incidents.
Their process IDs, active model choice, priorities and Git statements are not current.

## Historical completed state — 2026-10-13 00:24 UTC

Latest authorized task (more diverse14B tests) is completed:20 distinct scenarios,
21 attempts,7 immutable raw reports. Read LOCAL_14B_RESULTS.md and
artifacts/local-qwen14-expanded-summary.json first. Strict8 passes/13 failures;
assistant review by unique scenario6 complete/5 partial/7 failed/2 RAM-interrupted.
Three actual resource stops include repeated what-if. All financial safety checks
passed. No financial behavior changed during this evaluation; no real payments.

Latest code: scripts/live_compare.py exploratory10 + durable-event grading;
tests/test_live_evaluation.py11 checks; local_llm.py q4_0 opt-in and idle prompt
cache disabled; tests/test_resource_guard.py6 checks. Default cache remains q8_0.
Guard thresholds intact. Actual last commands:11 evaluator checks PASS0.021s;
preceding combined16 PASS0.988s; five quality checks PASS. Prior full163 PASS is
not a new run. Derived acceptance still96 PASS/4 NOT_RUN(T023/T031/T032/T097).
Original29 handoff hashes preserved. No Git metadata in workspace.

All benchmark drivers ended. Last known guard session41930 on11434 (q4_0 cache),
API34724 on8080 and existing PostgreSQL53556; verify liveness before reuse.
Supplementary real UI cash query workflow_be4e413ff19142c1afd4fdf6aef8f71c COMPLETE:
317.297s,2 calls,4775 tokens. Correct120000CNY/as_ofOct10, wrong source_id label
(snapshot_id instead). PARTIAL, excluded from20-case suite. JSON and screenshot:
browser-qwen14-expanded*. Existing financial history remains; no reseed.

Key next engineering gaps: evidence/tool-use completeness, real-ID recovery,
source-vs-snapshot citations, and long-chain final-answer timeouts. Preserve all
failed reports. Do not silently mark resource stops as reasoning failures or
compare cache/model scores across unmatched workloads. No new weights needed.
User wants current-memory protection; do not close foreign apps/lower thresholds.

## Historical checkpoints below (superseded by completed state above)

## Current: expanded agent platform verification, 2026-10-13

User authorized stopping Claude again. Verified Claude.exe processes and its
CoworkVMService were stopped; its VM released commitment. No files, startup policy
or Windows memory settings changed by this task. After a later system reboot,
CPU Ollama is under the same memory guard in session 76286; PostgreSQL53556 was
restarted from its existing cluster. Verify liveness before reusing session IDs.

Agent-tools-v2 implemented: finance/agent_data.py, agents.py, workflows.py, new
contract and tests. See AGENT_CAPABILITIES.md and ADR 0004. Detail tools require
visible matching record IDs; prepare requires visible plan/action pairs. Selected
actions retain scope through replan and cannot implicitly approve or execute other
plan actions. Full saved computation results and long-record continuation exist.

Final regression v3: 163 PASSED, 144.756 s, PostgreSQL included; acceptance
96 PASSED / 4 NOT_RUN. All five quality checks passed. Includes visible-record
prerequisites, quality diagnosis, compact plan quotes and resource-cap changes.
Independent planner/validator/executor still block unsafe plans. Subsequently fixed
only the LIVE grader to accept a complete get_evidence read as an alternative to
pagination: 7 focused evaluation tests PASSED (0.033 s), all five quality checks
PASSED again. The 163-test full regression predates that grader-only correction.

LIVE v1 probe stopped on commit reserve; v2 had wrong detail arguments and a CPU
timeout. Both raw reports remain. Full Qwen platform suite v3 was INTERRUPTED
after five completed failures because it had loaded older code. Its stale raw
RUNNING status is superseded by live-platform-qwen-v3-interruption.json. Preserve
both reports. Corrected v4 stopped after eight completed cases when the resource
guard detected C: at 268,492,800 free bytes; a later OS reboot ended the old
sessions. Explicit records: live-platform-qwen7-v4-interruption.json and
local-model-platform-v4-guard-stop.json. Raw RUNNING is stale. Original score 2/8;
separate post-hoc regrade 3/8 (valid whole-document evidence route). Review notes
are live-platform-qwen7-v4-review.json. Extension was interrupted without a final
case result; private-document was NOT_RUN. Do not relabel old timings as post-reboot data.

The user requested a larger free local model and explicitly asked to try the
current memory without closing more applications. qwen2.5:14b-instruct-q3_K_S
(local metadata 14.8B, Q3_K_S, 6,659,609,509 bytes, Apache 2.0) downloaded with
exit code 0 and digest verification. Metadata: qwen14-installed.json; log:
qwen14-download.log. Model files/TEMP remain on E:. The
allowlist/download reserve and E: runtime-footprint cap (14 -> 20 GiB) were updated
for the third model. Memory/C:/free-E: reserves and the 2 GiB private-commit job
limit remain unchanged. User screenshot and system inspection after the reboot
show C: ~14.6 GiB/E: ~35.2 GiB, pagefile now E:9728 MiB. This task did not change
pagefile settings. Fresh resources ~18.5 GiB RAM/~25.5 GiB commit available.
Actual 14B smoke PASSED: live-qwen14-smoke-v1.json, 12.628 s including load,
45 prompt +19 completion tokens, CPU/8192 context. Connectivity only.
Four-case 14B platform run is in session24729: supplier, invoice, fact history,
saved action; output live-platform-qwen14-v1.json. Same finance/gateway/tools code
as Qwen7, corrected grader; timing environment differs after the reboot.

API8080 restored in session34724 against `.runtime/pg-workspace`, LIVE14B and
explicit 240/600 budgets. No reseeding. User manually refreshed browser tab1/browser2 after its URL block. CUA access then
succeeded; existing OWNER credentials reopened the unchanged workspace. UI shows
LIVE qwen2.5:14b-instruct-q3_K_S. No new UI inference while sequential evaluation
runs. Latest user request expands testing to 20 cases: platform10 plus exploratory10.
Exploratory fixtures/grader added in scripts/live_compare.py; 10 focused offline
tests passed (0.030 s). All five quality checks passed; preserved as quality-qwen14-evaluation-v1.json.
First four platform cases COMPLETED (session24729 exited 0): 1/4 strict pass.
Supplier/invoice skip requested reads; history is correct; saved-plan case makes no
tool call. Session33727 ended exit1: import timed out after successful lists (416.1 s);
what-if was interrupted at 92.9 s by RAM reserve (<5 GiB). Guard session76286
ended exit1; exact evidence qwen14-expanded-guard-stop-v1.json. No disk shortage.
Chrome is a large RAM consumer; no external processes were stopped. User explicitly
chose to continue with current memory and unchanged protection. Restarting guard
after preflight, then remaining platform and exploratory tasks. Outputs live-platform-qwen14-rest-v1.json and
live-exploratory-qwen14-v1.json. Assistant reviews saved incrementally in
live-qwen14-assistant-review.json. No runtime/model code changes during tests. Preserve PG history;
finish results, limitations, iteration notes and derived reports before delivery.

## Historical: comparison complete, Qwen LIVE UI restored, 2026-10-12

This section is historical; the October 13 section above is the current checkpoint.
The user authorized stopping Claude processes; the verified root and children exited.
No Claude files or Windows pagefile settings were changed. Current models/runtime
remain on E: (~10.8 GiB). No additional downloads are needed.

Completed CPU evaluation: Qwen2.5 7B 8/10 strict passes, median 64.063 s;
Granite 3.3 8B after its native-protocol adapter fix 8/10, median 90.693 s.
Selected experimental model: Qwen. Both have narrative failures; read
LIVE_MODEL_RESULTS.md, local-model-comparison-summary.json and the two assistant
reviews. Granite was rerun after a provider-specific fix and Qwen reused; this is
iterative development evaluation, not a held-out or repeated benchmark.

Final full regression: artifacts/regression-cpu-protocol-fixed.json, **151 PASSED**
in 110.739 s, including PostgreSQL; original acceptance **96 PASSED / 4 NOT_RUN**.
All five quality checks passed. The earlier 150-pass/1-fail report remains preserved;
its failure was a newly added offline fixture missing mandatory usage counts.
scripts.report regenerated traceability from the final actual regression report.

The existing PostgreSQL UI is running at http://127.0.0.1:8080/#copilot, LIVE Qwen,
with explicit 120 s/request and 600 s/task model budgets. New browser query completed:
120,000 CNY as of 10 October, correct returned source IDs, Russian answer,
one get_financial_snapshot tool call, no plan/propose calls, 2 model calls,
3418 provider-reported tokens, 117.219 s cumulative model time. Evidence:
artifacts/browser-live-cpu.json, browser-live-cpu-workflow.json, browser-live-cpu.png.
The old MOCK PAUSED workflow remains intact; this cash query is not a financial
execution or a new golden-run claim. Earlier ten-route browser proof is unchanged.

Current process sessions for this chat: guarded Ollama 52915, API 27323. Verify
actual liveness before using them after a new turn. PG cluster remains on port 53556;
preserve .runtime/pg-workspace and its private login file. CPU guard: 2 GiB private
commit cap, mmap weights, batch 128, LLAMA_ARG_REPACK=0, disabled GPU, one model.
C: minimum during the successful CPU guard session stayed above 6.24 GiB;
final snapshot is in artifacts/local-model-cpu-resource-final.json. File mappings
consume additional physical RAM; the job cap is not total RAM or OS security isolation.
Use docs/runbooks/local-llm.md to restart with these exact explicit budgets.

Remaining: T023/T031/T032 research pipelines and T097 OS isolation; full product
PARTIAL. LLM action preparation has an integration gap: compact optimize_plan output
omits action IDs although prepare_action is offered. The server rejected invented
IDs; do not loosen its checks. Language, amount-unit and citation errors need work.
Live B1/B2/B3 ablations, repeated held-outs and independent human review are NOT_RUN.

## Historical override: CPU comparison running, 2026-10-12

The user explicitly authorized terminating remaining Claude processes. Verified
Claude.exe root PID 4120 was stopped; its children exited, no Claude files were
deleted. Later checks found no Claude/Ollama/vmmem leftovers before the new launch.
The project API was temporarily stopped to release memory; preserve its PG history.

Granite GPU loading failed inside the 6 GiB job and C: transiently fell to 0.77 GiB.
The guard stopped the process tree; C: recovered to about 6.3 GiB. Pagefile allocation
remained 8704 MiB; the temporary disk allocation's precise source is unresolved.
See artifacts/live-granite8-gpu-failed.json. Do not restart the GPU profile.

Current profile: CPU only, 2 GiB job, startup C: >=6 GiB, runtime >=4 GiB, 0.5-second
monitor, num_gpu=0, memory-mapped weights, batch 128, LLAMA_ARG_REPACK=0. The latter
avoids a ~3.6 GiB extra CPU weight buffer; official documentation and installed
llama-server --help confirmed support. Model weights remain unchanged on E:.
CPU smoke succeeded in live-granite8-cpu-smoke-v3.json (batch 32). A prior CPU attempt
failed on Windows status-file replacement; bounded atomic retry now handles transient
sharing failures, with persistent errors still stopping the job. Connection resets
are now typed MODEL_UNAVAILABLE failures, covered by a regression test.

The first CPU comparison completed: artifacts/live-comparison-cpu-final-v1.json.
Qwen: 8/10 structural passes, median 64.063 seconds. Narrative review is in its
companion -review.json; forecast is in Chinese, approval-bypass task loops with
invented IDs (server rejects them), and receipt task omits calculate_business_metrics.
Granite baseline: 1/10, zero native tool calls. Diagnosis found that the official
template omits native-tool instructions when a custom system message is supplied.
The adapter now restores Granite's format while preserving app rules; it never
executes JSON found in prose/code fences. Five gateway tests passed, including
unchanged Qwen messages. See artifacts/granite-native-protocol-diagnosis.json.

Corrected Granite rerun is running: artifacts/live-granite8-native-protocol-v2.json.
Cash case passed with a real snapshot call; qualitative review is saved separately.
Same 10 cases and CPU settings: 120 seconds/request, 600 cumulative seconds/task,
context 8192/output 1024, batch 128. Qwen's complete prior results are reused; only
Granite's provider formatting changed. This is iterative development evaluation,
not a held-out or perfectly controlled performance benchmark. Do not declare a
winner from the running file or conflate structural and narrative quality.
Do not run heavy tests or a second model concurrently. After completion, review
visible narratives, restore the PG UI with the chosen explicit local configuration,
check a new read-only live workflow in the browser, then run regression/quality.

New focused checks: 14 gateway/evaluation/resource tests PASSED before atomic-retry
test; then all 5 resource tests PASSED including that new regression. First sandboxed
attempts had local-socket/rename permission errors; normal Windows reruns passed.
Full regression-cpu-protocol.json: 150 PASSED / 1 FAILED in 109.367 seconds; the new
native-protocol test fixture omitted mandatory usage counters. Fixed fixture then
passed all 5 gateway tests. Run a fresh full regression after live evaluation to
record the final combined result. All 5 scripts.check checks passed before that
fixture-only correction. Historical 148-test report is not current proof.
See runbooks/local-llm.md for current settings; older sections below are history.

## Latest override: guarded local comparison resumed, 2026-10-12

The user approved reboot after cleanup, and shutdown /r /t 0 completed. After boot,
C: had 16.75 GiB free, E: 34.55 GiB, pagefile allocation 8704 MiB, no model processes.
The user explicitly resumed work on E: and subsequently requested models >=4B.
A later disk check found 61.82 GiB free on E:. No pagefile configuration was changed.

Actual Qwen2.5 7B baseline completed: 4/10 structural tasks; live-qwen7-guarded-v1.json.
No model memory failure. Weak tool sequencing caused invented snapshot IDs and extra
arguments. Added documented tool purposes and enforced prerequisites: snapshot compute
tools are exposed only after a successful snapshot read, with its exact ID enum;
server independently rejects unread/invented IDs. No backend authorization is relaxed.
Three diagnostic cases subsequently passed structurally (live-qwen7-prerequisite-probe-v3.json),
but visible-text review found Chinese response to a Russian forecast question and an
incorrect reserve disclaimer. See companion -review.json. Added metric definitions;
final two-model run must use identical latest source/settings. Both downloads are
complete: Qwen 4,683,087,703 bytes and Granite 4,942,892,065 bytes; installed runtime
totals about 10.78 GiB on E:. Offline manifest/blob-size evidence is retained in
artifacts/local-model-resource-stop.json. Granite inference has NOT_RUN. No winner.

The user confirmed the Claude VM download on C: was intentional and said to continue
on E:. Claude files were left untouched. System-disk reserve was changed explicitly
from 12 to 4 GiB; job memory remains 6 GiB, startup RAM 10 GiB / commit 8 GiB.
The subsequent launch was refused before any Ollama process started: available
Windows commit headroom was about 6.9 GiB, below 8 GiB. C: had about 6.26 GiB free,
E: 51.01 GiB, physical RAM about 12 GiB free. No pagefile settings were changed.
The user was asked to free memory by closing unneeded applications. Continue with
a fresh resource check; do not bypass memory checks or start a second server.

Selected Qwen2.5 7B + Granite 3.3 8B. scripts/local_llm.py now limits provisioning
and requires project storage on E:, redirects child TEMP/TMP, and starts a single
Windows job with 6 GiB aggregate committed-memory limit, kill-on-close and no
breakaway. Startup and two-second runtime checks preserve C:/E:/RAM/commit reserves.
See runbooks/local-llm.md and LIVE_MODEL_PLAN.md. Disk checks are polling safeguards,
not hard quotas. GPU/other processes are not bounded by this CPU job limit.

Resource guard tests: 4 PASSED, including real Windows denied allocation and child
lifecycle; artifacts/resource-guard-tests.json. Focused gateway/workflow tests:
15 PASSED before the later tool prerequisite change; 13 PASSED after it. Latest full
regression: 148 PASSED in 121.968 seconds, including PostgreSQL;
artifacts/regression-live-prerequisites.json (96 acceptance PASSED / 4 NOT_RUN).
Four resource tests passed again after the disk-floor revision. Actual two-model
comparison is pending available memory. Business state preserved.

Earlier incident: all Ollama/download processes were stopped and the project-local
.runtime/ollama tree (10.37 GiB logical size) removed. C: stayed near 200 MiB because
its system-managed pagefile was 21.56 GiB after a second model server OOM. The original
C: baseline was not measured, so exact growth is unknown. Reboot subsequently freed C:.

Earlier partial live evidence remains intact: Qwen3 4B custom-template run passed
4/10 structural cases, six exhausted generation limits (live-qwen4-template-v3.json).
No Qwen3 8B or Granite inference occurred in that earlier experiment. Those weights
were deleted. Prior full stage: 143 tests PASSED; regression-live-stage.json.
T094 has since been refreshed with a read-only actual-browser check of all ten
routes and the saved response/approval; artifacts/browser-resource-stage.json.
The PG browser remains MOCK, with the existing PAUSED workflow and clock Oct 10;
it is not a completed golden. Start a new workflow when switching to a live model.

The following older continuation details predate this override.

Full-product acceptance is PARTIAL. Continue this repository; do not replace the
kernel, reinitialize original instructions or reseed existing workspaces. No Git
metadata exists. Source files and user handoff hashes are preserved.

## Current implementation

FastAPI/Pydantic transport, psycopg PostgreSQL financial store with restricted tenant
logins/RLS, SQLite fallback, OR-Tools CP-SAT, independent validator, actual LangGraph
with per-tenant SQLite checkpoints, opt-in Ollama adapter (offline tested only),
separate worker, CSV review, text/PDF lexical retrieval, signed internal webhook,
conditional supplier extensions, ten English UI routes and independent oracle v2.
Read implementation_catalog.json, ACCEPTANCE_MATRIX.md and KNOWN_LIMITATIONS.md.

## Evidence and live state

- Full suite: 136 passed; PostgreSQL tests included. artifacts/test-results.json.
- Browser completed golden is `.runtime/product`: five SETTLED, 28,000 CNY final,
  20,000 minimum, no missed deadlines/open debt/payables; LangGraph COMPLETE,
  one UNKNOWN event recovered. artifacts/browser-evaluation.json and current
  screenshots are proof. This workspace is served at 8081 in the current session.
- PostgreSQL exploratory cabinet `.runtime/pg-workspace` is served at 8080. It has
  a confirmed supplier extension to Oct 13, reviewed synthetic invoice, Chinese
  source document, restored reserve 20,000, cash 120,000, and a PAUSED approval
  workflow. During UI checks the synthetic clock advanced to Oct 6 before payment;
  it is not a successful golden. Do not reset its history or label it COMPLETE.
- Local PostgreSQL cluster: `.runtime/postgres`, admin connection in
  `cluster.secret.json`; never print it. API/worker use the restricted connection in
  the workspace's `postgres.secret.json`. Membership token is the OWNER value in
  that workspace's `local-login.secret.json`. Tokens differ between workspaces.
- Ports/processes are session-local, not guaranteed to survive app/host restart.
  Use `scripts.postgres status/start`, then `scripts.serve --directory ...`.
- Rehearsal and golden oracle v2 passed; live-smoke.json is BLOCKED. No real model
  ran. A test HTTP Ollama fixture is not real-model evaluation.

## Next work in order

1. Preserve the 136 passing financial tests. Policy observation-time migrations
   (SQLite 004 / PostgreSQL 002) are now implemented and tested. Historic queries
   cannot borrow a later reserve; unknown legacy times fail explicitly. No further
   policy migration is needed for the completed local behavior.
2. Separate process/OS permissions for model-facing service, observed storage and
   simulator truth; separate worker DB role from API. Automate negative private
   file/seed/label access tests before changing T097/I24/I28 to verified. Do not
   change host-wide ACLs or enable Docker/network services without appropriate scope.
3. Durable import/parser jobs, review-friendly mapping, OS parser memory limits;
   implement additional formats only from actual verified specifications. Current
   text PDF is bounded but not an OCR/OFD implementation.
4. Internal event/alert inbox and observed materiality/debounce; preserve mandatory
   fresh checks before sends. Add event-triggered replan tests that retain settled
   actions and never clear UNKNOWN reserves solely due to age.
5. Diverse linked 3–5-company synthetic generator, meaningful aging/concentration
   metrics and broader paired benchmark. Keep future truth outside agent context.
6. Authorized configured local model: MODEL_PROVIDER=ollama, exact installed name,
   localhost endpoint and ALLOW_LOCAL_MODEL_INFERENCE=true. Then run provider smoke
   and real LangGraph novel-task/clarification/injection suite with actual usage.
   Do not download a model, invent its ID/license or silently fall back to mock.
7. Standalone browser E2E runner, accessibility/cross-browser coverage, final clean
   rehearsal and required release/submission artifacts. Existing `make e2e` verifies
   recorded CUA evidence only. No Git release tag can exist without a repository.

P2 training/survival/holdout research, real banks, FX and paid/real-data integrations
remain outside the current authorization. Update I/T/W status only from actual
commands and artifacts. scripts.report rebuilds the matrix without altering raw
unittest outcomes or handoff checklists. Keep failed attempts and scope limitations
visible; never substitute aggregate green counts for unfinished requirements.


Latest restart: guard session41473, same safety limits. Driver session23895 runs
exploratory boundaries4, remaining platform5 (including resource-interrupted what-if
retry), then exploratory compute6. New reports: live-exploratory-qwen14-boundaries-v1.json,
live-platform-qwen14-resume-v1.json, live-exploratory-qwen14-compute-v1.json.
Approval-bypass case passed structurally and narrative review: explicit refusal,
no false claim of payment. The unstarted live-exploratory-qwen14-v1.json does not exist.


Q8 retry also stopped on RAM (guard-stop-v2). No foreign process was closed.
Introduced bounded SME_OLLAMA_KV_CACHE_TYPE q8_0/default or q4_0 and disabled
LLAMA_ARG_CACHE_RAM. Six resource tests + ten evaluator tests PASSED (0.988 s),
all five quality checks PASSED. Current Q4-cache guard session81810; actual log
confirms KV432 MiB, context8192, prompt cache disabled (qwen14-kv4-runtime.json).
Driver session71405 runs platform4 (long document/operations/extension/private),
exploratory6 (forecast/eligibility/clarification/injection/simulation/stress), then
what-if retry. Outputs live-platform-qwen14-kv4-v1.json,
live-exploratory-qwen14-kv4-v1.json, live-platform-qwen14-whatif-kv4-v1.json.
Keep Q4-cache results distinct from Q8; model weights/finance tools remain unchanged.


Latest at ~2026-10-12 23:52 UTC: Q4 guard81810 and driver71405 ended on RAM reserve
(5341286400 bytes), evidence qwen14-kv4-guard-stop-v1.json. Platform Q4 four cases
COMPLETED: long document PASS, operations/extension/private strict FAIL. Forecast
PASS521 s (accurate money/dates but no source citation), financing interrupted by
RAM235.7 s. Reviews saved. Same profile restarted successfully in guard41930.
Driver10446 now runs last four distinct cases: clarification, document injection,
financing simulation, saved-plan stress; report live-exploratory-qwen14-final4-kv4-v1.json.
No Q4 what-if retry has run; two Q8 what-if interruptions remain the operational
result. Do not claim the planned third retry exists. Once the last four are attempted,
20 distinct cases /21 attempts exist unless another stop prevents coverage.
Finish all review notes, aggregate per-profile results with hashes and resource
interruptions separate, update docs/catalog and derive reports from prior163 report.
Optional additional read-only UI query only when benchmark inference finishes.
API34724 on8080 remains running with LIVE14B; existing PG history preserved.
