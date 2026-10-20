# Runtime contract notes

The original handoff schemas and examples are preserved byte-for-byte. Runtime
synthetic execution uses execution-command.schema.json v1: payment plus due time,
cash delta, dependencies, completion predicate and DEMO loan terms. This is an
internal contract and has no relationship to a real banking API.

finance/contracts.py supports the used JSON Schema subset only (types, const/enum,
required/properties/additionalProperties, bounds, date-time, arrays/uniqueItems,
oneOf/allOf/if). No remote references or arbitrary schema execution. Structural
checks are followed by current domain, exact approval and financial checks.

HTTP response: schema_version, request_id, result; errors contain code, safe_message
and retryable. Authenticated membership provides the tenant. Tool responses follow
the supplied tool-result envelope. Submitted commands are not claimed settled.
The plan JSON contains its full actions, quote, independent validation and stress
paths, rather than pretending the handoff metadata envelope alone is executable.

## Settlement identity (19 Oct 2026)

The synthetic sandbox movement contract contains `ref`, `stable_key` (nullable for
external cash), `delta` (signed integer minor units), `counterparty`, `reference`
and `at`. Currency is implicitly CNY in this adapter. For a Copilot operation,
`stable_key` must equal the approved command's `idempotency_key`; a previously
observed `provider_ref` must also match. Exactly one command must match. The
counterparty, signed cash delta and reference must equal the approved command;
the expected reference is `obligation_id` or `loan` for a draw. No fuzzy matching
or normalization is used. An unknown provider ref can be recovered by the exact
stable key after a lost response. Already terminal actions cannot accept another
new settlement movement.

Internal immutable object `settlement_issue`, schema version **1**, uses action ID
as its tenant-scoped object ID. Fields: `action_id`, `plan_id`, `transaction_id`,
`provider_ref`, `approved_payload_hash`, `observation_hash`, `mismatch_fields`,
`approved_delta_minor`, `observed_delta_minor`, `status=REVIEW_REQUIRED`. Possible
mismatch fields: `stable_key`, `provider_ref`, `counterparty`, `reference`,
`amount`, `terminal_action`, `ambiguous_operation`. The first discrepancy is
retained; repeated input and later provider statuses cannot acknowledge it.

Reconciliation objects now have schema version **2**. Existing fields remain;
`cash_matched` separately records equality of balances and `settlement_issues`
lists tenant-scoped discrepancies. `matched = cash_matched AND no settlement_issues`.
`status` is `RECONCILED` or `NEEDS_RECONCILIATION`. Zero monetary difference alone
is insufficient for safe completion or resuming sends. `action` and timeline read
models expose the issue; the timeline disables ordinary status checking for a
disputed action. Authenticated refresh remains available for observing cash.

Storage uses the existing append-only `objects` table; no DDL migration or rewrite
of existing reconciliation objects is performed. Readers accept old objects with
these additive fields absent. This is an internal sandbox contract, not a real
banking specification. See [ADR 0006](../docs/adr/0006-settlement-identity.md).

## Business health (19 Oct 2026)

Runtime tools use `agent-tools-v5`, calculations `compute-v3`, and the shared
cabinet calculation `analysis-v2`. The existing tool names and argument scopes
are unchanged; the original handoff tool schema remains historical.

`calculate_business_metrics(snapshot_id)` retains `metrics` and `pnl`, and adds
`business_health` under [business-health-v1](business-health.schema.json).
`forecast_cashflow(snapshot_id)` exposes the same health calculation for its first
(baseline) scenario. `what_if_cashflow` exposes it under `forecast.business_health`
for the explicitly requested scenario. This is not a forecast for an approved
payment plan; `stress_test_plan` retains its separate saved-plan meaning.

Money is integer CNY minor units. Ageing is a list of `{bucket,outstanding_minor}`,
so money never masquerades as a unitless count. Coverage and concentration use
integer basis points, rounded down. Combined top-three share is calculated from
combined amounts, not by adding rounded individual shares. The legacy field name
`supplier_concentration` includes all outgoing payable counterparties (including
payroll, rent or a lender), not just inventory suppliers. Concentration describes
open balances, not revenue or expenses.

