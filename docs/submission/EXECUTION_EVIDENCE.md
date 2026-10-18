# Execution evidence: sandbox operation logs

Topic E is a non-on-chain topic, so execution evidence is simulated-account
operation logs; section 3 lists the on-chain anchors made for the challenge bonus. All data is synthetic; the bank is an independent sandbox process
with its own database. Regenerate this page with `python -m scripts.execution_log`
after re-running the two commands below.

## 1. Golden scenario with a lost bank response

Source: `artifacts/golden-latest.json` (`python -m scripts.demo --lost-response`).
Mode: SYNTHETIC_SANDBOX · model: mock · approvals: scripted synthetic owner approvals.

| # | Business date | Action | Amount | Idempotency key | Approval payload hash | After send |
|---|---|---|---|---|---|---|
| 1 | 2026-10-02 | DRAW_LOAN lender_v1 | CNY 91,000.00 | `demo_company_plan_44725ac974aa14427bcdd0cf_fund` | `3b4239226dafd34f…` | SUBMITTED |
| 2 | 2026-10-05 | PAY_OBLIGATION salary | CNY 80,000.00 | `demo_company_plan_44725ac974aa14427bcdd0cf_b31f526e191d` | `e2fdeb4fabd44514…` | UNKNOWN |
| 3 | 2026-10-06 | PAY_OBLIGATION rent | CNY 20,000.00 | `demo_company_plan_44725ac974aa14427bcdd0cf_e633aa88f47c` | `f3b0112f321b100e…` | UNKNOWN |
| 4 | 2026-10-08 | PAY_OBLIGATION supplier | CNY 90,000.00 | `demo_company_plan_44725ac974aa14427bcdd0cf_9ff3df0a6b05` | `91d1224847119e4c…` | UNKNOWN |
| 5 | 2026-10-31 | REPAY_LOAN plan_44725ac974aa14427bcdd0cf_fund_debt | CNY 91,000.00 | `demo_company_plan_44725ac974aa14427bcdd0cf_repay` | `55f270d962bbd7da…` | SUBMITTED |

UNKNOWN means the sandbox accepted the payment but the response was lost on purpose.
The worker found each one by the same key; no second payment was sent.

| Result | Value |
|---|---|
| Plan | COMPLETED, 5/5 actions settled |
| Reconciliation | RECONCILED, local CNY 29,000.00 = bank CNY 29,000.00, discrepancy CNY 0.00 |
| Independent evaluator (world-ledger-oracle-v2) | final cash CNY 29,000.00, lowest CNY 20,000.00, open payables CNY 0.00, open debt CNY 0.00, 6 bank movements, missed deadlines 0 |
| Hash-chained audit records | 23 |

## 2. Product path through the real server, worker and sandbox

Source: `artifacts/v03/e2e-latest.json` (`python -m scripts.e2e_v03`).
Scope: Real HTTP server + queue worker + independent sandbox via cookie session; MOCK runtime; no LIVE model decisions.

