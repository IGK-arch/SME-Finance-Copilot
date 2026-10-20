# ADR 0006 — verify approved identity before recognizing settlement

Date: 19 Oct 2026 (Moscow). Status: implemented for the synthetic sandbox.

## Context

AUD-01 / K15 reproduced a false success: a movement with the approved cash delta
but the wrong recipient or purpose could set an action to SETTLED and release its
reserve. Matching bank and local balances did not prove that the approved
obligation had been paid. The original audit evidence is retained.

## Decision

1. Before allocation, debt creation or action completion, match exactly one
   approved command by stable key and, when known, provider reference. Check its
   signed amount, counterparty and obligation reference. A lost response can leave
   the provider reference unknown; the exact stable key and economic fields are
   still required. A conflict between two candidate commands quarantines both.
2. Record the observed cash transaction and balanced ledger entries once even
   when identity is wrong. Do not allocate disputed cash to the approved bill or
   another bill; do not infer a confirmed debt from a disputed loan draw.
   Unmatched external movements remain supported. An unknown nonempty operation
   key cannot be treated as an ordinary external receipt for automatic allocation.
3. Persist the first discrepancy as a tenant-scoped immutable object. Nonterminal
   actions become UNKNOWN, keep their active reservations and no longer assume
   that the provider's available balance contains the reserve. Historical terminal
   actions are not rolled back by a later conflicting movement.
4. Stop new sends. A disputed action cannot be resent by the worker; later status
   responses cannot release the reservation or erase the discrepancy. Replay,
   restart and even a corrected reappearance of the same movement leave it open.
   Cash observation remains available. Resuming requires a fresh fully matched
   reconciliation and fails while any settlement issue remains.
5. Separate balance equality from full reconciliation. Reconciliation v2 exposes
   `cash_matched` and `settlement_issues`; `matched` additionally requires no issue.
   Owner alerts and timelines explain that review is needed, rather than calling
   every UNKNOWN action a lost response. Exact approvals, authentication, tenant
   isolation, stable keys and the kill-switch guards are retained.

## Compatibility and limits

The existing `objects` table stores settlement issue v1 and reconciliation v2;
no DDL change is needed. Old objects are preserved. This is not a historical repair
job: already accepted movements in the inbox are not retroactively revalidated.

There is deliberately no automatic or force-clear resolution endpoint. A true
provider discrepancy leaves execution stopped until a separately designed,
audited resolution process exists. This preserves safety at the cost of
availability; a matching balance or repeated approval cannot clear the issue.

The current sandbox is CNY-only and exposes symbolic counterparty IDs and
obligation references. This does not verify an actual bank account, beneficiary
version, currency conversion or bank payment-purpose format. A real adapter
requires an explicit authenticated settlement contract and its own failure tests.

## Verification

`tests/test_settlement_identity.py` exercises actual approvals, independent
sandbox operations and fault-injected observations: payment/loan/repayment
identity, amount and reference conflicts, durable quarantine, reserves, worker
blocking, tenant scope and successful lost-response reconciliation. Full
regression, HTTP E2E, golden and static results are recorded in
[the dated fix report](../SETTLEMENT_FIX_20261019_RU.md).
