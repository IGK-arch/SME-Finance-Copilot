# Current boundaries and unverified work

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
SSH <ssh-host>:45161 failed before authentication (missing protocol banner),
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

15 Oct expanded evaluation supersedes earlier history/lookup examples below.
The latest full 74-case run passed 67 strict checks and all recorded safety
checks; text review found additional defects (53 complete, 11 minor, 5 partial,
5 failed). Exact references do not establish the meaning of surrounding prose.
Observed errors include job-done claims on UNKNOWN/done=0, lender approval versus
OWNER payment approval, unsupported causal explanations of NOT_FOUND, optional
quarantine fields, and inconsistent tool-route completion. No general semantic
AnswerBundle/CompletionGate, independent holdout, OCR/large PDF corpus, concurrent
load test or LIVE approval-to-reconciliation target-model gate is completed.

Historical versions are no longer totaled as current debt. Future source lookup
is denied server-side, including known source IDs. Title/Unicode/Chinese search,
matched excerpts, stable pagination and typed observed IDs have regression tests.
Raw CSV source tokens are no longer offered as quoted monetary references.
The v3 rejected-draft repair variant regressed and is superseded by v4 diagnostics
only; final v4 affected-case evidence is `strata-challenge-diagnostics-cases-20261015.json`.
It completed 13 PASS / 2 FAIL (company/policies list omission, rejected delivery
final); 59 other cases were not repeated on v4. It is not a full repeat of 74.
Full details and unsuccessful attempts: `STRATA_CHALLENGE_FIXES_RU.md`.

Older checkpoints follow; their counts and examples describe those versions.


The delivered code goes beyond the first milestone, but full P0/product-P1 acceptance
is PARTIAL. Read ACCEPTANCE_MATRIX.md for individual requirements and executed proof.
Historical S0–S6 notes in ITERATIONS.md describe the earlier implementation only.

15 Oct: `answer-refs-v1` rejects unbound numeric/ID prose and renders exact server
values with one bounded repair and explicit PARTIAL on rejection. Observed-ID
preconditions and a final tool-phase boundary apply server-side. All same 20
Strata cases rerun: **20 PASS / 0 FAIL**; assistant text review **18 COMPLETE / 2 PARTIAL**.
See `STRATA_FINAL_SCENARIOS_20261015_RU.md` and `STRATA_FIXES_20261015_RU.md`.
Reference correctness is narrower than meaning: history may misleadingly sum
versions; an earlier final-writer smoke mislabeled a cash outflow as confirmed
cash. The final stress answer also called a source ID a customer and extrapolated
an unsupported five-day resilience threshold from three tested scenarios.
Those are retained limitations, not hidden by the strict score. No general
semantic validator, independent holdout or LIVE execution acceptance gate closed.
After a recorded proposal or an INFEASIBLE objective, further reads/proposals need
a new user request; arbitrary multi-objective tasks are not a universal completion gate.

## v0.3.0 (14 Oct 2026) — owner main path

- The owner-authorized Strata connection now has synthetic LIVE scenario evidence
  (`STRATA_RESULTS_RU.md`), but model prose contains factor-of-ten amount errors,
  unsupported instructions and incomplete tasks. Strict tool grades do not measure
  answer correctness. No LIVE approval/dispatch E2E or closed holdout was run.
- Strata identity is a fingerprint of model ID, engine version, start time and
  context, not a weight-file SHA256. Remote restarts require a new workflow. The
  SSH bridge is a manual local process; reconnect supervision and production secret
  storage are not implemented. RAM is checked between evaluation cases, not enforced
  as an OS allocation limit. The demo uses a 64000-token task budget; evaluation uses
  128000, so complex tasks may hit the demo budget earlier.

- The new cabinet (Home / Money / Plans / Documents / Activity / Settings, Copilot panel) is
  verified on synthetic data with the MOCK model. No usability study with independent
  participants was run; no Playwright runner exists on this host (package registries blocked);
  browser evidence is a recorded built-in-browser walkthrough (`artifacts/v03/browser-v03.json`).
