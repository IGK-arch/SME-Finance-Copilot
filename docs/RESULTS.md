# Actual local product results

Generated from real artifacts at 2026-10-13T00:24:00.096489+00:00.

Unittest checks: 163; outcomes: {'PASSED': 163}.
Acceptance targets, including current recorded browser evidence: {'PASSED': 96, 'NOT_RUN': 4}.
Supplemental browser records verified against web hashes: 1.

These are synthetic/local checks, not real-agent or Chinese-SME quality metrics.

Independent golden world result:

```json
{
  "evaluator_version": "world-ledger-oracle-v2",
  "data_mode": "synthetic",
  "final_cash_minor": 2800000,
  "arithmetic_cash_minor": 2800000,
  "minimum_cash_minor": 2000000,
  "remaining_payables_minor": 0,
  "remaining_debt_minor": 0,
  "movement_count": 6,
  "missed_deadlines": [],
  "success": true
}
```

Reconciliation: RECONCILED; discrepancy_minor=0.

Quality commands actually run:

- `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff\.venv\Scripts\python.exe -m compileall -q finance sandbox scripts tests` — PASSED
- `node --check web/app.js` — PASSED
- `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff\.venv\Scripts\python.exe -m ruff check finance sandbox scripts tests --select E9,F63,F7,F82,F401,F841` — PASSED
- `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff\.venv\Scripts\python.exe -m mypy finance sandbox scripts --check-untyped-defs` — PASSED
- `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff\.venv\Scripts\python.exe -m ruff format --check finance sandbox scripts tests` — PASSED

Live local-model evidence is recorded separately in docs/model_cards/local-gateway.md; it is not counted as a unittest or production-quality metric. B1/B2/B3 ablations: **NOT_RUN**.
Production banking, real data, legal/competition refresh, external CI and release tag: **NOT_RUN**.

See KNOWN_LIMITATIONS.md, SECURITY.md, ITERATIONS.md and the full machine report.

