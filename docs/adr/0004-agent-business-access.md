# ADR 0004 — Agent business reads and exact selected-action proposals

Date: 2026-10-13. Status: implemented; live verification tracked separately.

The previous model projection omitted obligations/invoices and plan action IDs.
This prevented detailed answers and encouraged fabricated identifiers. Increasing
the prompt to contain the entire database would lose permission boundaries and
exceed the local model's context.

Expose a closed business-dataset enum, literal search, stable ordering, five-record
pages, explicit next offsets and content hashes. Source/document bodies and large
records are read in 3000-character JSON fragments with an explicit continuation.
Small details remain structured JSON. The caller never supplies table names, SQL,
filesystem paths, simulator capabilities or database credentials. Membership reads
select user ID, role and active status only, excluding token hashes.

The first live probe confused list parameters with detail parameters. Consequently,
detail schemas are exposed only after visible dataset/record pairs; saved-plan
details require a listed/created plan. Pair matching is repeated server-side and
tested against unread, fabricated, mixed-dataset and malformed IDs. IDs remain
opaque values copied from results, never guessed from the user's prose.

Every read reauthorizes the membership and tenant. Document/source permissions are
filtered before search/count/pagination; workflows require their creator and original
role, and detail reads recheck source permissions. Facts expose observed versions;
current invoice/transaction/obligation views use snapshot time semantics. Future
simulator truth is never queried. Query is a literal substring, not a natural-language
database filter. Field totals cover all matching records and are explicitly not cash
or revenue. Collections may change between reads; hashes make that visible.

Full financial calculation results are stored as existing immutable objects of kind
agent_calculation. Their result IDs support paginated detail reads, including forecast
events omitted by compact summaries. No relational schema change/migration is needed;
existing objects storage and PostgreSQL tenant RLS apply. Original contracts remain
unchanged; agent-tools-v2 documents the added contract.

Plan summaries include real actions; get_plan_details supports further pages and
actual recorded states. prepare_action is advertised only after visible plan/action
pairs and server-checked against those pairs. The execution service still validates
tenant, role, plan membership, due date, dependencies and current financial conditions.
Not-yet-due proposals return WAITING_PRECONDITIONS, never false success. An explicitly
selected action controls the workflow's exact pending command; finishing it does not
automatically select another action from the plan.

Approval/dispatch/recovery, data correction/allocation, policy changes, cancellation,
kill switch and demo administration remain human/server controls. Capabilities report
their routes and authority. Supplier-extension proposals only create the existing
conditional request; an independent observed decision is required to change terms.
What-if runs compute hypothetical forecasts/plans without registering executable plans.

Quality flags no longer interrupt before the model can inspect rejected imports.
They are exposed as a server warning; the existing independent planning/validation/
execution guards remain. An offline test proves diagnosis completes while no
executable plan or operation is created. This closes an actual live-suite blocker.

P0: data/detail reads, real action IDs, exact proposal scope and permissions.
P1: computation details, what-if, conditional proposal, SQLite/PostgreSQL regression,
local model request suite and browser verification.
P2: external integrations, semantic retrieval, repeated/held-out language evaluation,
large-dataset query indexing and production OS isolation remain separate.

Requirements: I01/I03/I07/I08/I11/I15/I19/I20/I24/I27–I32/I34/I36;
T055–T068/T071–T086 retain their original scope. Additional tests are evidence, not
substitutes for the four original NOT_RUN targets or proof of perfect model prose.
