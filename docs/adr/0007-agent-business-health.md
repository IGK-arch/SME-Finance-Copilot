# ADR 0007 — expose Business health through scoped agent calculations

Date: 19 Oct 2026 (Moscow). Status: implemented; measured verification is in the
dated Business health report.

## Context

AUD-05 / OPEN-11 found that the cabinet called `compute.analysis` while the agent's
metrics tool only returned the earlier basic balances. The model could not use
the new deterministic ageing, coverage or concentration values. Asking it to
derive them from prose would bypass the project's exact-value answer contract.

## Decision

- Reuse `compute.analysis` for cabinet and agent. Add a typed `business_health`
  projection to metrics, baseline forecast and hypothetical forecast tool results.
  Do not introduce another source of financial truth or extra action permissions.
- Preserve old metric fields and add a versioned contract. Use explicit minor-unit
  ageing rows, integer basis points, nullable ratios and declared forecast scope.
  Compute combined top-three shares before rounding, and include a settled-event
  count so an empty observed window is distinguishable from an invented history.
- Expose the calculation in tool descriptions, capability discovery, source-linked
  saved calculations and owner result cards. Existing full-result pagination and
  observed-ID prerequisites continue to apply. The model uses server-generated
  money/percentage references and does not perform financial arithmetic itself.
- Keep current and hypothetical facts distinct: only forecast-dependent health
  fields change in a what-if. A health ratio cannot authorize a payment, replace
  an approved plan or prove profit, creditworthiness or insolvency probability.
- Keep the original benchmark cases and results immutable. Add a separate set of
  twenty synthetic paired EN/ZH cases, freeze code/cases/budgets before LIVE,
  retain failures and manually review prose separately from automatic PASS.

## Compatibility and limits

No new SQL tables, migrations, provider route or execution tool. Existing
`agent_calculation` objects carry `agent-tools-v5`; old results/cards still work.
`compute-v3` and `analysis-v2` distinguish the new output. Health schema is tested
using the project's supported local JSON Schema subset; no remote schema fetch.

Ratios describe observed synthetic CNY facts, contractual due-date buckets and
explicit DEMO forecasts. They are not accounting statements, credit decisions,
complete knowledge of a real business, or unrestricted model arithmetic. See
[runtime contract](../../contracts/RUNTIME.md) and
[measured report](../BUSINESS_HEALTH_AGENT_20261019_RU.md).
