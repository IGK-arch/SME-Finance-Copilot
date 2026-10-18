# CLAUDE.md — orientation map (read this first, then only what the task needs)

SME Finance Copilot, Topic E. Local synthetic SME cash workspace: import → facts → snapshot →
forecast → OR-Tools plan → independent validator → exact owner approval → worker → independent
sandbox → reconciliation. Version **0.3.0** (pyproject, FastAPI); code is at the **v0.3 iteration**
(owner main-path cabinet). Status: PARTIAL, synthetic/sandbox only, MOCK model by default.
Answer the owner in Russian. Code, UI copy and docs are English unless a doc is `*_RU.md`.

## Do NOT read unless the task requires it (expensive)
- `MASTER_SPEC.md` (300 KB), `SME_Finance_Copilot_Master_Spec.docx`, `sources/R*` — original spec.
- `docs/TECHNICAL_REPORT_RU.md` (100 KB) — historical v0.2 body plus a v0.3 addendum; this file supersedes it for orientation.
  `docs/CURRENT_STATE_RU.md` is the current Russian overview with the 14 Oct sync findings.
- `SME_Copilot_v0_3_Audit_UX_Package/` — already applied; IDs V03-01…25 live in `checklists/v03_acceptance.json`.
- `artifacts/*.json` raw runs, `.runtime/`, `.venv/`, `.mypy_cache/`, `__pycache__/`, `web/legacy/`.
- `docs/LOCAL_14B_*`, `docs/LIVE_MODEL_*`, `docs/AGENT_PLATFORM_RESULTS.md` — historical 14B evaluation.

## Where things are
| Area | File | Notes |
|---|---|---|
| Money/time/errors | `finance/domain.py` | int minor units, `minor()`, `utc()`, `digest()`, `FinanceError(code,msg)`, `require()` |
| Storage | `finance/store.py`, `finance/postgres.py` | same SQL dialect; `objects(tenant,kind,object_id,payload)` is append-only KV used for new features (no migrations) |
| Import (strict CSV) | `finance/ingestion.py` | `import_csv`, quarantine, `snapshot()` (writes snapshot object) |
| Import wizard | `finance/mapping.py` | CSV/XLSX → mapping → preview → commit via `import_csv`; ambiguous dates/decimals are errors |
| Calculations | `finance/compute.py` | `forecast`, `obligation_flows` (supports `obligation_shocks`, `customer_shocks`), `financing`, `candidate`, oracle `optimize` |
| Planner | `finance/planner.py` | CP-SAT `solve`; `OBJECTIVES` + `objective_scope()` shared with oracle (keep both in sync) |
| Validator | `finance/validation.py` | independent; never call compute/planner from it |
| Execution | `finance/execution.py` | `command/approve/prepare/deliver/refresh`; real-time approval TTL (`approval_ttl` objects) |
| Worker | `finance/worker.py` | `enqueue`, `work_once`; status lookup before any resend |
| Owner read models | `finance/cases.py` | home, case events (OPENED/PROBLEM_CHANGED/OPTIONS_COMPUTED/OPTION_SELECTED/CLOSED), options, review, timeline, activity, alerts, what-if, user context |
| Approve reviewed payload | `finance/digest_check.py` | browser sends only payload hash; server recompiles and compares |
| Copilot glue | `finance/copilot.py` | background runs, scoped plan/action/obligation context, result cards; case_id is only a generic hint |
| Agent graph/tools | `finance/workflows.py`, `finance/agents.py`, `finance/agent_data.py`, `finance/gateway.py`, `finance/strata.py` | `ChatGateway` providers: mock / disabled / ollama / strata / llamacpp (explicit server opt-in) |
| HTTP | `finance/asgi.py` (FastAPI, `/session` cookie auth, `/assets/*`, `/legacy`), `finance/api.py` (`dispatch` + `v03_route`) | |
| UI | `web/index.html`, `ui.js` (h(), api(), chart, formatting), `pages.js` (pages + Dialog), `copilot.js`, `app.js` (router/session), `style.css` (tokens on `:root`) | |
| Sandbox | `sandbox/world.py`, `sandbox/server.py` | separate process + `private/world.db` |
| Runtime/harness | `scripts/runtime.py`, `scripts/serve.py`, `scripts/task.py` | |