`coverage_30d_bps=null` means NOT_APPLICABLE with no observed due payable;
`days_to_gap=null` means NO_GAP_IN_FORECAST in the named horizon, not infinite
runway. Zero days means an immediate reserve breach. Empty concentration has
no parties, no top entries and null combined share. `settled_transaction_count`
and the fixed trailing thirty-day window describe observed SETTLED cash events;
invoices/submissions are excluded. P&L remains INSUFFICIENT_DATA. No credit score
or calibrated insolvency probability is produced.

Forecast scope names the scenario, delay, receipt fraction and end of that
scenario's computed horizon. Hypothetical liquidity buffer and gap timing may
change; the observed cash, net working position, ageing and concentration do not
become hypothetical ledger facts. Evidence refs, snapshot, observation time,
quality flags and definitions accompany the output. The final answer renderer
binds monetary and percentage references without model-side arithmetic.

Existing `agent_calculation` objects persist full results and contract version.
`list_business_records`/`read_business_record` on `calculations` expose authorized
saved outputs with normal pagination. Old results remain readable; old cards
without health retain the previous rendering. No DDL migration or money state
transition is added. Membership/tenant checks, snapshot-ID prerequisites,
read/compute/propose boundaries and exact owner approvals remain unchanged.

## Typed health answer selection (19 Oct follow-up)

The v1 description below is historical. The compatible six-field v2 extension is
specified after it; existing persisted answers retain their recorded version.

`health-answer-v1` is an internal terminal-presentation contract, not an executable
tool or a replacement for the financial calculation contract. For bounded EN/ZH
aggregate health requests the model returns exactly these JSON fields:

```json
{
  "language": "en",
  "current_result_id": "<observed metrics result on latest observed snapshot>",
  "sections": ["overview"],
  "history_result_ids": [],
  "scenario_result_ids": [],
  "document_source_ids": []
}
```

Allowed sections are overview, aging, concentration, settled, limits, scenario,
history and documents. Arrays contain unique catalog strings, at most twelve.
No free prose, numeric replacements, arbitrary labels or authority keys are
accepted. Required sections follow the original user task, never document text.
Historical/scenario/document selectors must name authorized observed results;
full record reads require contiguous pages and a matching content hash. The
current result must match the latest snapshot actually read by the workflow.

Server presentation binds field labels to those values and uses the unchanged
`answers.render` reference check. It emits `presentation_contract`, the selected
IDs and field-level `claims` in answer validation, with
`model_text_trust=SERVER_RENDERED_HEALTH_FROM_OBSERVED_TOOLS`. Absence of a gap,
zero days, coverage null, P&L status and forecast horizon have distinct renderings.
History is presented as separate snapshot observations without inferred ordering
or arithmetic. Document cash comparison is limited to explicitly labelled CNY
cash literals with two decimal places; it never makes document text a cash fact.

Tools close only when the required health evidence and existing read-completion
requirements are satisfied. Malformed model selections use the existing bounded
repair; persistent rejection remains PARTIAL, with no successful template fallback.
Mixed action tasks keep the general flow. This feature changes neither approval
payloads nor execution authorization. No storage migration. See
[ADR 0008](../docs/adr/0008-typed-health-answers.md).

### Mixed-task completion extension: health-answer-v2

The same terminal JSON now permits additional sections: `details`, `search`,
`capabilities`, `plan`. `health_tasks.requirements` derives a bounded EN/ZH
checklist from the original request. The catalog exposes pending evidence,
never hidden fixture answers or authority. `ready` and `render` both enforce
all tasks; multiple scenarios require distinct parameter pairs and selection
of all requested alternatives. Named documents must all be fully read and
selected. Search evidence retains its actual query; an empty authorized result
cannot establish global non-existence. Detailed entity records must match
facts in the latest observed snapshot. Plan presentation requires a validated
candidate on that snapshot with the requested objective, after health computation.
The bounded plan presentation supports `MIN_COST`; other planning requests retain
the general workflow and its actual tool schemas and required parameters.

Largest-counterparty fields, detail fields, loan principal/net proceeds,
candidate forecast and baseline values are individually bound to their source
fields. Quoted document sign-off text stays untrusted and cannot change controls.
The executor and exact OWNER approval path are unchanged. Invalid or incomplete
selection still fails closed under the existing model/repair budget. No DDL
migration or new external API is required. Heuristic coverage and independent
holdout remain limitations; see [ADR 0009](../docs/adr/0009-mixed-health-completion.md).
