# Execution evidence: sandbox operation logs

Topic E is a non-on-chain topic, so the required execution evidence is
simulated-account (sandbox) operation logs and the demo video. All data is
synthetic; the bank is an independent sandbox process with its own database.

| Evidence | Where |
|---|---|
| Golden scenario: 5 payments, one deliberately lost bank response | [section 1](#1-golden-scenario-with-a-lost-bank-response), `artifacts/golden-latest.json` |
| Product path through the real HTTP server, worker and sandbox bank | [section 2](#2-product-path-through-the-real-server-worker-and-sandbox), `artifacts/v03/e2e-latest.json` |
| On-chain transaction hashes (challenge bonus) | [section 3](#3-on-chain-anchors), `artifacts/onchain-anchors.json` |
| Bank-fault safety: wrong settlement identity | [section 4](#4-bank-fault-safety-wrong-settlement-identity) |
| Demo video (≤ 5 min) | Submitted with the presentation; script in [demo-script.md](demo-script.md) |

Every table below is generated from the raw artifacts by
`python -m scripts.execution_log` after `python -m scripts.demo --lost-response`
and `python -m scripts.e2e_v03`; nothing is typed by hand.

## 1. Golden scenario with a lost bank response

Source: `artifacts/golden-latest.json` (`python -m scripts.demo --lost-response`).
Mode: SYNTHETIC_SANDBOX · model: mock · approvals: scripted synthetic owner approvals.

| # | Business date | Action | Amount | Idempotency key | Approval payload hash | After send |
|---|---|---|---|---|---|---|
| 1 | 2026-10-02 | DRAW_LOAN lender_v1 | CNY 91,000.00 | `demo_company_plan_23795b9f9eba9cef596c8df5_fund` | `74e8902e642b4b32…` | SUBMITTED |
| 2 | 2026-10-05 | PAY_OBLIGATION salary | CNY 80,000.00 | `demo_company_plan_23795b9f9eba9cef596c8df5_b31f526e191d` | `8f831f9e3ab7bbd7…` | UNKNOWN |
| 3 | 2026-10-06 | PAY_OBLIGATION rent | CNY 20,000.00 | `demo_company_plan_23795b9f9eba9cef596c8df5_e633aa88f47c` | `ef3e1a6bd29f7a63…` | UNKNOWN |
| 4 | 2026-10-08 | PAY_OBLIGATION supplier | CNY 90,000.00 | `demo_company_plan_23795b9f9eba9cef596c8df5_9ff3df0a6b05` | `5fc36f9337cc55ee…` | UNKNOWN |
| 5 | 2026-10-31 | REPAY_LOAN plan_23795b9f9eba9cef596c8df5_fund_debt | CNY 91,000.00 | `demo_company_plan_23795b9f9eba9cef596c8df5_repay` | `0aa4d436bea7a676…` | SUBMITTED |

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
| selected | plan_id: plan_5423161537503cf01dc321d2, actions: ["Draw loan · CNY 96,000.00", "Pay Payroll · CNY 80,000.00", "Pay Landlord · CNY 20,000.00", "Pay 苏州合成供应商 · CNY 90,000.00", "Repay loan · CNY 96,000.00"] |
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
| server_restarted | home_state: UNKNOWN_PAYMENT |
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

The head of the hash-chained audit log is published as the data of a
zero-value transaction on a public testnet; only hashes leave the machine.
`verify` reads the transaction back and recomputes the local chain, so a
rewritten and re-hashed audit history no longer matches. The transaction
can be checked independently in the block explorer link below.

Source: `artifacts/onchain-anchors.json` (`python -m scripts.anchor_audit`).

| When | Command | Network | Transaction | Records covered | Chain head | Result |
|---|---|---|---|---|---|---|
| 2026-10-18T13:46:15 | send | Ethereum Sepolia | [0x7ac42f1fccf4…](https://sepolia.etherscan.io/tx/0x7ac42f1fccf4aa2ceb9554544a4e1493a256cc7c1f19de4bb1eb311d42e9d1ba) | 72 | `cb50d8226473a02c…` | CONFIRMED |
| 2026-10-18T13:48:54 | verify | Ethereum Sepolia | [0x7ac42f1fccf4…](https://sepolia.etherscan.io/tx/0x7ac42f1fccf4aa2ceb9554544a4e1493a256cc7c1f19de4bb1eb311d42e9d1ba) | 72 | `cb50d8226473a02c…` | VALID |

## 4. Bank-fault safety: wrong settlement identity

The sandbox can report a settlement with the right amount but the wrong
counterparty or obligation reference. The reconciler must not mark the
action SETTLED, must keep the reserve and must stop further sends.

| Run | Code | Tests | Result |
|---|---|---|---|
| 2026-10-18T22:07:55 | before the fix | 12 | FAILED 11, PASSED 1 (`artifacts/settlement-fix-20261019/before.json`) |
| 2026-10-18T22:13:07 | after the fix | 15 | PASSED 15 (`artifacts/settlement-fix-20261019/targeted-final.json`) |

Design: [ADR 0006](../adr/0006-settlement-identity.md); tests:
`tests/test_settlement_identity.py`.
