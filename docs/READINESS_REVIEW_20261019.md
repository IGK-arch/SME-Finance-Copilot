# Submission readiness review — 19 October 2026 (Moscow)

> Internal pre-submission engineering review of 19 Oct 2026, kept for transparency. Its findings were addressed afterwards (settlement identity fixed, see ADR 0006); current results are in the README.

> **19 Oct Business health follow-up:** AUD-05 integration gap closed: shared typed metrics/forecast/what-if, saved results and agent card. Fresh regression 328 PASS / 4 PG SKIP, targeted17, E2E23/23 MOCK, static9/9. Qwen EN/ZH20 complete:14 strict PASS, but prose11 COMPLETE/2 PARTIAL/7 FAILED. OPEN-12 retains the narrative-quality blocker; overall HOLD and other findings remain. See [measured report](BUSINESS_HEALTH_AGENT_20261019_RU.md). The audit below is historical evidence, not a claim that health tools are still missing.

**Status: HOLD for final submission on remaining items.** Follow-up on 19 Oct: AUD-01/K15 is fixed for the synthetic adapter; targeted 15/15, regression 311 PASS / 4 PG SKIP, HTTP E2E 23/23, golden 5/5, static 9/9. [Fix report and limitations](SETTLEMENT_FIX_20261019_RU.md). The original audit observations and counters below are preserved; the other findings and submission packaging remain open. This is an engineering review by the coding assistant, not independent certification or a predicted competition score.

Audited application commit: `d3764f0a5155fe0153e3b7d807f0fa37d78640d3` (`security-hardening`). The working tree was initially clean. Application code and financial safeguards were not modified by this review. New diagnostic harnesses, evidence and documentation are additional uncommitted work. Full analysis: [Russian audit](PRE_SUBMISSION_AUDIT_RU.md). Slide-by-slide corrections: pitch review (working notes, not in the repository).

## Fresh evidence

All paths below refer to `artifacts/submission-audit-20261019/`:

| Check | Actual result | Evidence |
|---|---|---|
| Regression | 300 run: **296 passed, 4 skipped, zero failed** | [regression.json](../artifacts/submission-audit-20261019/regression.json) |
| T001–T100 | 95 PASSED, 5 NOT_RUN: T023, T031, T032, T094, T097 | Same report; old browser evidence no longer matches current web hashes |
| HTTP product lifecycle | 23/23 checks passed, including exact approval, step-up, lost response, server restart, independent bank reconciliation | [e2e.json](../artifacts/submission-audit-20261019/e2e.json); MOCK, no LIVE model decisions |
| Golden lifecycle | 5/5 SETTLED; CNY 29,000 final cash; CNY 20,000 minimum; no outstanding debt/payables or missed deadlines; zero discrepancy | [golden-latest.json](../artifacts/submission-audit-20261019/golden/golden-latest.json) |
| Static and dependency consistency | 10 checks passed; installed pins match | [static-checks.json](../artifacts/submission-audit-20261019/static-checks.json), [inventory](../artifacts/submission-audit-20261019/installed-dependencies.json) |
| Security scan | Current tracked files passed; OSV checked 80 packages without reported vulnerabilities; history scan FAILED on 15 old public-IP occurrences | [security-scan.json](../artifacts/submission-audit-20261019/security-scan.json); accepted K13, not rewritten |
| Edge browser smoke | Six pages at 390/768/1440 px, 18 renders, seven assertions passed | [browser-smoke.json](../artifacts/submission-audit-20261019/browser-smoke.json); isolated synthetic workspace, not a full browser payment E2E or accessibility certification |
| Public anchor | Sepolia receipt status 1, block 11941459, value 0, 65-byte payload, 72 records, recorded hash matches | [public RPC check](../artifacts/submission-audit-20261019/onchain-public-check.json); read only |
| Repository readiness | Private; default main behind audited branch; PR #4 open; CI on audited HEAD succeeded | [GitHub snapshot](../artifacts/submission-audit-20261019/github-readiness.json) |

PostgreSQL tests were skipped because no test connection was configured. Fresh selected-model LIVE evaluation, clean-room install, participant study and operating-system isolation tests were not run. A new browser smoke is not silently counted as a replacement for the acceptance collector's missing T094 evidence.

## Open findings

