# Current W01–W36 implementation assessment

Actual test evidence: artifacts/regression-agent-data-v3.json; browser evidence: artifacts/browser-smoke.json.

| Task | Status | Code | Result / remaining work |
|---|---|---|---|
| W01 | VERIFIED | docs/HANDOFF_INVENTORY.json; tests/test_governance.py | Original handoff hashes checked; no Git metadata |
| W02 | VERIFIED | docs/adr/0001-local-milestone.md; docs/adr/0002-product-continuation.md; docs/adr/0003-postgresql.md | Explicit stack/money/time/access decisions |
| W03 | PARTIAL | pyproject.toml; requirements.lock; scripts/check.py; .github/workflows/ci.yml | Local checks ran; remote CI NOT_RUN |
| W04 | PARTIAL | finance/store.py; finance/postgres.py; tests/test_postgres.py | Membership + restricted DB logins/RLS verified; worker shares tenant role |
| W05 | VERIFIED | finance/migrations; finance/postgres/001_core.sql; tests/test_domain.py | Both actual stores exercise core entities and financial checks |
| W06 | VERIFIED | finance/store.py; finance/ingestion.py; tests/test_domain.py | Source bytes, hashes, immutable versions, observed cutoffs |
| W07 | VERIFIED | finance/workspace.py; finance/api.py; web/app.js; tests/test_workspace.py | CSV review correction/discard and browser review verified; fixed CSV schema scope |
| W08 | VERIFIED | finance/ingestion.py; finance/store.py; finance/migrations/004_policy_time.sql; tests/test_policy_history.py; tests/test_postgres.py | Observed/effective fact cutoffs and historical policy selection verified; unknown legacy policy times fail historical recomputation explicitly |
| W09 | PARTIAL | finance/ingestion.py; web/app.js; tests/test_domain.py | Exact/partial manual allocations verified; calibrated fuzzy matching absent |
| W10 | VERIFIED | finance/execution.py; finance/domain.py; tests/test_execution.py | Minor-unit balances, active reserves, provider holds, balanced settlement ledger |
| W11 | PARTIAL | sandbox/world.py; sandbox/server.py; finance/adapter.py | Separate process/DB and capability boundary verified; OS private-file isolation missing |
| W12 | VERIFIED | scripts/runtime.py; sandbox/world.py; tests/test_evaluator_deadlines.py | Fresh golden and independent cash/debt/deadline oracle verified |
| W13 | PARTIAL | finance/compute.py; finance/workspace.py; web/app.js | Cash/overdue/outstanding and quality UI verified; richer aging/concentration not implemented |
| W14 | VERIFIED | finance/compute.py; tests/test_domain.py | F0 deterministic calendar, money and evidence |
| W15 | VERIFIED | finance/compute.py; finance/validation.py; tests/test_workspace.py | Uncalibrated delays, partial receipts, shared-customer shocks; no learned probabilities |
| W16 | VERIFIED | finance/compute.py; finance/ingestion.py; tests/test_domain.py | Immutable observed DEMO catalog and PASS/FAIL/UNKNOWN screening |
| W17 | VERIFIED | finance/compute.py; tests/test_domain.py | Net proceeds, charges, interest, repayment tail; execution limited to DEMO loans |
| W18 | VERIFIED | finance/planner.py; tests/test_planner.py | Actual OR-Tools finite-grid compiler, objectives and prefix constraints; oracle comparison |
| W19 | VERIFIED | finance/validation.py; tests/test_planner.py; tests/test_domain.py | Independent validation, timeout UNKNOWN, no false OPTIMAL |
| W20 | PARTIAL | finance/contingency.py; finance/execution.py; tests/test_contingency.py | DAG, what-if and observed conditional extension verified; arbitrary branching remains |
| W21 | VERIFIED | finance/execution.py; tests/test_execution.py; tests/test_workflows.py | Exact canonical payload/expiry/revoke and stale-command refresh tested |
| W22 | VERIFIED | finance/execution.py; finance/worker.py; tests/test_postgres.py | Atomic reserves/outbox/jobs; SQLite and PostgreSQL concurrency tested |
| W23 | VERIFIED | finance/worker.py; finance/hooks.py; tests/test_webhook.py; tests/test_execution.py | Leases/status lookup/reconciliation and HMAC internal webhook duplicates tested |
| W24 | VERIFIED | finance/execution.py; tests/test_execution.py | Kill switch, partial execution, UNKNOWN and safe recovery |
| W25 | VERIFIED | finance/agents.py; finance/agent_data.py; finance/workflows.py; contracts/agent-tools-v2.json; tests/test_agent_data.py | Typed scoped business readers, full calculations, what-if, selected action and conditional extension proposals; no send/approve/shell/SQL |
| W26 | PARTIAL | finance/workflows.py; tests/test_agent_data.py; tests/test_workflows.py; tests/test_postgres.py | Persistent LangGraph with exact visible record/plan/action pairs, selected-action replan, mandatory separate approval and single-action reconciliation; expanded live verification tracked separately from historical 8/10 baselines |
| W27 | PARTIAL | finance/gateway.py; tests/test_gateway.py; scripts/local_llm.py; scripts/resource_guard.py; scripts/live_compare.py | Expanded Qwen14B local evaluation:20 distinct cases/21 attempts,8 strict passes; assistant review6 complete/5 partial/7 failed/2 RAM-interrupted scenarios. Q8/Q4 cache profiles separate; guards retained. Supplementary browser cash/date correct but source ID mislabelled. Historical7B/8B scores not comparable. See LOCAL_14B_RESULTS.md |
| W28 | PARTIAL | finance/workspace.py; finance/store.py; tests/test_documents.py | ACL/version/source retrieval and report links verified; semantic retrieval/evidence benchmark absent |
| W29 | PARTIAL | web/index.html; web/app.js; web/style.css; artifacts/browser-smoke.json | Ten functional routes and browser flows verified; standalone E2E runner/accessibility matrix absent |
| W30 | PARTIAL | finance/parser.py; finance/workspace.py; tests/test_documents.py | Text PDF extraction/indexing/injection test verified; OFD/XML/OCR/OS parser isolation absent |
| W31 | PARTIAL | finance/contingency.py; finance/workflows.py; finance/execution.py | Observed event replan and send rechecks verified; generalized debounce/internal alerts absent |
| W32 | PARTIAL | scripts/test.py; tests; artifacts/regression-agent-data-v3.json | T001–T100 tracked; unresolved targets stay NOT_RUN; no blanket completion claim |
| W33 | PARTIAL | scripts/benchmark.py; artifacts/benchmark.json | Three paired deterministic sensitivity runs; diverse synthetic/live B1/B2/B3 absent |
| W34 | PARTIAL | docs/data_cards/synthetic.md; docs/model_cards/local-gateway.md; scripts/licenses.py; docs/SECURITY.md | Actual metadata inventory; source rights/real model licenses not inferred |
| W35 | VERIFIED | README.md; docs/architecture/README.md; docs/runbooks; docs/submission/demo-script.md | English runnable instructions and boundaries updated; final contest media outside product deliverable |
| W36 | PARTIAL | scripts/rehearse.py; artifacts/rehearsal.json | Fresh code/venv/wheels/DB golden verified; no Git repository/release tag/remote CI |
