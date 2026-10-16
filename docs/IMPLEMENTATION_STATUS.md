# Implementation status — v0.3.0, 2026-10-14

15 Oct update: exact-value references, observed stress/status IDs, bounded repair
and Strata final-writer protocol are implemented. Full unchanged 20-case rerun:
**20 PASS / 0 FAIL**; assistant text review **18 COMPLETE / 2 PARTIAL**.
Regression **195 PASS / 4 SKIP (199)**, target 47 PASS, quality nine PASS.
See [all final scenarios](STRATA_FINAL_SCENARIOS_20261015_RU.md) and
[changes/limitations](STRATA_FIXES_20261015_RU.md). Semantic interpretation is
still fallible; this does not close general LIVE acceptance. Cabinet 8092 resumed
and HTTP-verified; PostgreSQL/new browser walkthrough/LIVE payment E2E not run.

Overall full-product gate: **PARTIAL**, synthetic data / sandbox execution / MOCK
by default. Start with [CLAUDE.md](../CLAUDE.md) and
[CURRENT_STATE_RU.md](CURRENT_STATE_RU.md). Code baseline: `d3e24b6` on `main`;
the private Git origin exists. No release tag is present in the inspected checkout.

Later on 14 Oct, the owner authorized connection to an existing Strata server.
The new `strata` provider uses authenticated loopback HTTP over verified SSH,
native function calls and measured provider usage. The model is
`qwen3.8-flash-next-iq3_xxs`, engine 0.1.43.1. See [results](STRATA_RESULTS_RU.md)
and [runbook](runbooks/strata.md). Final regression after the journal/bridge fixes:
**184 PASSED / 4 SKIPPED** out of 188 (`artifacts/regression-strata-final-20261014.json`);
all nine quality checks passed. Final adapter/gateway/governance checks: 16 PASSED.
PostgreSQL and new browser testing were not run. The earlier sync evidence below
is retained; model narrative/CompletionGate/LIVE execution acceptance remain open.

| Current capability | Evidence and boundary |
|---|---|
| Six-page owner cabinet and context Copilot panel | `web/`, `finance/cases.py`; saved browser evidence matches all six web hashes |
| Financial case, options, exact review and timeline | Append-only case events; resolution requires completed plan and matched reconciliation |
| Distinct strategies | Explicit higher-reserve target and stress constraints; finite candidate grid |
| CSV/XLSX mapping and per-receivable what-if | Strict dates/decimal choices, preview/review, versioned facts; scenarios do not rewrite facts |
| Server session and approval expiry | 8-hour session; new approvals have 24-hour real-time TTL; legacy approvals retain business-clock expiry |
| Background LangGraph and tool-result cards | Implemented; new focused run exposed a Windows cleanup error, isolated rerun passed |
| Financial execution and recovery | Fresh HTTP/worker/sandbox E2E passed 21/21, five SETTLED, no duplicate, reconciliation matched |
| LIVE quality, production isolation and usability | Still incomplete; target-model items DEFERRED_MODEL |

Release regression (`artifacts/v03/regression-v03.json`, 14 Oct): **177 PASSED /
4 SKIPPED** out of 181; PostgreSQL was not configured in that shell. Original
acceptance: **96 PASSED / 4 NOT_RUN**. V03 matrix: 9 PASSED, 5 PARTIAL,
2 EVIDENCE_RECORDED, 6 DEFERRED_MODEL, 3 NOT_RUN. Saved quality evidence has nine
PASSED records (Python syntax, five JS syntax checks, Ruff, mypy, format).

Fresh Codex refresh: `scripts.test --pattern test_v03.py` with a dedicated output
reported **11 PASSED / 1 FAILED** (WinError 32 at temporary SQLite cleanup in V03-05).
The single-test repeat passed; this does not establish a fix. `scripts.e2e_v03`
with a dedicated output passed **21/21**. The first restricted-shell test attempt
failed setup with WinError 10013. See `artifacts/v03/codex-sync-*.json` for each
separate outcome. Full regression, PostgreSQL, quality and LIVE were not rerun.
No owner workspace was seeded or changed. Existing release evidence is preserved.

Current open work: [V03_PLAN.md](V03_PLAN.md),
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md), [CONTINUATION.md](CONTINUATION.md).

## Historical v0.2 implementation status — 2026-10-13

