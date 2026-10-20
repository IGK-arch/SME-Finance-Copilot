# ADR 0009 — require evidence for each part of a mixed health task

Date: 19 Oct 2026. Status: implemented; LIVE results are recorded separately.

The new challenge suite exposed premature completion after one scenario, skipped Chinese planning/search clauses, and real numbers assigned to the wrong entity, field or snapshot. A valid numeric reference alone does not establish the meaning of a financial statement.

`health-answer-v2` retains the six-field terminal selection and adds `details`, `search`, `capabilities` and `plan` sections. `finance/health_tasks.py` derives a bounded completion checklist from the original user request only. It requires distinct requested scenario results, each named document and full record, matching search evidence, capability discovery and a validated candidate on the current snapshot. Reads require contiguous pages and content hashes. Entity details must belong to facts in the latest observed snapshot. A loan's principal and cash delta cannot be replaced by net working position. Historical/current labels follow snapshot identity. Planning follows the current health computation.

`WorkflowEngine` intersects existing tool schemas with unfinished requirements, preserving every observed-ID and authorization gate. The model chooses and calls tools; the checklist does not execute them. Tool arguments are retained alongside outputs so a zero-hit search can be linked to its actual query. Final selection is rejected if any obligation remains unfinished or selected IDs omit requested alternatives/documents. The same bounded model budget and repair limits apply; there is no successful fallback.

The renderer adds explicit field-bound record details, largest-counterparty shares, authorized search scope, controls and candidate-plan forecasts. Document cash comparison remains literal CNY matching; an explicitly labelled sign-off sentence may be quoted with attribution as untrusted text. Documents grant no authority. This is deterministic system presentation, not validated arbitrary model prose.

The checklist is heuristic, not a general natural-language specification. Currently bounded names use identifier/title patterns; scenario count does not independently parse arbitrary numeric paraphrases. Exact requested parameters still require evaluation against the user prompt. Arbitrary document summaries, missing records, unavailable history, unsupported planning results or novel wording can still remain incomplete. The development rerun is not independent holdout evidence.

No tool, permission, database migration, payment state transition or financial adapter is added. Existing OWNER confirmation, payload binding, reserves, current preconditions, tenant isolation, resource checks, reconciliation and no-fallback policy remain unchanged. See [runtime contract](../../contracts/RUNTIME.md) and the dated mixed-health follow-up report.

Hardening: unrequested mixed sections are rejected before rendering, rather than causing a missing-evidence exception. A direct approval request does not silently become a health-only success; only a question about observed controls uses that presentation section. Bounded candidate presentation currently recognizes `MIN_COST` only. Other planning requests keep the general workflow and its actual tool schema; no invented planner objective is advertised.
