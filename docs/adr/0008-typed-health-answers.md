# ADR 0008 — bind health answer labels to server-verified fields

Date: 19 Oct 2026 (Moscow). Status: implemented; measured results in the dated follow-up report.

## Problem

The initial twenty health cases produced six rejected final texts and three semantic errors among automatic passes. A valid reference can name the wrong field: a zero transaction count is not a null gap; P&L status is not coverage status; saved/current calculations are not interchangeable. Repeating prompt instructions did not reliably prevent unbound digits in headings.

## Decision

Use `health-answer-v1` for bounded English/Chinese aggregate health requests. The LIVE model still chooses and invokes authorized tools, reads full pages and selects report sections and catalog IDs. Its terminal response is strict selection JSON, with no numeric values, arbitrary prose or authority fields. The server binds labels, values, snapshot/result identity, null meanings and forecast scope as indivisible claims, then passes the generated marker text through the existing exact-reference renderer.

Current means the metrics calculation on the latest financial snapshot actually returned to this workflow, not a timestamp inferred from list order. Saved calculations require complete contiguous, hash-matching pages and a different snapshot. They are labelled separate observations; the renderer infers no unproven chronology, sum or difference. Document text never creates calculation IDs. Document comparison only recognizes explicitly labelled literal CNY confirmed-cash amounts with two decimal places; missing or ambiguous forms remain unestablished. A quoted amount is not promoted to financial evidence.

Once the requested health evidence and the existing read-completion requirements are satisfied, close tools for a final selection. This does not bypass missing reads, force a model response, call tools on its behalf or provide successful fallback. Malformed/unsupported selections get the existing bounded repair; persistent failure remains PARTIAL. Detected mixed actions, specified broader document tasks and Cyrillic requests keep the general workflow. EN/ZH routing is heuristic; other languages and arbitrary paraphrases are not evaluated.

## Safety and scope

No additional tools, authority, mutable financial state or database tables. OWNER approvals, exact payloads, reserves, current preconditions, tenant isolation and independent reconciliation remain unchanged. `answers.render` is unchanged. `model_text_trust` explicitly marks server-rendered health presentation; do not describe this as improved free-form financial prose by the model.

Tests cover the preserved synthetic traces, semantic swaps, null/status/scope confusion, wrong IDs, missing/tampered pages, document injection, literal comparison, mixed-task routing, complete workflow and refusal to manufacture success after invalid model output. The fixed development suite is not a holdout.

See [runtime contract](../../contracts/RUNTIME.md) and [measured follow-up](../BUSINESS_HEALTH_FIX_20261019_RU.md).