| Target | Actual status | Executed implementation / reason |
|---|---|---|
| T001 | PASSED | tests.test_domain.DomainTests.test_T001_balanced_import |
| T002 | PASSED | tests.test_domain.DomainTests.test_T002_file_repeat |
| T003 | PASSED | tests.test_domain.DomainTests.test_T003_provider_namespaces |
| T004 | PASSED | tests.test_domain.DomainTests.test_T004_tenant_namespaces |
| T005 | PASSED | tests.test_domain.DomainTests.test_T005_quarantine |
| T006 | PASSED | tests.test_domain.DomainTests.test_T006_unsupported_schema |
| T007 | PASSED | tests.test_domain.DomainTests.test_T007_partial_allocation |
| T008 | PASSED | tests.test_domain.DomainTests.test_T008_one_payment_many |
| T009 | PASSED | tests.test_domain.DomainTests.test_T009_overallocation |
| T010 | PASSED | tests.test_domain.DomainTests.test_T010_overpayment_preserved |
| T011 | PASSED | tests.test_domain.DomainTests.test_T011_unmatched_cash |
| T012 | PASSED | tests.test_domain.DomainTests.test_T012_red_invoice_link |
| T013 | PASSED | tests.test_domain.DomainTests.test_T013_merchant_bridge |
| T014 | PASSED | tests.test_domain.DomainTests.test_T014_currency_and_integer |
| T015 | PASSED | tests.test_domain.DomainTests.test_T015_rounding |
| T016 | PASSED | tests.test_domain.DomainTests.test_T016_late_observation |
| T017 | PASSED | tests.test_domain.DomainTests.test_T017_version_preserved |
| T018 | PASSED | tests.test_domain.DomainTests.test_T018_incomplete_statement |
| T019 | PASSED | tests.test_domain.DomainTests.test_T019_conflict_review |
| T020 | PASSED | tests.test_domain.DomainTests.test_T020_order_independence |
| T021 | PASSED | tests.test_domain.DomainTests.test_T021_invoice_not_cash |
| T022 | PASSED | tests.test_domain.DomainTests.test_T022_residual_deduplication |
| T023 | NOT_RUN | No trained survival dataset/model in this milestone |
| T024 | PASSED | tests.test_domain.DomainTests.test_T024_overdue_conditional_fallback |
| T025 | PASSED | tests.test_domain.DomainTests.test_T025_partial_forecast |
| T026 | PASSED | tests.test_domain.DomainTests.test_T026_shared_customer_shock |
| T027 | PASSED | tests.test_domain.DomainTests.test_T027_intraday_ordering |
| T028 | PASSED | tests.test_domain.DomainTests.test_T028_repayment_tail |
| T029 | PASSED | tests.test_domain.DomainTests.test_T029_sparse_label |
| T030 | PASSED | tests.test_domain.DomainTests.test_T030_probability_label |
| T031 | NOT_RUN | No training/temporal-validation pipeline; observed cutoff is covered by T016 |
| T032 | NOT_RUN | No training/company-holdout pipeline or downloaded dataset |
| T033 | PASSED | tests.test_domain.DomainTests.test_T033_snapshot_cache_key |
| T034 | PASSED | tests.test_domain.DomainTests.test_T034_pnl_blocked |
| T035 | PASSED | tests.test_domain.DomainTests.test_T035_metric_evidence |
| T036 | PASSED | tests.test_domain.DomainTests.test_T036_eligibility_unknown |
| T037 | PASSED | tests.test_domain.DomainTests.test_T037_eligibility_fail |
| T038 | PASSED | tests.test_domain.DomainTests.test_T038_late_finance |
| T039 | PASSED | tests.test_domain.DomainTests.test_T039_net_proceeds |
| T040 | PASSED | tests.test_domain.DomainTests.test_T040_debt_schedule |
| T041 | PASSED | tests.test_domain.DomainTests.test_T041_factoring |
| T042 | PASSED | tests.test_execution.ExecutionTests.test_T042_expired_quote |
| T043 | PASSED | tests.test_domain.DomainTests.test_T043_extension_request_not_fact |
| T044 | PASSED | tests.test_domain.DomainTests.test_T044_application_not_cash |
| T045 | PASSED | tests.test_domain.DomainTests.test_T045_protected_salary |
| T046 | PASSED | tests.test_domain.DomainTests.test_T046_hard_reserve |
| T047 | PASSED | tests.test_domain.DomainTests.test_T047_feasible_status |
| T048 | PASSED | tests.test_domain.DomainTests.test_T048_unknown_status |
| T049 | PASSED | tests.test_domain.DomainTests.test_T049_independent_corruption |
| T050 | PASSED | tests.test_domain.DomainTests.test_T050_no_plan_explained |
| T051 | PASSED | tests.test_contingency.ContingencyTests.test_T051_branch_activates_only_after_observed_confirmation |
| T052 | PASSED | tests.test_domain.DomainTests.test_T052_nonanticipative |
| T053 | PASSED | tests.test_domain.DomainTests.test_T053_dag |
| T054 | PASSED | tests.test_domain.DomainTests.test_T054_no_debt_not_invented |
| T055 | PASSED | tests.test_api.ApiTests.test_T055_what_if_isolated |
| T056 | PASSED | tests.test_execution.ExecutionTests.test_T056_tool_allowlist |
| T057 | PASSED | tests.test_execution.ExecutionTests.test_T057_no_code_argument |
| T058 | PASSED | tests.test_documents.DocumentTests.test_T058_pdf_injection_does_not_grant_tool_or_policy_rights |
| T059 | PASSED | tests.test_execution.ExecutionTests.test_T059_beneficiary_version |
| T060 | PASSED | tests.test_api.ApiTests.test_T060_api_tenant_and_roles |
| T061 | PASSED | tests.test_agent_data.AgentDataTests.test_T061_old_workflow_evidence_is_denied_after_role_change, tests.test_execution.ExecutionTests.test_T061_scoped_retrieval |
| T062 | PASSED | tests.test_execution.ExecutionTests.test_T062_cache_scope |
| T063 | PASSED | tests.test_execution.ExecutionTests.test_T063_bounded_invalid_output |
| T064 | PASSED | tests.test_execution.ExecutionTests.test_T064_wrong_economic_amount |
| T065 | PASSED | tests.test_gateway.GatewayTests.test_T065_steps_tokens_time_and_no_paid_cost_enforced, tests.test_workflows.WorkflowTests.test_T065_step_token_and_context_budgets |
| T066 | PASSED | tests.test_agent_data.AgentDataTests.test_T066_T086_selected_due_action_requires_exact_approval_and_reconciles_once, tests.test_execution.ExecutionTests.test_T066_model_outage_no_bypass |
| T067 | PASSED | tests.test_execution.ExecutionTests.test_T067_fallback_denied |
| T068 | PASSED | tests.test_execution.ExecutionTests.test_T068_no_secrets_in_outputs |
| T069 | PASSED | tests.test_execution.ExecutionTests.test_T069_phrase_not_policy |
| T070 | PASSED | tests.test_execution.ExecutionTests.test_T070_no_approval_promise |
| T071 | PASSED | tests.test_execution.ExecutionTests.test_T071_approval_required |
| T072 | PASSED | tests.test_execution.ExecutionTests.test_T072_revoke_and_expiry |
| T073 | PASSED | tests.test_execution.ExecutionTests.test_T073_payload_hash |
| T074 | PASSED | tests.test_execution.ExecutionTests.test_T074_same_key_payload |
| T075 | PASSED | tests.test_execution.ExecutionTests.test_T075_key_conflict |
| T076 | PASSED | tests.test_execution.ExecutionTests.test_T076_parallel_reserves |
| T077 | PASSED | tests.test_execution.ExecutionTests.test_T077_outbox_survives_restart |
| T078 | PASSED | tests.test_execution.ExecutionTests.test_T078_duplicate_delivery |
| T079 | PASSED | tests.test_execution.ExecutionTests.test_T079_crash_after_send |
| T080 | PASSED | tests.test_execution.ExecutionTests.test_T080_timeout_unknown |
| T081 | PASSED | tests.test_execution.ExecutionTests.test_T081_unknown_keeps_reserve |
| T082 | PASSED | tests.test_execution.ExecutionTests.test_T082_late_settlement_once |
| T083 | PASSED | tests.test_webhook.WebhookTests.test_T083_repeated_signed_webhook_preserves_one_movement_and_ledger_pair |
| T084 | PASSED | tests.test_execution.ExecutionTests.test_T084_terminal_state_not_regressed |
| T085 | PASSED | tests.test_execution.ExecutionTests.test_T085_hold_not_double_counted |
| T086 | PASSED | tests.test_agent_data.AgentDataTests.test_T066_T086_selected_due_action_requires_exact_approval_and_reconciles_once, tests.test_workflows.WorkflowTests.test_T086_graph_resume_exact_approval_worker_and_reconciliation |
| T087 | PASSED | tests.test_execution.ExecutionTests.test_T087_partial_execution_preserved |
| T088 | PASSED | tests.test_execution.ExecutionTests.test_T088_kill_switch_status_continues |
| T089 | PASSED | tests.test_execution.ExecutionTests.test_T089_cancel_keeps_sent_action |
| T090 | PASSED | tests.test_execution.ExecutionTests.test_T090_external_owner_cash |
| T091 | PASSED | tests.test_execution.ExecutionTests.test_T091_source_changes_snapshot |
| T092 | PASSED | tests.test_execution.ExecutionTests.test_T092_refresh_before_send |
| T093 | PASSED | tests.test_api.ApiTests.test_T093_actual_expected_api_and_ui |
| T094 | PASSED | cua.resource_stage_ui |
| T095 | PASSED | tests.test_execution.ExecutionTests.test_T095_fresh_golden |
| T096 | PASSED | tests.test_execution.ExecutionTests.test_T096_evaluator_ignores_agent_text |
| T097 | NOT_RUN | Observation capability is scoped but private files are not OS/container isolated from local administrators |
| T098 | PASSED | tests.test_execution.ExecutionTests.test_T098_same_world_inputs |
| T099 | PASSED | tests.test_governance.GovernanceTests.test_T099_honest_status_report |
| T100 | PASSED | tests.test_governance.GovernanceTests.test_T100_source_manifest_and_dependencies |
