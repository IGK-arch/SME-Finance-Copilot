# Agent access to the current platform

Contract: agent-tools-v2. All current data is synthetic; execution is sandbox only.
Local model selection/quality and availability must be read from actual live reports.

| Platform data or function | Agent access | Authority/boundary |
|---|---|---|
| Company, account, membership and beneficiary details | list_business_records / read_business_record | Tenant and current role; no authentication secrets |
| Facts and versions, invoices, transactions, obligations, allocations | Same paginated readers | Invoice/obligation/settled cash stay distinct; source IDs and times retained |
| Imports and quarantine/review decisions | Same readers | Corrections/discards and allocations remain human actions |
| Sources and document versions/full text | Same readers, search_documents, get_evidence | ACL checked before search; untrusted text; long-record continuation |
| Policies and protected payments | Same readers; current snapshot | Policy changes require OWNER in Settings |
| Plans, snapshots and saved calculations | Same readers, get_plan_details | Full detail available by returned record/result ID |
| Approvals, actions, reservations, attempts, jobs, outbox/inbox, ledger, audit | Same readers; get_action_status | Recorded state, not invented settlement; no grant/dispatch tool |
| Own workflow history | Same readers | Creator and role scoped; old restricted evidence remains protected |
| Financing products/terms | Same readers, screen_financing_products, simulate_financing | DEMO only; eligibility is not lender approval |
| Metrics, cashflow forecast, stress tests | Existing deterministic tools; full calculations dataset | Integer money, explicit assumptions, source references |
| Receipt delay and partial-payment what-if | what_if_cashflow | Forecast + hypothetical MIN_COST plan; actual facts unchanged |
| New plan | optimize_plan | Actual OR-Tools and independent validation; no approval implied |
| Selected action proposal | get_plan_details then prepare_action | Real matching IDs, current preconditions, separate exact approval |
| Supplier extension | propose_supplier_extension; extensions dataset | Pending conditional request only; protected obligations rejected |
| Import/upload, review/allocation, settings, approval/revoke, cancellation, execution/recovery, kill switch, reconcile, demo clock/decisions | get_platform_capabilities explains human controls | Existing UI/API authority; no autonomous mutation tool added |

Read protocol: list_business_records(dataset, query, offset), beginning at offset 0.
An empty query lists all authorized records; nonempty query is literal substring
search. Follow next_offset to see remaining matches. Lists contain summaries; use
read_business_record(dataset, record_id, offset) for complete contents. Large details
return JSON fragments; continue until next_offset is null, comparing content_hash.
Do not interpret a page count as a company total or a missing fragment as no evidence.
The current local implementation scans scoped records in memory; it is not a
production-scale query engine or arbitrary SQL/natural-language database access.

Financial compute envelopes contain result_id. Read dataset calculations with that
ID for complete forecast event paths and assumptions, even when the model's initial
summary is compact. Real plan IDs/action IDs appear in optimize_plan/get_plan_details;
the server rejects fabricated or mismatched pairs. A waiting proposal has no executable
command until its preconditions pass. Exact approval is never obtained from chat text.

The model sees detail-read tools only after it has obtained matching dataset/record
IDs. Saved-plan detail similarly requires a listed/created plan. Both the schema
and server call boundary enforce these prerequisites. They do not replace current
tenant/role/precondition checks, which are repeated on each actual operation.

The model still has bounded context, time and calls. Tool coverage is distinct from
reliable natural-language performance. Requests and actual live outcomes are preserved
by scripts.live_compare --suite platform; failed or blocked runs are not model passes.

Data-quality flags permit read-only diagnosis of imports, quarantined rows and
sources, with an explicit server warning. The planner, independent validator and
executor still reject an executable financial plan until the flags are resolved.
The model cannot silently correct or discard a row to clear the restriction.