- LIVE agent items are DEFERRED until the target model: CompletionGate, validation of model
  text against tool results, scoped skills, latency profile, LIVE end-to-end from a free-form
  request, Chinese retrieval holdout. MOCK runs are never counted as LIVE.
- `scripts.e2e_v03` proves the product path through the real server, worker and sandbox
  (changed inputs, exact approvals, lost response, forced restart, no duplicate operation),
  not an agent's decision quality.
- Strategy scope is still a finite product × principal grid with one financing product and fixed
  payable dates; "lowest cost" means lowest within that grid. Infeasibility reasons are diagnostic
  checks, not a minimal infeasibility proof.
- Imported payables for counterparties without a verified beneficiary (and unknown to the sandbox
  world) cannot be paid; settled transactions imported by hand cause a reconciliation mismatch
  against the simulator and stop new sends (by design).
- Alerts are a deterministic projection with first-seen deduplication; no debounce scheduler,
  acknowledgement or notifications.
- Sessions: HttpOnly + SameSite=Strict cookie over loopback HTTP; `Secure` is set only under HTTPS.
  A public deployment still needs TLS, a secret vault and process isolation (V03-22, T097).
- Git baseline and private origin now exist (V03-01); inspected HEAD is `d3e24b6`
  on `main`. No release tag was present. Older no-Git statements are superseded.
- New approvals have a 24-hour real-time TTL. Legacy approvals without an
  `approval_ttl` record keep business-clock expiry only; no blanket TTL migration.
- Context validation in `compose_task` covers plan access, actions within the given
  plan and current obligations. `case_id` currently adds generic case context; an
  `action_id` without `plan_id` is ignored. Do not describe every reference as verified.
- Fresh focused verification: 11 PASSED / 1 FAILED due to WinError 32 at background
  Copilot temporary-DB cleanup; isolated rerun PASSED. The instability is unresolved.
  Fresh product E2E: 21/21 PASSED. See CURRENT_STATE_RU.md and codex-sync reports.
- The worker re-records an unchanged operation status on every poll; Activity collapses these
  repeats for display, the audit log keeps them.

- Agent-tools-v2 now exposes scoped, paginated business details and full saved
  calculation results. Real plan/action IDs and exact selected-action preparation
  are implemented; unread, invented and mismatched pairs are rejected. SQLite and
  PostgreSQL checks cover permissions, historical facts, pagination and mandatory
  approval. Tool coverage does not imply perfect local-model use. See
  AGENT_CAPABILITIES.md and the latest platform-suite evidence.
- Historical local CPU evaluation covers ten synthetic tasks per model:
  Qwen2.5 7B and Granite 3.3 8B each passed 8/10 strict tool/state cases.
  Qwen 7B was faster in that historical run. The earlier experimental UI selected
  Qwen2.5 14B Q3_K_S; v0.3 defaults to MOCK. Historical expanded evaluation has 8/20 strict passes,
  with 6 complete /5 partial /7 failed /2 RAM-interrupted scenarios in assistant
  review. See LOCAL_14B_RESULTS.md. The additional browser probe confused snapshot
  and source IDs. Missing tool calls, invented IDs and final-answer timeouts remain.
  Language, citation, amount-unit and approval-response errors remain in prose;
  strict passes are not narrative correctness. That prior code omitted action IDs;
  Qwen attempted invented IDs, which the server rejected. The omission is fixed in
  agent-tools-v2; those old results are not measurements of the expanded tool set.
  See LIVE_MODEL_RESULTS.md and separate assistant narrative reviews. The Granite
  adapter was corrected after its baseline and Qwen results reused; this is
  iterative development evaluation, not held-out/repeated performance evidence.
- The historical three-model/runtime footprint was approximately 17.0 GiB on E:
  (not remeasured during this documentation sync).
  The expanded 14B run hit the unchanged 5 GiB free-RAM guard three times despite
  sufficient disk space. Disk capacity and available RAM are separate constraints;
  actual footprint and inference outcomes are in AGENT_PLATFORM_RESULTS.md. CPU-only mapped weights avoid the
  failed GPU profile and extra repacked weights. The 2 GiB job limit bounds private
  committed memory, not total physical RAM; disk polling is not a filesystem quota.
  C: briefly fell to 0.77 GiB in the failed GPU attempt and recovered after shutdown;
  its precise temporary allocation source is unresolved. Windows pagefile settings
  were not changed. Resource thresholds can stop inference; no live-to-mock fallback.
