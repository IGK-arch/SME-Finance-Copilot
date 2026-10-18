# Acceptance matrix v0.3 — V03-01…V03-25

Generated from `artifacts/v03/regression-v03.json` (started 2026-10-18T14:50:31.254959+00:00, 278 tests: {'PASSED': 274, 'SKIPPED': 4}).
IDs and wording come from the v0.3 audit package; T001–T100 remain in ACCEPTANCE_MATRIX.md (current counts {'PASSED': 96, 'NOT_RUN': 4}).
DEFERRED (target model) items are model-dependent and are not counted as passed from MOCK runs.

| ID | Priority | Requirement | Status | Evidence | Note |
|---|---|---|---|---|---|
| V03-01 | R0 | Baseline, Git and hashes | EVIDENCE_RECORDED | artifacts/v03/baseline-regression.json<br>artifacts/v03/baseline/ |  |
| V03-02 | R0 | Health backend label and status docs | PASSED | test_V03_02_health_reports_actual_backend |  |
| V03-03 | R0 | CompletionGate: 'I will do it' is not COMPLETE | DEFERRED (target model) | — |  |
| V03-04 | R0 | Typed AnswerBundle/evidence for model answers | DEFERRED (target model) | — | UI shows server-typed result cards with evidence refs; model-text validation deferred |
| V03-05 | R0 | Result-first UI: computation visible without narrative | PASSED | test_V03_05_background_copilot_shows_results_without_narrative |  |
| V03-06 | R0 | Skills and scoped tools reduce steps | DEFERRED (target model) | — |  |
| V03-07 | R0 | SQL filters/pagination for agent reads | NOT_RUN | — |  |
| V03-08 | R0 | Model latency profiling | DEFERRED (target model) | — |  |
| V03-09 | R0 | Financial case keeps context; no second ledger | PASSED | test_V03_09_case_closes_honestly_when_gap_disappears_from_data<br>test_V03_09_case_records_changes_and_context_roundtrip |  |
| V03-10 | R0 | Home redesign names problem, date, next action | PARTIAL | test_V03_10_V03_17_home_names_problem_date_next_action_and_dedups_alerts<br>v03_owner_main_path | 30-second usability test with participants not run |
| V03-11 | R0 | Plans: executable / conditional / infeasible with gross/net/repayment/scenario scope | PASSED | test_V03_11_options_show_executable_conditional_and_infeasible_reasons<br>v03_owner_main_path |  |
| V03-12 | R0 | Exact approval and timeline; UNKNOWN has no blind retry | PASSED | test_V03_12_review_approve_exact_payload_timeline_and_lost_response<br>v03_owner_main_path<br>artifacts/v03/e2e-latest.json (passed) |  |
| V03-13 | R0 | Planner objectives: PRESERVE distinct, HIGHER with target/price trade-off | PASSED | test_V03_13_strategies_are_distinct_and_oracle_consistent |  |
| V03-14 | R0 | LIVE end-to-end browser→graph→approval→worker→sandbox→reconcile | DEFERRED (target model) | artifacts/v03/e2e-latest.json (passed) | Product path verified by scripts.e2e_v03 without a model decision; LIVE agent from a free-form request deferred to the target model |
| V03-15 | R0 | Server session survives refresh; revoke/roles; no localStorage bearer | PARTIAL | test_V03_15_cookie_session_refresh_revoke_and_csrf<br>v03_owner_main_path | HTTPS Secure cookie applies only behind TLS; loopback dev uses HttpOnly+SameSite=Strict |
| V03-16 | R1 | Flexible CSV/XLSX mapping, review, provenance | PASSED | test_V03_16_mapped_csv_and_xlsx_import_with_review_and_versions<br>v03_owner_main_path |  |
| V03-17 | R1 | Alerts with dedup | PARTIAL | test_V03_10_V03_17_home_names_problem_date_next_action_and_dedups_alerts | Detection is a deterministic projection with first-seen dedup; no debounce scheduler or acknowledgements yet |
| V03-18 | R1 | Per-invoice what-if | PASSED | test_V03_18_what_if_changes_one_receivable_and_keeps_facts |  |
| V03-19 | R1 | Chinese retrieval holdout | DEFERRED (target model) | — |  |
| V03-20 | R1 | Real-time approval TTL | PASSED | test_V03_20_real_time_approval_ttl_with_frozen_business_clock |  |
| V03-21 | R1 | Partial replan / stale checks | NOT_RUN | — | Existing STALE_PLAN/STALE_SNAPSHOT checks plus server-side hash re-check at approval; unrelated-change tolerance not changed |
| V03-22 | R1 | Isolation, roles, backup | NOT_RUN | — |  |
| V03-23 | R0 | Browser regression on real backend | PARTIAL | v03_owner_main_path | Manual browser walkthrough recorded; no Playwright runner on this Windows host (PyPI/npm blocked) |
| V03-24 | R0 | Usability and accessibility | PARTIAL | v03_owner_main_path | Semantic markup, focus, dialog, no page overflow at 390/768/1366/1440 measured; participant study not run |
| V03-25 | R0 | Updated release evidence | EVIDENCE_RECORDED | artifacts/v03/regression-v03.json<br>artifacts/v03/e2e-latest.json<br>artifacts/v03/browser-v03.json<br>docs/V03_PLAN.md<br>docs/adr/0005-v03-owner-main-path.md |  |

