# v0.3 plan — owner main path first

Date: 13 Oct 2026. Basis: `SME_Copilot_v0_3_Audit_UX_Package` (README, AUDIT_AND_UX_SPEC_RU,
CODEX_NEXT_ITERATION, UX_Prototype.html, reference_previews) and the owner's clarification of
13 Oct 2026. The clarification changes only the **order** of work: the local 14B model is a
temporary integration model, so model optimisation (quantisation, CPU inference, fine-tuning,
prompt workarounds, graph rebuilds for its score) is not the main direction. Safety, financial
invariants, correct sources and honest statuses are not postponed.

Status words: DONE (implemented and verified here), PARTIAL, NOT_STARTED, DEFERRED_MODEL
(waits for the target model; never reported as passed from MOCK). IDs are unchanged from the package.

## Order of work

| # | Stage | Package IDs | Status | Evidence |
|---|---|---|---|---|
| 1 | Audit the current cabinet in the browser, keep the initial state; baseline regression | V03-01 | DONE (Git baseline `aaf467d`, 14 Oct) | `artifacts/v03/baseline/`, `artifacts/v03/baseline-regression.json` (169 PASSED; 96/4) |
| 2a | Read models for the main path: Home, financial case, options, action review, timeline, activity | V03-09, V03-02 | DONE | `finance/cases.py`, `finance/digest_check.py`; tests V03_09/10/11/12; health label fixed |
| 2b | New cabinet: Home, Plans (case + comparison), exact approval dialog, Activity timeline, Money, Documents, Settings; Copilot as a panel | V03-10, V03-11, V03-12 | DONE (usability study open) | `web/`; browser walkthrough; layout 390/768/1366/1440 |
| 3 | Product functions the path needs: distinct strategies, infeasibility reasons, per-obligation what-if, import with mapping/review, alerts, saved user context, server session | V03-13, V03-16, V03-17, V03-18, V03-15 | DONE; alerts PARTIAL | tests V03_13/16/18/15; ADR 0005 |
| 4 | Agent kept and integrated: context panel, real graph in background, result cards before narrative, clarifications/approval/wait pauses; swappable adapter retained | V03-05 (done); V03-03/04/06/08 | V03-05 DONE; rest DEFERRED_MODEL | `finance/copilot.py`, `web/copilot.js`, test V03_05 |
| 5 | Product process through backend + worker + sandbox: changed inputs, restart persistence, exact approval, lost response, no double charge | V03-14 (product part), V03-23 | DONE for the product path; LIVE part DEFERRED_MODEL; Playwright runner not available | `scripts/e2e_v03.py` → `artifacts/v03/e2e-latest.json` (21/21) |
| 5b | UX pass (14 Oct): boot/loading/error/not-found states, phone/tablet bottom tab bar, charts at on-screen width, compact metrics, file picker, readable server dates, owner's logo | V03-10, V03-24 (layout part) | DONE | `artifacts/v03/browser-v03.json` (ux_pass), screenshots in `artifacts/v03/browser/` |
| 6 | Reporting: plan, acceptance matrix, ADR, limitations | V03-25 | DONE for this iteration | this file, `docs/ACCEPTANCE_MATRIX_V03.md`, `docs/adr/0005-v03-owner-main-path.md` |

## After the target model is connected (DEFERRED_MODEL)

14 Oct update: the owner requested and authorized Strata server connection and
scenario testing. The adapter and synthetic evaluation now exist; see
`STRATA_RESULTS_RU.md`. This does not select it as the final target model or close
the gates below. Repeated narrative amount errors remain a blocker for trusted answers.

Repeat the same process starting from a free-form owner request, with the existing guards:
V03-03 CompletionGate, V03-04 AnswerBundle validation of model text (amount/sign/date/source type),
V03-06 skills and scoped tools with measured step counts, V03-08 latency profile (cold/warm),
V03-14 LIVE end-to-end, V03-19 Chinese retrieval holdout. Keep the 20 historical LIVE cases and
their grader for comparability; add authorized execution tasks and a closed holdout. A new provider
is added as a `ChatGateway` provider with explicit opt-in; no quality is claimed beforehand.

## Approval expiry completed

V03-20 is implemented: new approvals also expire after 24 real hours, independently
of the synthetic clock. Pre-v0.3 approvals without a TTL record keep business-time
expiry only. Verified again by the 14 Oct targeted run (see CURRENT_STATE_RU.md).

## Open items not done in this iteration

- V03-07 server-side filters/aggregates for agent reads; V03-21 unrelated-change
  tolerance; V03-22 process isolation/roles/backup — not started.
- The 14 Oct refresh found a Windows SQLite cleanup error in the background Copilot
  test; an isolated rerun passed. Cleanup reliability remains to be investigated.
- V03-17 alerts: first-seen dedup projection exists; no debounce scheduler or acknowledgement.
- V03-23 Playwright runner: no Playwright/Node packages installable on this host (registries blocked);
  evidence is a recorded walkthrough in the built-in browser plus the HTTP E2E above.
- V03-24 usability study with 3–5 independent participants and keyboard/zoom audit by a person.
- Imported payables for new counterparties have no verified beneficiary and are unknown to the
  sandbox world, so their payment stays blocked (honest, visible in review).
- The legacy cabinet (`/legacy`) still hosts manual allocation and raw synthetic CSV import.