1. **P0 — settlement identity (AUD-01 / K15).** The reconciliation code matches an action by provider reference or stable key and checks its amount. An observation with the same amount but a wrong counterparty or obligation reference still marks that action SETTLED and releases its reservation. In both fresh synthetic probes, payroll remained CNY 80,000 outstanding while cash reconciliation reported zero difference and sends were not stopped. This is provider-fault injection, not evidence of an external exploit. Preserve actual cash movements, but require unambiguous command/observation identity before completing the action. [Reproductions](../artifacts/submission-audit-20261019/adversarial-probes.json).
2. **P0 — submission tree and access.** Pin the final commit/archive, resolve the open security PR, arrange judge access to the private repository and verify a clean download. No repository publication or merge was performed by this audit.
3. **P0 — final materials.** The received 17-page PDF contains team/contact/photo placeholders, a broken `92/100` line, outdated counters and overbroad guarantees. No final video or editable presentation source was found in the repository. The PDF's apparent Live demo button has no link annotation. Do not mark these as submitted without the actual materials.
4. **P0 — claims consistency.** Use one dated release manifest. Historical runs remain historical. A successful golden case, historical model benchmark and fresh full regression establish different things.
5. **P1 — agent health calculations.** The new Money-page `compute.analysis` outputs are absent from the agent's calculation contract. `calculate_business_metrics` still exposes four basic cash/obligation metrics. Raw records are available, but requiring model arithmetic is not a substitute for a typed calculation tool.
6. **P1 — release gates.** Run selected Qwen through a few complete EN/ZH request-to-reconciled-result paths after fixes; run the four PostgreSQL integration tests in a separate test database. CI currently omits `scripts.e2e_v03`, browser checks and PostgreSQL.
7. **P1 — anchor scope and privacy.** The deterministic tenant hash is a stable pseudonymous tag, not a secret/randomly salted identifier. Count and transaction metadata are public. The anchor protects an agreed prefix relative to a trusted transaction hash; it neither verifies the meaning of original facts nor protects later unanchored records. Local records are required to recompute the commitment. The current `verify` helper does not establish a finality depth; this audit separately checked the successful receipt.
8. **P1 — distribution rights and export.** Project code has an MIT license. Supplied R1–R3 redistribution rights and the exact served model's weight identity/license require separate verification. The export helper copies all tracked files, excludes new untracked files, and changes four current tracked files through regex sanitization. Test the exported tree and retain a redaction/provenance manifest; do not overwrite raw measurements.
9. **P2 — independent quality and usability.** Add a new EN/ZH document holdout and observed SME-owner tasks. Measure time and errors before claiming savings or universal correctness. Lexical retrieval, text-only PDF and no OCR remain explicit boundaries.

## Model evidence: what 92/100 means

The selected LIVE provider remains `qwen3.8-flash-next-iq3_xxs` on Strata. Its runtime alias does not prove parameter count or a weight-file checksum. No model switch was made.

The 17 October developer benchmark has 100 scenarios per reasoning mode: 67 EN and 33 ZH, one primary outcome per mode/case, not a blind independent holdout. Strict automatic passes were **87/100 (none)** and **92/100 (medium)**. Assistant semantic review classified **77/100** and **80/100** COMPLETE; the intersection of strict PASS and COMPLETE was **76/100** and **75/100**. Full-scenario p50/p95 was **30.946/71.902 seconds** and **28.236/53.618 seconds**. One case per mode was refused by server authorization before a model call. Automatic PASS is not a guarantee that every sentence is correct. [Full method and failures](REASONING_100_RESULTS_RU.md).

The previous 500 alternative-model outcomes remain preserved; they do not constitute a fresh test of this application commit. Default runnable demo remains explicitly MOCK. No adaptive reasoning policy has been validated.

## Criteria and submission decision

The requested 40% task completion / 30% security / 30% innovation-and-interaction rubric is used. Strength: a real source-to-plan-to-approved-operation-to-independent-observation lifecycle. Weakness: completion is overstated when settlement identity, current LIVE lifecycle and delivery packaging are incomplete. The on-chain anchor is supplementary evidence; no bonus score is guaranteed.

The [official homepage](https://fintechathon.g-ican.com/) currently gives **20 OCT** for the International AI deadline and UTC+8 for dates. Its general AI scoring table differs from the supplied international brief. Confirm the applicable international rules; do not substitute domestic-track dates. Detailed 23:59 timing and eligibility checks remain based on supplied R1 rather than a newly authenticated organizer decision.

AUD-01 is now fixed and retested in the working tree. Release still requires a single accessible release tree; final deck/video/team fields; synchronized claims; and explicit acceptance of remaining limitations. Do not relax approval, tenant, resource or provider-identity safeguards to make a demo pass.
