# CLAUDE.md — orientation map (read this first, then only what the task needs)

<!-- MEDIUM-120-20261020-START -->
> **Latest 20 Oct: current-code Qwen medium120 COMPLETE, production unchanged.** Same120 EN/ZH cases/system/tools/budgets/service instance as latest none; only think/strata_reasoning_effort differ. **89/100 +7/20 strict PASS**, versus none88+5 and historical medium92/100. Main100 p50/p95 **32.787/56.647s**, new20 **46.804/77.503s**;379 model calls vs629 none. Four new output truncations at2048 tokens; max159.518s. One expected AUDITOR pre-model POLICY_DENIED, no network run errors. All120 semantically reviewed: main100 81 COMPLETE/8 MINOR/5 PARTIAL/6 FAILED, joint strict+COMPLETE78; new20 5/6/2/7, joint3. Not independent accountant/holdout. Typed rendering and automatic PASS do not prove all prose.
>
> Confirmed gaps: missed capabilities/multiple scenarios/history, wrong Chinese transaction-to-obligations routing, repeated reads/output budget, omitted full-detail/status reads, filtered absence overclaims, field/value confusion. `clarification_ru` suggests adjusting reserve after INFEASIBLE; no mutation but text-safety issue untested by state assertions. No production fix in this task. All recorded state safety passes;18/18 tools29/29 datasets. All frozen source hashes unchanged during one120-case segment; evaluator exit0/no PID, postflight same Strata ready. Runtime metadata is not weight/license proof.
>
> Fresh7 target tests/static9/report lint/types/format/final integrity PASS. Full regression/E2E/PG/UI/LIVE payment lifecycle NOT_RUN this iteration (366PASS/4PG SKIP and23MOCK E2E historical). Cabinet neither restarted nor switched to medium. `scripts/release_eval.py` now requires explicit `--reasoning none|medium`; tests add explicit-mode/comparability assertions. Start `docs/QWEN_MEDIUM_120_20261020_RU.md`, answers of same prefix, `artifacts/release-medium-120-20261019/{summary,diagnostics,narrative-review,final-audit,manifest}.json`. Reproduce `python -m analysis.release_medium_report --final`. Older none report generator is frozen to the previous runner; do not rerun it on current hashes. OPEN-12/submission HOLD remain. Blocks below are historical.
<!-- MEDIUM-120-20261020-END -->

<!-- RELEASE-120-20261019-START -->
> **Baseline clarification:** historical **92/100 is reasoning=medium**; historical87/current88 are reasoning=none. At that previous stage current-code medium was NOT_RUN (now completed in 20 Oct block above); do not present 92→88 as an isolated code regression. Latest benchmark retained none from health-series configuration, not the historical best strict-score profile. See `artifacts/release-eval-20261019/baseline-clarification.json` (9 losses/5 gains versus historical medium; otherwise same case definitions/budget).

> **Latest 19 Oct: full selected-Qwen release evaluation COMPLETE, production unchanged.** Frozen current code, original100 + author-created new20 EN/ZH, Strata `qwen3.8-flash-next-iq3_xxs`, reasoning none/same budgets/no fallback. **88/100 strict PASS** (historical87), **5/20 new strict PASS**; p50/p95 old 100: 35.331/77.573s, new 20: 67.634/90.032s; 629 model calls;119 tasks reach model +1 AUDITOR pre-model policy denial. All120 semantic reviews: old 100: 78 COMPLETE/7 MINOR/5 PARTIAL/10 FAILED, joint strict+COMPLETE74; new 20: 3 COMPLETE/3 MINOR/6 PARTIAL/8 FAILED, joint1. **Do not treat strict PASS or workflow COMPLETE as prose correctness.** New paraphrases expose intent completeness, wrong transactions/obligations routing, premature HEALTH_EVIDENCE_COMPLETE, omitted capabilities/history/scenarios; generic field/value/control/source confusion, placeholder clarification and scoped-empty-search errors remain. Some correct document explanations fail the frozen source-ID citation criterion; primary grades preserved. 18/18 tools, 29/29 datasets, recorded safety all pass, guards/approvals unchanged. Harness-only recovery: 2+65+53 disjoint primary outcomes, last segment COMPLETED/evaluator exit0/postflight same Strata; no failure replacement. Five new target tests PASS, static9 and report lint/types/format PASS; full regression/E2E/PG/UI/LIVE payment lifecycle NOT_RUN this iteration. Prior 366 PASS / 4 PG SKIP, E2E 23 MOCK remain historical. Start `docs/QWEN_RELEASE_120_20261019_RU.md`, full answers of same prefix, `artifacts/release-eval-20261019/summary.json`/narrative-review/final-audit/manifest. `python -m analysis.release_report --final` checks all120 primary/review hashes and frozen code. New files scripts/release_eval.py, release_challenge_scenarios.py, tests/test_release_eval.py, analysis/release_report.py. OPEN-12/submission HOLD remain. Runtime metadata is not weight/licence proof; new20 is not independent external holdout. Historical blocks below are superseded for current evaluation.
<!-- RELEASE-120-20261019-END -->