The following text is retained as earlier evidence. Its ten-route cabinet, active
14B configuration, missing Git and 163-test regression describe that checkpoint,
not the current version. Current scope and verification above take precedence.

Overall full-product gate: **PARTIAL**. This is a working persistent financial
workspace, beyond the first milestone. Real local inference has partial measured
evidence; OS isolation and broader P1/deployment requirements remain open. No claim of complete
P0/P1 acceptance or production readiness is made.

The audit read CODEX_START_HERE.md, MASTER_SPEC.md, the clarification register,
R1–R3, CODEX_BUILD_FULL_PRODUCT.md, checklists and contracts. No required package
file was missing. Existing AGENTS.md and 29 original handoff files are unchanged
(hash test). No Git metadata exists, so attribution of pre-existing uncommitted
edits and a release tag are unavailable. Existing useful code was extended.

| Capability | Status | Actual implementation and evidence |
|---|---|---|
| Ten connected English sections | VERIFIED in local browser scope | web/, finance/asgi.py + api.py; browser-smoke.json, four current screenshots; each route opened |
| Permanent API-backed financial state | VERIFIED | store.py, postgres.py, numbered migrations; backend/worker restart tests and browser restarts |
| PostgreSQL integration and two tenants | VERIFIED in tested local scope | PostgreSQL 18.6, restricted tenant logins, FORCE RLS, direct cross-tenant SQL/DDL denial; test_postgres.py |
| Full process/file/DB role isolation | PARTIAL | Tenant RLS verified; API/worker share role, simulator private files are not OS-isolated; T097 NOT_RUN |
| CSV import, disputed-row review, allocations | VERIFIED for fixed schema | ingestion.py/workspace.py; test_workspace.py/test_domain.py; browser corrected one quarantined invoice without creating cash |
| Financial calculations and independent validator | VERIFIED | compute.py/validation.py; minor units, fees, debt tail, timing, unmatched cash and invariant tests |
| F0/F1 scenarios and what-if | VERIFIED for explicit assumptions | Delay, partial remainder and shared-customer shocks; actual facts unchanged; no calibration claim |
| Actual OR-Tools CP-SAT | VERIFIED for disclosed finite grid | planner.py; 27 input/objective combinations compared to separate enumeration oracle; timeout/debt-tail tests |
| Conditional extension and observed replan | VERIFIED for supplier-extension branch | contingency.py + world.py; request alone non-executable, actual observation creates fact version; API/browser and full alternate 30,000 CNY case tested |
| LangGraph, typed tools and checkpoints | VERIFIED offline | workflows.py; actual tool results, durable question/approval/observation interrupts, restart and stale approval refresh tests |
| Agent business details and selected proposals | VERIFIED offline | agent-tools-v2: scoped list/detail/history, full calculation results, real action IDs, what-if and pending extension; SQLite/PostgreSQL, role changes, exact approval and single-action reconciliation tests; see AGENT_CAPABILITIES.md |
| Real model adapter | VERIFIED offline + limited live | gateway.py; native Ollama calls, Granite system/tool-format compatibility, typed transport failures and bounded-response tests; no failed-live fallback |
| Real model inference and novel tasks | PARTIAL | Experimental UI uses Qwen2.5 14B Q3_K_S; 20 distinct cases /21 attempts completed: 8 strict passes; assistant review 6 complete /5 partial /7 failed /2 resource-interrupted scenarios. See LOCAL_14B_RESULTS.md. Historical 7B/8B 8/10 results measure an earlier tool set |
| Exact authorization and separate worker | VERIFIED local | execution.py/worker.py; approval payload, authorization refresh, atomic reserve/outbox/job, leases, concurrency, UNKNOWN/status recovery |
| Independent financial sandbox and evaluator | VERIFIED local arithmetic/behavior | Separate world process/DB/math; oracle v2 checks cash/minimum/debt/payables/deadlines; late settled salary must fail |
| Optional signed webhook ingestion | VERIFIED internal sandbox contract | hooks.py + actual FastAPI endpoint test; HMAC, replay/dedup and authoritative status lookup; no real bank webhook |
| Text/PDF retrieval and evidence export | PARTIAL | Actual pypdf subprocess + role/version/cutoff lexical retrieval/source links; PDF injection test and browser Chinese document; OCR/OFD/XML/OS memory limits missing |
| General event automation, alerts and broad synthetic world | PARTIAL | Observed conditional decisions and workflow replan implemented; alert inbox/debounce and linked multi-company generator remain |
| History semantics | VERIFIED in tested scope | Immutable fact cutoffs and policy observation cutoff; migrations preserve legacy unknown times; tests/test_policy_history.py and PostgreSQL regression |
| Deployment/release | PARTIAL | Fresh installed-dependency/DB rehearsal passed; no Git release, hosted deployment or remote CI run |

