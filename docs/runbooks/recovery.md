# Local sandbox recovery

## UNKNOWN / lost response / worker crash

Read the action, attempts, stable key, reserve and audit. Use “Read status & recover”
or POST /v1/actions/{id}/recover. Status lookup occurs before resend. If the provider
has accepted it, do not create a new key. Advance the synthetic clock to observe
settlement, then reconcile. A timeout is not FAILED and does not release reserves.
Repeated recovery must leave one external operation and one pair of ledger lines.

## Stop / revocation / stale facts

“Stop new sends” blocks sends and preserves status/reconciliation reads. Resume is
an explicit OWNER/ADMIN control with a reason, after checking pending operations.
Revoking approval blocks unsent commands; sent operations remain observable. A
cancelled plan retains settlements. No sandbox cancel capability is advertised.

If membership, beneficiary version, policy or data changes, compile a fresh command
from the revised plan/state and approve that exact payload. Do not edit approval
hashes or delete a settled action. A compensation would require a separate supported
operation and its own approval; compensation is currently unsupported.

## Balance mismatch / owner payment outside Copilot

Refresh independent sandbox observations. Unmatched cash stays in the ledger and
does not silently close a payable. A discrepancy stops new sends and creates audit
evidence. Resolve missing/incorrect sources using new versions; do not fabricate
balancing income. Recheck the old snapshot, movement IDs, allocation totals and
external state before resuming.

## RESERVED but never sent

Inspect outbox and attempt records, then use the execution service with the same
action ID. Current authorization and funds checks still apply. A stale command is
blocked. Never release an uncertain reservation solely because it is old. The
prototype has no generic operator “clear reservation” endpoint; migration to a
reviewed cancellation/replacement workflow is required for unattended operations.

## Model unavailable / import unsupported

Live inference fails explicitly. The deterministic mock can calculate and propose,
but cannot bypass approvals. Unsupported scanned PDF/OFD/XML/merchant/bank formats return a
typed error or remain unimplemented. CSV quarantine preserves row numbers and
reasons; execution is blocked while quality flags are unresolved.

## Process shutdown / backups / credentials

Ctrl+C in the foreground server stops its worker and sandbox child in finally. PostgreSQL
is stopped separately with scripts.postgres stop. Preserve
.runtime workspace files for investigation. “make down” prints this instruction and
never kills unrelated processes or deletes data. Back up both databases and audit
before any future destructive migration. Credentials are local random secrets;
never attach .runtime, secret JSON, tokens or private world files to public evidence.

## Restart and stale workflow approvals

Reuse the same --directory. Startup reads persistent capabilities/tokens and never
reimports the fixture on resume. After login, open the saved workflow. For a changed
snapshot use Refresh command from current facts; inspect and approve the replacement.
This refresh grants no approval and sends no operation. Exact stale payloads fail.

A standalone PostgreSQL service must be running before opening its workspace; see
postgres.md. Do not run two API runtimes against the same directory/world. The
independent evaluator now rejects missed payment deadlines even if cash matches.