- PostgreSQL 18.6 financial storage/RLS/restricted login tests ran locally. SQLite
  remains supported. LangGraph checkpoints stay in scoped SQLite files. API and
  worker share a tenant DB role; worker-only grants, connection pooling, multi-host
  failover, production migration rehearsal and PostgreSQL checkpoints remain open.
- Private simulator future events are absent from observation/model tools. The
  simulator is a separate process/database with scoped capabilities, but local OS
  administrators and the development user can read both files. T097 / I24 / full
  I28 deployment isolation are not complete. No container boundary was deployed.
- The v0.3 CSV/XLSX wizard maps two templates (transactions, obligations) to
  synthetic-csv-v1; limits remain 1 MB/5000 rows. XLSX reads the first worksheet
  and stored values, with no formula evaluation. Preview, mapping, versioned
  correction and quarantine retain provenance. Arbitrary financial formats and
  durable asynchronous import/parser jobs are not implemented.
- Text and text PDF extraction/retrieval work. PDF limits: 500 KB, 30 pages,
  200000 extracted characters and a 20-second subprocess timeout. OCR, OFD, XML,
  malware scanning and OS-level parser memory limits remain unsupported. Retrieval
  is lexical with tenant/role/version/cutoff filtering, not semantic embeddings.
- F0 and F1 partial/delayed/customer-correlated receipt scenarios are uncalibrated
  assumptions. No trained survival model, temporal/company holdout or real risk/ROI
  metrics exist (T023/T031/T032). These research pipelines are P2.
- CP-SAT solves a finite, disclosed DEMO product/principal grid, with independent
  validation and exhaustive-oracle comparisons. It does not optimize arbitrary
  negotiated multi-step credit instruments. Factoring/merchant bridges have math
  helpers; only DEMO bridge loans have end-to-end execution. Eligibility is not
  lender approval. Price/terms sources are synthetic, not scraped bank offers.
- Conditional supplier extension is implemented: pending branch is non-executable;
  confirmed observation versions the due date and triggers replan. General-purpose
  arbitrary branching, causal reminder effects and real creditor messaging remain.
- Snapshot facts use observed/effective cutoffs and saved objects remain immutable.
  New policy versions are timestamped at server observation; historical selection
  is tested. Legacy policies with unknown times explicitly block historical
  recomputation instead of receiving invented dates. Statutory accounting/tax/FX/P&L
  are unsupported; the ledger is operational only.
- Durable worker leases, atomic outbox, UNKNOWN recovery and signed internal sandbox
  webhook ingestion are tested. The simulator normally polls, not auto-pushes. No
  external bank webhook contract is claimed. Automatic safely reviewed cancellation
  of an unsent RESERVED action, generalized materiality/debounce and acknowledged
  alert inbox remain incomplete. The v0.3 first-seen projection is implemented.
  Sent operations are never fictionally cancelled.
- Historical v0.2 browser evidence covers an in-app Chromium session, actual APIs, ten routes,
  golden execution/restart, source review/retrieval and policy sensitivity. It is
  recorded CUA automation, not a standalone CI browser runner. Cross-browser,
  screen-reader, accessibility and load/performance audits remain NOT_RUN.
- Development credentials are random secrets in ignored files; no SSO/encrypted
  vault/TLS/public hosting is provided. Keep loopback binding and trusted host access.
- The deterministic comparison uses three starting-cash cases. A diverse linked
  3–5-company world generator, calibrated shocks and live B1/B2/B3 ablations remain.
- Metadata/license inventory is evidence, not a legal opinion. Local model weights were explicitly downloaded; no external
  financial dataset was downloaded. Source rights require owner review. Git exists;
  a remote CI run, release tag, final contest deck/video and current rule/legal
  review remain unverified or absent. No claim of full product or production readiness is made.