API added in v0.3: `GET /v1/home`, `GET /v1/case`, `POST /v1/case/{options,select,what-if}`,
`GET /v1/review/{plan}/{action}`, `POST /v1/review/{plan}/{action}/approve`, `GET /v1/timeline/{action}`,
`GET /v1/plans/{id}/progress`, `GET /v1/activity`, `POST /v1/imports/{preview,commit}`,
`GET /v1/copilot/{run}`, `GET|POST /v1/context`, `POST /session`, `POST /session/logout`.

## Invariants (never break; tests guard them)
Integer minor units, no float money. Invoice/expected receipt ≠ cash. Facts versioned, observed vs
effective time. Validator independent of solver. One exact OWNER approval per action, bound to payload
hash; no approve-all; LLM never approves/sends. Reservations, stable idempotency key, UNKNOWN keeps
reserve, status lookup before resend. Tenant from membership only. No secrets/tokens in outputs, URLs,
localStorage. LIVE failure never falls back to MOCK. Case is RESOLVED only after plan COMPLETED + matched
reconciliation. Statuses honest: NOT_RUN / DEFERRED_MODEL never reported as PASSED.

## UI conventions
DOM via `UI.h()` text nodes only (no innerHTML with data). CSP `style-src 'self'`: no inline `style=""`
strings — use `style: {…}` objects (CSSOM) or classes. Amounts: display strings come from the server
(`money()` → `{minor, minor_str, display}`); client exact math only via `UI.minorText`/`UI.parseMajor` (BigInt).
Dates shown in Asia/Shanghai (`UI.day/time`), real timestamps via `UI.real` (en-GB). Pages filter null
children with `put()`. Theme: warm ivory/near-black; accent token `--accent`; no third-party logos/fonts.

## How to run things on this machine (important — saves time)
- Windows host, project `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff`.
  Linux VM (`device_bash`) sees it at `$HOME/mnt/sme_codex_handoff`; VM has python3.10/node but **no project
  deps and no PyPI**. The cloud container has no PyPI either. Windows `.venv` (Python 3.11.9) is the only runtime.
- Commands run through the owner-started allowlisted runner `scripts/devbridge.py` (owner runs
  `.\.venv\Scripts\python.exe -m scripts.devbridge`). Submit a JSON task into `.runtime/devbridge/queue/`,
  read `.runtime/devbridge/out/<id>.json|.log`. Kinds: `module` (`scripts.*`, `tests.*`, `unittest`),
  `serve` (workspaces `dev`=.runtime/v03-dev, `pg`=.runtime/pg-workspace, `e2e`; ports 8000–8999), `stop`.
  If no output appears within seconds, the runner is not running — ask the owner to start it.
- Helper (recreate in VM `$HOME/bridge.py` if missing): writes `queue/<id>.json`, waits, prints result + log tail.
- Dev cabinet: serve `dev` on 8090; login token in `.runtime/v03-dev/local-login.secret.json` (OWNER; test value,
  never echo it in chat). `pg-workspace` is the owner's data: read-only browsing only, never seed/reset.
- Writing big files: `device_bash` heredocs fail above ~40 KB (E2BIG). Write in the cloud under
  `/mnt/user-data/outputs/…` and copy with `device_commit_files`. Small edits: python read-modify-write in VM.
- From the Linux VM deleting files in the folder is disabled; move strays into `.runtime/devbridge/out/`.
  (Any session running directly on the Windows host, including Codex, can use PowerShell, git and `.venv` directly; devbridge is only needed from the VM.)
- Browser checks: built-in browser pane at `http://127.0.0.1:8090`; screenshots fail while the pane is
  hidden — use `get_page_text`/JS measurements, ask the owner for Ctrl+Shift+B when images are needed.
  Hard-reload (`location.reload()`) after CSS/JS changes; restart the server after Python changes.

## Command output (rtk)
Shell output on this host is condensed by rtk via a hook (matcher `Bash|PowerShell`). `rtk gain` shows token
savings; `rtk recall` re-reads the full output of a recent command; prefix `rtk proxy <cmd>` only when a result is
unusable (empty, garbled or contradicting its exit code).

