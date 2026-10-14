# ADR 0005 — v0.3 owner main path, strategies, session and import mapping

Date: 2026-10-13. Status: implemented for the synthetic/sandbox scope; LIVE agent items deferred.

## Context

The v0.2.0 kernel (integer money, versioned facts, CP-SAT, independent validator, exact
approvals, reserves, worker, sandbox, reconciliation) was correct but exposed ten technical
sections. The v0.3 audit package (`SME_Copilot_v0_3_Audit_UX_Package`) and the owner's
re-prioritisation of 13 Oct 2026 put the product path first:
problem → cause → options → choice → exact approval → execution → reconciled result.
The local 14B model is a temporary integration model; optimising it is explicitly not the
main direction.

## Decisions

1. **Read models, not a second domain.** `finance/cases.py` projects Home, the financial
   case, option cards, action review, timelines and activity from snapshot/forecast/planner/
   ExecutionService. Balances, approvals, reserves and sends stay in the existing services.
2. **Financial case as an append-only event log** in `objects` (kind `case_event`): OPENED,
   PROBLEM_CHANGED (with a human diff), OPTIONS_COMPUTED, OPTION_SELECTED, CLOSED. No migration;
   works on SQLite and PostgreSQL. A case is CLOSED as `RESOLVED_SETTLED_AND_RECONCILED` only
   when the selected plan is COMPLETED and reconciliation matches; if the gap disappears from
   data without execution it is `NO_LONGER_DETECTED_IN_DATA`. Selecting a plan never resolves it.
3. **Distinct strategies, shared by CP-SAT and the oracle** (`planner.objective_scope`):
   - MIN_COST: minimum cost, then principal, base scenario.
   - NO_NEW_DEBT: no financing candidates.
   - HIGHER_RESERVE: minimum cost subject to an explicit cash target `reserve_target_minor`
     (default 125% of the reserve). Previously it maximised the minimum cash, which rewarded
     borrowing the largest amount.
   - PRESERVE_LIQUIDITY: minimum cost subject to the reserve in every DEMO scenario (f0,
     delay_5, delay_25). Previously identical to MIN_COST.
   Every result records `objective_implemented`, `liquidity_floor_minor`, `validated_scenarios`
   and `candidate_scope` (finite grid). The agent system prompt now describes these semantics.
4. **Infeasibility diagnostics** (`cases.explain_infeasible`) are deterministic checks
   (shortfall without financing, eligibility, expired quote, funding arrives after the gap,
   repayment creates a gap, maximum amount insufficient). They are labelled as diagnostics,
   not a minimal infeasibility proof.
5. **Approve exactly what was reviewed.** `POST /v1/review/{plan}/{action}/approve` receives
   only the displayed payload hash and an explicit confirmation. The server recompiles the
   command; a different digest is refused (`APPROVAL_HASH_MISMATCH`). It then calls the existing
   `approve` and `enqueue`. One approval covers one action; there is no approve-all.
6. **Server session** (`/session`): the membership token is exchanged for a random session id,
   stored hashed in `objects` with real-time expiry (8 h) and revocation; every request re-checks
   the active membership and its token hash. Cookie: HttpOnly, SameSite=Strict, Secure under
   HTTPS. Cookie-authenticated POSTs require `X-SME-Request: 1` plus the existing same-origin
   check. Bearer tokens remain for scripts/tests. Nothing is stored in localStorage.
7. **Import mapping** (`finance/mapping.py`): CSV/XLSX (first sheet, values only, size-bounded,
   stdlib parser) for two templates (transactions, obligations); explicit decimal separator and
   date format, ambiguous values are errors, never guesses; Decimal → minor units; versioned
   updates of existing records in their namespace; rows with errors go to the existing
   quarantine; raw upload and mapping version stored for provenance. Not a bank adapter.
8. **Copilot integration** (`finance/copilot.py`): background runs return immediately; the UI
   polls recorded events. Typed result cards come from tool outputs; narrative, computation,
   workflow and execution statuses are separate. UI context is passed as references that the
   server re-authorizes; unknown references are refused. The model adapter stays the existing
   `ChatGateway` (mock / disabled / ollama); a stronger runtime is a later, separately verified
   provider and no quality is claimed in advance.
9. **Frontend**: vanilla JS kept (no build pipeline on this host), split into `ui.js`,
   `pages.js`, `copilot.js`, `app.js`; navigation Home / Money / Plans / Documents / Activity /
   Settings; the previous cabinet stays at `/legacy` for tools not yet migrated (manual
   allocation, raw synthetic CSV).

## Consequences

- `test_planner` comparisons still hold; new tests cover the changed objectives.
- The case stays OPEN while a plan is in progress, even when the base-scenario gap is gone.
- Imported payables for unknown counterparties are not payable (no verified beneficiary, and
  the sandbox world does not know them): an honest block, visible in review.
- Deferred to the target model: CompletionGate, AnswerBundle validation of model text, skills/
  scoped tools measurement, latency profiling, LIVE end-to-end from a free-form request.
