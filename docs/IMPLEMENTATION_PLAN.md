# Implementation plan — Topic E (full-product continuation)

## Current ordered implementation

A–F below are substantially implemented and tested; G now includes actual PostgreSQL.
Full acceptance remains PARTIAL. The exact outstanding order is CONTINUATION.md;
historical milestone/P1 paragraphs below record the original plan, not current status.

The first milestone below is historical; it is not the product completion gate.
CODEX_BUILD_FULL_PRODUCT.md expands the active target to full P0 + product/agent P1.

1. A — Persistent startup/resume and separate durable execution worker; prove
   restart preserves tokens, facts, plans, approvals and unknown operation keys.
2. B — Review quarantined rows, allocation actions, settings, source retrieval;
   prove versioned correction changes computed forecasts without duplicate cash.
3. C — OR-Tools compiler/solver plus independent validator and oracle comparisons.
4. D — LangGraph checkpoints, typed tools, bounded model gateway, clarification,
   approval/observation resume; offline tests and separately gated live smoke.
5. E — F1 partial/correlated scenarios, conditional requests and observed replans,
   document text ingestion, permission/version-filtered retrieval and evidence.
6. F — Complete linked English workspace routes and real browser E2E.
7. G — PostgreSQL integration/deployment gates, full regression, clean setup,
   reports, I/T/W acceptance matrix and precise continuation point if incomplete.

Use ADR 0002; preserve the useful existing financial kernel. P2 remains real banks,
FX, specialized training and empirical model evaluation on authorized data.

## Historical milestone plan

Source of truth: MASTER_SPEC.md, clarification D01–D20, I01–I36, T001–T100.
The original handoff files and AGENTS.md are preserved. This directory had no Git
metadata or application code on inspection (2026-10-12); Git change attribution
therefore cannot be established. Do not create a release tag without a repository.

## P0: single-company executable milestone

1. S0: inventory, ADR, fail-closed configuration, versioned contracts and migrations.
2. S1: strict minor-unit money; scoped repositories; source hashes; CSV quarantine;
   immutable fact versions; observed/effective cutoffs; matching and snapshots.
3. S2: independent sandbox process/database, observation-only capability and oracle.
4. S3: F0/F1 DEMO forecasts; tri-state eligibility; fees/net proceeds/repayment tail;
   bounded discrete optimizer and separately implemented plan validator.
5. S4: exact expiring/revocable approvals; current authorization; reservations;
   transactionally committed outbox; stable keys; status recovery and reconciliation.
6. S5: bounded mock workflow, scoped evidence; English working dashboard; source,
   plan, approval, operation and evidence screens backed by the service.
7. S6: actual acceptance results, fault/race/security tests, deterministic baselines,
   golden evidence, fresh-directory rehearsal and operational documentation.

Each gate records commands/results and limitations in docs/ITERATIONS.md. Test
results live in artifacts/test-results.json. Unimplemented targets remain NOT_RUN.
Passing a narrower test is not evidence for an unimplemented integration.

## P1

PDF/XML/OFD/OCR adapters with isolated resource-limited parsers; calibrated payment
models and temporal/company holdouts; richer contingent DAGs; reviewed products;
production framework migration; authorized real-model evaluation; accessibility
and browser matrix; expanded synthetic world and benchmark diversity.

## P2

Specialized training/distillation/RL after measured errors; consented production
data; independently tested banking adapters; FX; statutory accounting; hosted
deployment and legal/security review. Blockchain/Agent Wallet excluded.

## Dependency gates

No external dataset, bank, model or paid service is used. Real-model metrics,
external licenses, production integrations, competition rule updates and legal
applicability remain unverified. APIs offered by this project are internal SPEC
contracts, not representations of a bank API.
