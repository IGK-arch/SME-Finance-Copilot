# Current boundaries and unverified work

The delivered code goes beyond the first milestone, but full P0/product-P1 acceptance
is PARTIAL. Read ACCEPTANCE_MATRIX.md for individual requirements and executed proof.
Historical S0–S6 notes in ITERATIONS.md describe the earlier implementation only.

## v0.3 (13 Oct 2026) — owner main path

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
- Git baseline (V03-01) is not created: the bridged folder disallows deletions that git needs.
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
  Qwen 7B was faster in that historical run. The current experimental UI selects
  Qwen2.5 14B Q3_K_S; completed expanded evaluation has 8/20 strict passes,
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
- The three models and portable runtime occupy approximately 17.0 GiB on E:.
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
- CSV is fixed synthetic-csv-v1 (1 MB/5000 rows), synchronous. Review correction
  and discard work and preserve original evidence. Arbitrary export mapping and
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
  of an unsent RESERVED action, generalized materiality/debounce and internal alert
  inbox remain incomplete. Sent operations are never fictionally cancelled.
- Browser evidence covers this in-app Chromium session, actual APIs, ten routes,
  golden execution/restart, source review/retrieval and policy sensitivity. It is
  recorded CUA automation, not a standalone CI browser runner. Cross-browser,
  screen-reader, accessibility and load/performance audits remain NOT_RUN.
- Development credentials are random secrets in ignored files; no SSO/encrypted
  vault/TLS/public hosting is provided. Keep loopback binding and trusted host access.
- The deterministic comparison uses three starting-cash cases. A diverse linked
  3–5-company world generator, calibrated shocks and live B1/B2/B3 ablations remain.
- Metadata/license inventory is evidence, not a legal opinion. Local model weights were explicitly downloaded; no external
  financial dataset was downloaded. Source rights require owner review. No Git repository,
  remote CI run, release tag, final contest deck/video or current rule/legal review
  was produced. No claim of full product or production readiness is made.