Counts: {'EVIDENCE_RECORDED': 2, 'PASSED': 9, 'DEFERRED_MODEL': 6, 'NOT_RUN': 3, 'PARTIAL': 5}

## Product-path E2E (`python -m scripts.e2e_v03`)

Scope: Real HTTP server + queue worker + independent sandbox via cookie session; MOCK runtime; no LIVE model decisions. Passed: **True**. Workspace `.runtime\v03-e2e\20261018-170345`.

| Check | Result |
|---|---|
| initial_gap_90000 | PASS |
| receivable_due_moved | PASS |
| same_gap_not_reported_as_change | PASS |
| change_recorded_in_case | PASS |
| options_differ | PASS |
| approval_requires_step_up | PASS |
| browser_session_cannot_use_legacy_money_route | PASS |
| tampered_hash_refused | PASS |
| action_1_settled | PASS |
| action_2_settled | PASS |
| action_3_settled | PASS |
| session_survives_restart | PASS |
| action_4_settled | PASS |
| lost_response_single_attempt | PASS |
| action_5_settled | PASS |
| plan_completed | PASS |
| reconciled_zero_difference | PASS |
| final_cash_29000 | PASS |
| case_resolved_only_after_reconciliation | PASS |
| world_one_operation_per_key | PASS |
| world_movements_6 | PASS |
| world_cash_matches | PASS |
| ledger_one_balanced_pair_per_movement | PASS |

Not covered: Pixel rendering (see browser evidence); LIVE agent from a free-form request (deferred until the target model).

## Browser walkthrough (built-in browser pane, real backend)

Scope: 18 Oct re-recording after the submission PR (#2) changed web/pages.js, copilot.js, ui.js and style.css. Built-in browser pane on the owner's Windows host against a fresh throwaway workspace (.runtime/browser-check-20261018, port 8091, MOCK model, independent sandbox, queue worker) on merged main 0b1720f. Real clicks and typing; the CSV was attached via DataTransfer on the same input change handler. The pane was hidden, so evidence is page text and DOM measurements, no new screenshots; 'previous_screenshots' are from 2026-10-14T13:58:00Z and show the earlier UI. No real money; synthetic sandbox only. Not a Playwright runner.

- home_names_gap_date_amount_and_cta: PASS
- chinese_names_and_cny_amounts_rendered: PASS
- options_compared_executable_infeasible_conditional: PASS
- review_dialog_blocks_before_due_with_reason: PASS
- exact_approval_checkbox_and_specific_button: PASS
- lost_response_single_attempt_and_settled_timeline: PASS
- session_survives_reload_and_server_restart: PASS
- copilot_cards_separate_from_model_text: PASS
- import_mapping_ambiguity_flagged_and_review_unblocks: PASS
- no_horizontal_overflow_390_768_1366_1440: PASS
- all_form_fields_labelled: PASS
- contrast_pairs_at_least_4_5: PASS
- no_unexpected_console_errors: PASS
- money_business_health_card_rendered: PASS

Screenshots: 