<!-- HEALTH-MIXED-FIX-20261019-START -->
> **Latest 19 Oct: mixed-health correction complete.** `health-answer-v2`, new `finance/health_tasks.py`, `health_answers.py`/`workflows.py`: require every requested subtask, full entity/document pages, distinct scenarios, matched search query, capabilities and current health before validated MIN_COST candidate. Field-bound counterparty/outstanding/history/current/loan-cash semantics; no numeric-guard change or new authority. Unsupported planning stays general; unrequested mixed sections reject safely. Same 20 challenge EN/ZH, same Qwen/Strata reasoning none/budget/grader: final v3 **19/20 strict PASS; all 20 reviewed, 19 COMPLETE; joint 19/20**, versus original 6 strict / 5 joint. p50 38.606s / p95 47.221s / 85 calls. One primary MODEL_UNAVAILABLE from bridge interruption remains FAILED; separate recovery PASSED/COMPLETE, successful unique cases including recovery 20/20. System-rendered typed quality, not arbitrary model prose or holdout. **38 targeted PASS; full 366 PASS / 4 PG SKIP; E2E 23 MOCK; static 9; T001–100: 95 PASS / 5 NOT_RUN.** Guards unchanged, recorded safety all passed; financial state/facts/company/world unchanged. No cabinet restart/PG/pixelUI/LIVE100/500/LIVE payment lifecycle. Preserved diagnostic 10 and full v2 before final v3; never replace failures. Start `docs/BUSINESS_HEALTH_MIXED_FIX_20261019_RU.md`, answers of same prefix, ADR 0009, `contracts/RUNTIME.md`, `tests/test_health_mixed.py`. Final artifacts `artifacts/health-challenge-fix-20261019/health-challenge-fix-20261019-v3-combined.json`, summary/review/audit; report command `python -m analysis.health_mixed_report` checks exact frozen code and past evidence. Old generators are historical-source-bound. OPEN-12 remains for independent holdout/general prose/unseen mixed requests; submission HOLD remains. Blocks below are historical.
<!-- HEALTH-MIXED-FIX-20261019-END -->

<!-- HEALTH-CHALLENGE-20261019-START -->
> **Latest 19 Oct: NEW health challenge measured, no production fix.** Twenty new paired EN/ZH complex/paraphrased tasks on unchanged selected Qwen/Strata reasoning none, same budget: **6 strict PASS / 14 FAIL; reviewed all20: 5 COMPLETE / 5 PARTIAL / 10 FAILED, joint success5/20**. Prior20/20 is the old bounded development suite only. Six unbound-digit refusals; one corrupted document ID then malformed empty tool arguments exhausted repair; three delivered entity/field/history errors; five incomplete tasks. `health_answers.intent/ready` can close tools before second scenario, Chinese plan/search/authority explanation; generic prose still swaps beneficiary/counterparty, old/current, invoice/receivable. OPEN-12 and submission HOLD remain. Recorded safety all passed; financial records/facts/company/world unchanged; no leaks. Retrieval challenge coverage must distinguish skipped searches/unread docs. Failed workflow has empty state but durable tool events: new reporting counts event errors/coverage, preserves original strict grades. p50all60.707s/p9584.164s;119 model calls;11 tools/6 list datasets. New offline5/5 and lint/types/format PASS. Full regression/E2E/PG/UI/LIVE100/500 NOT_RUN this iteration. All prior production/source hashes unchanged; only new `scripts/health_challenge_{scenarios,eval}.py`, `tests/test_health_challenge_eval.py`, `analysis/health_challenge_report.py`, artifacts/docs. Start with `docs/BUSINESS_HEALTH_CHALLENGE_20261019_RU.md`; all answers/design of same prefix. Data `artifacts/business-health-challenge-20261019/summary.json`, raw `health-challenge-20261019-primary.json`, preregistration/review/final-audit/manifest. Reproduce report with `python -m analysis.health_challenge_report`; use unique future output/workspace names. No model/cabinet restart, no source fixes or retry substitution. Blocks below are historical.
<!-- HEALTH-CHALLENGE-20261019-END -->