| Step | Details |
|---|---|
| home_initial | state: GAP, need: CNY 90,000.00, gap: 2026-10-08T00:00:00.000000+00:00 |
| import_preview | ready: 1, update: {"from_version": 1, "changes": {"due_at": ["2026-10-11T00:00:00.000000+00:00", "2026-10-14T16:00:00.000000+00:00"]}} |
| import_commit | status: IMPORTED, accepted: 1 |
| home_after_change | state: GAP, history: ["OPENED"], receivable_due: 2026-10-14T16:00:00.000000+00:00 |
| home_after_policy | need: CNY 95,000.00, change: Data changed: need CNY 90,000.00 → CNY 95,000.00; gap date Thu 8 Oct → Tue 6 Oct |
| options | summary: 1 executable of 4 options, statuses: {"FINANCE_MIN_COST": "EXECUTABLE", "NO_NEW_DEBT": "INFEASIBLE", "HIGHER_RESERVE": "INFEASIBLE", "STRESS_RESILIENT": "INFEASIBLE"} |
| selected | plan_id: plan_d42fd3b57d00f311b6b07f24, actions: ["Draw loan · CNY 96,000.00", "Pay Payroll · CNY 80,000.00", "Pay Landlord · CNY 20,000.00", "Pay 苏州合成供应商 · CNY 90,000.00", "Repay loan · CNY 96,000.00"] |
| approved | n: 1, title: Draw loan · CNY 96,000.00, status: RESERVED, lost_response: False |
| worker_sent | title: Draw loan · CNY 96,000.00, status: SUBMITTED |
| settled | title: Draw loan · CNY 96,000.00, status: SETTLED, attempts: 1 |
| approved | n: 2, title: Pay Payroll · CNY 80,000.00, status: RESERVED, lost_response: False |
| worker_sent | title: Pay Payroll · CNY 80,000.00, status: SUBMITTED |
| settled | title: Pay Payroll · CNY 80,000.00, status: SETTLED, attempts: 1 |
| approved | n: 3, title: Pay Landlord · CNY 20,000.00, status: RESERVED, lost_response: False |
| worker_sent | title: Pay Landlord · CNY 20,000.00, status: SUBMITTED |
| settled | title: Pay Landlord · CNY 20,000.00, status: SETTLED, attempts: 1 |
| approved | n: 4, title: Pay 苏州合成供应商 · CNY 90,000.00, status: RESERVED, lost_response: True |
| worker_sent | title: Pay 苏州合成供应商 · CNY 90,000.00, status: UNKNOWN |
| server_killed | while_status: UNKNOWN |
| server_restarted | home_state: IN_FLIGHT |
| settled | title: Pay 苏州合成供应商 · CNY 90,000.00, status: SETTLED, attempts: 1 |
| approved | n: 5, title: Repay loan · CNY 96,000.00, status: RESERVED, lost_response: False |
| worker_sent | title: Repay loan · CNY 96,000.00, status: SUBMITTED |
| settled | title: Repay loan · CNY 96,000.00, status: SETTLED, attempts: 1 |
| final | plan: COMPLETED, reconciliation: RECONCILED, cash: CNY 29,000.00, state: NO_GAP |
| case_after | state: NO_OPEN_CASE, closed_reason: RESOLVED_SETTLED_AND_RECONCILED |
| world | operations: 5, movements: 6, cash: 2900000, duplicate_keys: 0, ledger_pairs: 6 |

Checks: **23/23 PASSED** (overall PASSED).

| Check | Result |
|---|---|
| initial_gap_90000 | PASSED |
| receivable_due_moved | PASSED |
| same_gap_not_reported_as_change | PASSED |
| change_recorded_in_case | PASSED |
| options_differ | PASSED |
| approval_requires_step_up | PASSED |
| browser_session_cannot_use_legacy_money_route | PASSED |
| tampered_hash_refused | PASSED |
| action_1_settled | PASSED |
| action_2_settled | PASSED |
| action_3_settled | PASSED |
| session_survives_restart | PASSED |
| action_4_settled | PASSED |
| lost_response_single_attempt | PASSED |
| action_5_settled | PASSED |
| plan_completed | PASSED |
| reconciled_zero_difference | PASSED |
| final_cash_29000 | PASSED |
| case_resolved_only_after_reconciliation | PASSED |
| world_one_operation_per_key | PASSED |
| world_movements_6 | PASSED |
| world_cash_matches | PASSED |
| ledger_one_balanced_pair_per_movement | PASSED |

Not covered: Pixel rendering (see browser evidence); LIVE agent from a free-form request (deferred until the target model).

## 3. On-chain anchors

No anchor recorded yet. Run `python -m scripts.anchor_audit send`, then
`verify --tx <hash>`; results are appended to `artifacts/onchain-anchors.json`.