## Verify (pick the smallest relevant set)
- Targeted: `{"kind":"module","module":"unittest","args":["tests.test_v03"]}` (~15 s).
- Full regression (~150 s): `scripts.test --output artifacts/v03/regression-v03.json`. PostgreSQL tests only run when `SME_POSTGRES_TEST_CONFIG` is configured; otherwise they are SKIPPED.
- Lint/types/format: `scripts.check` (must be all PASSED); `scripts.fmt` changes code and is only for intentional formatting work.
- Product path E2E (~20 s): `scripts.e2e_v03` → `artifacts/v03/e2e-latest.json`.
- Matrix: `scripts.report_v03` → `docs/ACCEPTANCE_MATRIX_V03.md` (reads artifacts only).
- Browser evidence `artifacts/v03/browser-v03.json` is valid only while `webHashes` match current `web/*`;
  after UI edits it becomes stale (T094 drops to NOT_RUN) until re-recorded.

## Current state (update this block when it changes)

18 Oct security audit (branch security-hardening): Host allowlist (`SME_ALLOWED_HOSTS`
adds hosts; TestClient must use base_url http://127.0.0.1:...), extra headers, bearer
lockout, `sme.security` log, strict JSON, XLSX DTD refusal, webhook replay no-op,
`agent.tool_call` audit for T2 tools, `scripts.security_scan` in CI. Server IP remains
only in git history (K13). See docs/submission/SECURITY_AUDIT.md.

18 Oct: PR #2 merged (0b1720f): English reviewer docs in `docs/submission/`, Business
health card on Money, on-chain audit anchor (`finance/anchor.py`, `scripts.anchor_audit`,
optional `requirements-onchain.txt`, installed in `.venv`). First anchor on Ethereum Sepolia:
tx 0x7ac42f1f…d9d1ba, 72 audit records of `.runtime/v03-dev`, block 11941459, verify 5/5;
evidence `artifacts/onchain-anchors.json`. Testnet wallet key lives only in
`.runtime/v03-dev/anchor-wallet.secret.json` (never print). RPC needs a User-Agent (403 otherwise).
On merged main: regression 274 PASS / 4 PG SKIP; T001–T100 96 PASS / 4 NOT_RUN; e2e PASSED;
check all PASSED. Browser evidence re-recorded on throwaway 8091 workspace (text/DOM only, pane
hidden, no new screenshots); Activity anchor card not rendered there. Observed: case history
shows a duplicate 'problem changed' event after a clock advance (not fixed).

<!-- MULTIMODEL-100-START -->
Owner decision after comparison: retain the existing large Qwen on Strata
(`qwen3.8-flash-next-iq3_xxs`) as the selected LIVE model. Do not switch the
cabinet to a benchmark alternative. This decision does not change reasoning mode.

17 Oct final: COMPLETED / FINISHED, 500/500 unique primary outcomes, 100 per model.
Original Strata qwen3.8-flash-next-iq3_xxs restored; separate SSH45815 service check
at22:45:46MSK confirmed loaded=true, engine0.1.43.1. Queue/evaluator exited.
Strict PASS: Gemma62, Qwen3.6-35B54, GLM42. Occamy/Qwen3.8-27B each0, but each
has99 MODEL_UNAVAILABLE and1 pre-model POLICY_DENIED; their answer quality and
generation speed are NOT_MEASURED. All failures retained, no substituted retries.
Successful-case p50 seconds: Gemma12.144, Qwen3.6 20.872, GLM13.615.
42 matched both-PASS pairs: median Gemma/Qwen latency0.805 (19.5% lower).
Durable coverage: Gemma18/18tools,29/29datasets; Qwen17/18,29/29; GLM17/18,23/29.
Manual risk sample30 pairs (9 automatic PASS), not all500 or independent review.
Errors: semantic field/entity confusion, UNKNOWN/resend advice, pagination,
citation types, failed ID/tool recovery and validation fallback. Automatic PASS
does not prove prose. Qwen injection marker was in input tool text; not confirmed
attack execution. Frozen68 sources, case definitions, budgets/weight SHA unchanged.
10 reporting tests PASS; reporting lint/format/mypy PASS; generator + final audit PASS.
No fresh full product/PG/UI regression. Financial/tenant/approval guards unchanged.
See docs/MULTIMODEL_100_RESULTS_RU.md, MEASURED_RU/ANSWERS_RU of same prefix;
artifacts/multimodel-500-summary-20261017.json, narrative-review and final-audit.
No new model queue needed. Historical launch/recovery: docs/MULTIMODEL_100_RUN_RU.md.
Heartbeat sme-500 is PAUSED after completed comparison/documentation; app update and local configuration verified.
<!-- MULTIMODEL-100-END -->

<!-- REASONING-100-START -->
17 Oct: Qwen/Strata fixed-budget none/medium comparison COMPLETED: original 74 +
26 preregistered EN/ZH scenarios, 200 primary outcomes (198 reached model; two
AUDITOR POLICY_DENIED before model). Strict PASS none 87/100, medium 92/100;
manual clean text 77/80, joint strict+clean 76/75. Aggregate p50 30.946/28.236s,
p95 71.902/53.618s; 84 both-PASS pairs median medium/none ratio 1.090.
Two separate ACCOUNTANT diagnostics reached model; both safely refused escalation
but omitted company.role (strict FAIL, narrative PARTIAL). No substituted retries.
18/18 tools, 29/29 datasets; recorded safety checks pass. Regression 240 PASS /
4 PG SKIP; T001-100 96 PASS / 4 NOT_RUN; report tests 4 PASS; static checks 9 PASS.
See docs/REASONING_100_RESULTS_RU.md and REASONING_100_ANSWERS_RU.md; compact data
artifacts/reasoning-100-summary-20261017.json and reasoning-100-final-audit-20261017.json.
Adaptive routing NOT_IMPLEMENTED/NOT_EVALUATED; low/high NOT_RUN. Guards unchanged;
no cabinet restart/default switch. Medium74 had one typing-only cast delta, documented.
<!-- REASONING-100-END -->

<!-- QUALITY-V5-START -->
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
See docs/STRATA_QUALITY_V5_RESUMED_RESULTS_RU.md and
docs/STRATA_QUALITY_V5_RESUMED_ANSWERS_RU.md. Prior partial checkpoints are historical.
<!-- QUALITY-V5-END -->

Earlier checkpoints follow.
- 15 Oct expanded evaluation: 54 new scenarios + 20 original cases; full LIVE
  `strata-challenge-after2-20261015.json` completed **67 PASS / 7 FAIL**.
  Successful coverage: 18/18 tools, 29/29 datasets. Same 51 baseline cases:
  37 -> 46 PASS. All prose reviewed by coding assistant (not independent):
  53 COMPLETE / 11 MINOR_ISSUE / 5 PARTIAL / 5 FAILED. See
  `docs/STRATA_CHALLENGE_RESULTS_RU.md`, `docs/STRATA_CHALLENGE_ANSWERS_RU.md`,
  design and fixes of the same prefix. Safety checks passed within test scope.
  Contracts: agent-tools-v3, compute-v2, current answer-refs-v4. Source cutoff,
  title/Unicode/paged retrieval, quoted money, typed IDs, nonadditive history,
  initial gap and raw-CSV reference projection fixed. Execution gates unchanged.
  Repair-with-draft candidate regressed to 8/15 and was replaced. Diagnostics-only
  paired writer replay passed 4/4; full 15 affected-case follow-up: 13 PASS / 2 FAIL in
  `artifacts/strata-challenge-diagnostics-cases-20261015.json`. Do not claim full
  current-version 74-case acceptance from the earlier run; hashes differ.
  Final4 regression: 213 PASS / 4 PostgreSQL SKIP (217); delivery quality: nine PASS.
  Cabinet 8092 runs v4; HTTP verified in strata-cabinet-challenge-v4-20261015.json.
  Follow-up failures: company/policies lists omitted, delivery final rejected.
  No general semantic gate: status/prose errors and tool-route misses remain.
  T001-T100 unchanged: 96 PASS / 4 NOT_RUN. Earlier checkpoints follow.
- 15 Oct answer fixes and Strata rerun: **20 PASS / 0 FAIL**, all same 20 scenarios,
  original grader unchanged. Assistant narrative review: **18 COMPLETE / 2 PARTIAL**;
  this is not independent human review. See `docs/STRATA_FINAL_SCENARIOS_20261015_RU.md`
  for every answer and `docs/STRATA_FIXES_20261015_RU.md` for all attempts/changes.
  `answer-refs-v1` renders exact server amounts/percentages/dates/IDs, rejects
  unbound numbers and allows one bounded repair. Tool IDs require observed
  records; proposal/INFEASIBLE closes the tool phase. Final Strata requests use
  leading system rules, observed evidence without native call tags and explicit
  tool_choice=none; server still blocks calls during finalization.
  Exact references do not prove prose semantics: history can misleadingly sum
  versions; an earlier smoke mislabeled cash delta as cash balance. No general
  AnswerBundle/CompletionGate or target-model acceptance is claimed complete.
  Full regression **195 PASS / 4 PostgreSQL SKIP (199)**; target 47 PASS; quality
  nine PASS. T001–T100 remain 96 PASS / 4 NOT_RUN; V03 matrix unchanged.
  Latest evidence: `artifacts/strata-final4-20261015.json`,
  `artifacts/regression-strata-final4-20261015.json`. Intermediate attempts retained:
  first 15/20; second interrupted after 19 + separate last case; third 19/20.
  SSH restored at the owner-supplied endpoint (host kept out of the repo), original pinned key; no weights downloaded
  or remote model restart. Local bridge 18443 and existing synthetic cabinet
  `.runtime/strata-demo` on 8092 resumed and HTTP-verified after final tests.
  Verify processes on each new session; saved PIDs are not proof of availability.
  `pg-workspace` untouched; no real data/payment or LIVE approval/dispatch.
  Cabinet budget 64000 tokens vs evaluation 128000; default application remains MOCK.
- Strata integration (14 Oct, after the documentation sync): owner-authorized SSH
  reuses the existing remote RTX 3090 / 64 GB installation, engine 0.1.43.1,
  `qwen3.8-flash-next-iq3_xxs`. No model downloads or remote restarts. Authenticated
  loopback bridge on 18443; separate synthetic LIVE cabinet on 8092 in
  `.runtime/strata-demo`. Default remains MOCK; `pg-workspace` untouched. See
  `docs/runbooks/strata.md` and `docs/STRATA_RESULTS_RU.md` before using this model.
  SSH credential `SSH_key.txt` and `.runtime/*secret*` must never be printed.
  New full regression: 184 PASSED / 4 SKIPPED (188 tests), all nine quality checks
  passed. LIVE tool grades do not validate prose: repeated factor-of-ten money
  errors were observed. Target-model acceptance gates remain incomplete.
- Git: repo initialised on the Windows host (`main`), remote `origin` = github.com/IGK-arch/SME-Finance-Copilot
  (private). `.gitattributes` is `* -text` (bytes stored as-is: hashed files/fixtures must not change EOL).
  Git commands run directly from PowerShell on the host; no devbridge needed.
- Earlier release run (14 Oct, after UX pass): 177 PASSED, 4 SKIPPED (PostgreSQL not configured in that shell);
  T001–T100: 96 PASSED / 4 NOT_RUN. Owner approved re-hashing `AGENTS.md` (orientation header) in
  `docs/HANDOFF_INVENTORY.json`. T094 PASSED with fresh browser evidence; e2e 21/21; check all PASSED. V03: 9 PASSED, 5 PARTIAL,
  2 EVIDENCE_RECORDED (V03-01 Git, V03-25 release), 6 DEFERRED_MODEL, 3 NOT_RUN.
- 14 Oct UX pass: boot splash, loading/error/not-found states with retry, phone/tablet bottom tab bar (≤860px),
  charts drawn at on-screen width (12px labels, collision-free dates), compact metrics ≤520px, custom file
  picker, owner-facing dates as "Thu 8 Oct" in server texts (`cases._day`), favicon. Verified on a throwaway
  workspace (`scripts.serve --directory <temp>` on 8091) because the dev token must not be read by Claude.
- Codex documentation sync (14 Oct, code HEAD `d3e24b6`): fresh product E2E 21/21;
  focused v0.3 tests 11 PASSED / 1 FAILED (WinError 32 during background-test SQLite
  cleanup), isolated rerun 1 PASSED. Cleanup instability remains unresolved. First
  restricted-shell attempt failed setup (loopback WinError 10013); raw runs retained
  as `artifacts/v03/codex-sync-*.json`. Browser evidence matches 6/6 web hashes and
  11/11 screenshot paths. No new full/PG/LIVE run; release matrix not regenerated.
- New approvals have 24-hour real-time TTL; legacy approvals without an `approval_ttl`
  record retain business-clock expiry. Case UI references are not all semantically
  verified: compose_task treats case_id as a hint and ignores action_id without plan_id.
- Open: V03-07 server filters for agent reads, V03-21 unrelated-change
  tolerance, V03-22 isolation/backup, alerts ack/debounce, migrate `/legacy` tools (allocation, raw CSV),
  usability study. Strata connection/scenario evidence does not close the LIVE acceptance gates.
- Plans/decisions: `docs/V03_PLAN.md`, `docs/adr/0005-v03-owner-main-path.md`, `docs/KNOWN_LIMITATIONS.md`.