Latest full regression: **163 tests PASSED**, 144.756 s, including PostgreSQL:
`artifacts/regression-agent-data-v3.json`: **96 PASSED / 4 NOT_RUN**.
The current UI was checked read-only in the actual browser: ten routes,
Chinese/CNY, saved answer and exact approval.
`artifacts/browser-resource-stage.json` and refreshed browser-smoke.json record its
precise scope; the old full golden browser artifact is browser-smoke-pre-live.json.
Historical October 12 LIVE browser proof: browser-live-cpu.json and its workflow JSON
and screenshot. New Qwen cash query completed with correct 120,000 CNY/as-of/source
IDs, one native snapshot tool call and no plan; 2 model calls, 3418 tokens, 117.219 s.
The old paused MOCK workflow and PostgreSQL financial history remain preserved.
Four research/deployment cases remain T023, T031, T032 and T097. New model CPU-memory
limits are resource controls, not private-truth security isolation for T097.

October 13 supplementary LIVE browser probe completed in 317.297 s (2 calls, 4775
reported tokens): correct cash/date but snapshot ID mislabelled as source ID. PARTIAL;
artifacts/browser-qwen14-expanded.json and screenshot. Separate from the 20 cases.
Latest evaluator checks: 11 PASSED; preceding combined evaluator/resource checks:
16 PASSED (6 resource checks); all five quality checks PASSED. The full 163-test
regression above predates these grader/launcher changes.

Resource safeguard implementation: local_llm.py/resource_guard.py/serve.py and six
actual tests (denied allocation, process lifecycle, duplicate guard, reserves,
transient/persistent atomic status-write errors, bounded KV-cache options). Current profile is CPU-only,
2 GiB job commit, mapped weights on E:, weight repacking disabled.
All five checks in `scripts.check` passed after these changes. The user authorized
resumption on E: after reboot and requested models >=4B. This task did not change pagefile settings; after an external reboot Windows reports a 9728 MiB pagefile on E:.

The following evidence list describes the earlier product baseline unless noted:

Actually executed evidence:

- `.venv\Scripts\python.exe -m scripts.test` with SME_POSTGRES_TEST_CONFIG set:
  artifacts/test-results.json (136 actual tests; original timestamps retained).
- `scripts.check`: artifacts/quality-results.json; actual command/output for Python
  and JS syntax, Ruff, mypy and formatting. Read this file for the latest pass/fail.
- `scripts.demo --lost-response`: five SETTLED, final 2,800,000 minor units,
  minimum 2,000,000, zero outstanding/debt/discrepancy/missed deadlines.
- `scripts.rehearse`: fresh copied source, fresh venv, installed pinned wheels,
  new financial/world databases, same successful oracle v2 result.
- `scripts.benchmark`: three actual deterministic paired comparisons; live B1/B2/B3
  and empirical SME/model-quality metrics remain NOT_RUN.
- Actual browser: completed `.runtime/product` golden with restart and one UNKNOWN;
  evaluator re-read its persisted world with oracle v2, success true. PostgreSQL
  `.runtime/pg-workspace` separately exercised policy sensitivity, conditional
  confirmation, CSV review, Chinese retrieval and checkpoint/payload refresh. That
  exploratory PG browser session is PAUSED and is not claimed as a completed golden.
- `scripts.licenses`: 62 installed distribution metadata records. Missing license
  fields remain UNKNOWN; no legal permission inferred.
- Historical live doctor: a later Qwen3 connectivity probe passed; that runtime was
  removed. Connectivity alone does not prove task quality or current availability.

Detailed original requirement text, code, verification and status:
[ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md), [RESULTS.md](RESULTS.md),
[BACKLOG_PROGRESS.md](BACKLOG_PROGRESS.md). Remaining tasks and exact resumption
state are in [CONTINUATION.md](CONTINUATION.md). No real payment, paid service,
external notification or real-client-data transfer occurred.