<!-- HEALTH-ANSWER-FIX-20261019-START -->
> **Latest 19 Oct: health answer correction measured.** `finance/health_answers.py` (`health-answer-v1`) provides bounded EN/ZH typed presentation: LIVE Qwen selects tools, report sections and observed IDs; server binds financial labels/values, snapshot identity, null/status/scope through unchanged `answers.render`. Integration in `answers.context` / `workflows`: complete required reads before terminal selection, same bounded repairs, invalid selection remains PARTIAL. No financial prose/numbers/authority accepted in selection. Model trust explicitly `SERVER_RENDERED_HEALTH_FROM_OBSERVED_TOOLS`. No new action authority or DB migration. Six previously incomplete and three semantically wrong outcomes fixed on the same development suite: **20/20 strict PASS, EN10/ZH10, all 20 delivered answers reviewed COMPLETE**. This is system presentation quality, not free model prose; original baseline preserved. Full-case p50 **24.135s**, p95 **51.928s**, 74 model requests; same cases/budget/grader/selected Qwen reasoning none. **16 new target PASS; full344 PASS/4 PG SKIP; E2E23/23 MOCK; static9/9; T001–T10095 PASS/5 NOT_RUN.** No LIVE100/500, PG, pixel UI or LIVE payment-lifecycle rerun. Existing cabinet not restarted. OPEN-12 remains for independent holdout, paraphrases/routing and broader questions; EN/ZH routing is heuristic. Submission HOLD for release/access/PDF remains. Read `docs/BUSINESS_HEALTH_FIX_20261019_RU.md`, ADR0008, `contracts/RUNTIME.md`, `tests/test_health_answers.py`; measured results/answers in `artifacts/business-health-fix-20261019/summary.json` and `docs/BUSINESS_HEALTH_FIX_ANSWERS_20261019_RU.md`. Reproduce with `python -m analysis.health_answer_fix_report`; it verifies frozen source hashes and baseline configuration. New LIVE outputs must use fresh paths. Old report generator is tied to old frozen code and should not be rerun on current sources. Preserve old diagnostic and final artifacts. Blocks below are historical.
<!-- HEALTH-ANSWER-FIX-20261019-END -->

<!-- BUSINESS-HEALTH-20261019-START -->
> **Latest 19 Oct: Business health agent integration implemented (AUD-05 / OPEN-11).** Shared `analysis-v2` / `business-health-v1` in metrics, baseline forecast and what-if; capability discovery, source-linked saved calculation reads and Copilot card. Versions `agent-tools-v5`, `compute-v3`; no new action authority or DB migration. New tests: 17 PASS; full regression **328 PASS / 4 PG SKIP**, E2E23/23 MOCK, static9/9, T001–T10095 PASS/5 NOT_RUN. Selected Qwen/Strata reasoning none: **20/20 EN/ZH completed, 14 strict PASS / 6 FAIL**; all 20 narratives reviewed: **11 COMPLETE / 2 PARTIAL / 7 FAILED**. Exact tool values/safety passed; prose still fails reference formatting or confuses old/current, null/zero and field scopes (OPEN-12). All-case p50 62.361s/p95 84.247s. No benchmark alternative/default switch. Settlement execution/worker/validator/payload-check hashes unchanged. See `docs/BUSINESS_HEALTH_AGENT_20261019_RU.md`, `docs/BUSINESS_HEALTH_ANSWERS_20261019_RU.md`, `artifacts/business-health-20261019/summary.json`. Reproduce summary with `python -m analysis.business_health_report`; new LIVE runs require fresh output paths. Earlier partial diagnostic11 retained; not a full comparable baseline. PG/pixel UI/LIVE payment lifecycle NOT_RUN. Submission HOLD remains for narrative/release/access/PDF issues. Historical counters below are superseded for this stage.
<!-- BUSINESS-HEALTH-20261019-END -->

<!-- SUBMISSION-AUDIT-20261019-START -->
> **19 Oct follow-up: K15/AUD-01 fixed for synthetic sandbox** on working-tree patch over d3764f0. Settlement requires exact stable key, known ref, signed amount, counterparty and obligation reference. Durable tenant-scoped `settlement_issue` keeps reserves, stops sends and blocks resume even when cash matches; no force-clear/resolution API or historical repair. Alerts/timeline explain the discrepancy. Fresh checks: 15/15 targeted, **311 PASS / 4 PG SKIP** regression, T001–T100 95 PASS / 5 NOT_RUN, HTTP E2E 23/23 MOCK, golden 5/5 delta 0, static 9/9. See `docs/SETTLEMENT_FIX_20261019_RU.md`, `contracts/RUNTIME.md`, ADR 0006, `artifacts/settlement-fix-20261019/`. Prior failure evidence in `artifacts/submission-audit-20261019/` is retained. Model and approvals unchanged. Overall submission HOLD remains for other audit findings: health narrative quality, release/access and PDF packaging. Prior audit recorded private repo and open PR #4; not rechecked remotely by this fix. Historical counters below are not latest readiness.
<!-- SUBMISSION-AUDIT-20261019-END -->

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
