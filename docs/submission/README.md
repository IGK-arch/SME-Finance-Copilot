# Submission index — International Track, Topic E

SME Finance Copilot: an AI finance copilot for small-business owners that finds a
coming cash gap, matches financing, and carries the chosen plan through exact
owner approval, sandbox execution and reconciliation.

Repository: <https://github.com/IGK-arch/SME-Finance-Copilot> · license MIT ·
what data is used: see the [data note](../../README.md#sme-finance-copilot).

## Submission checklist (rules §5)

| # | Required item | Where |
|---|---|---|
| 1 | Technical documentation (architecture, core algorithms, security design) | [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) · [architecture notes](../architecture/README.md) · [ADRs](../adr/) |
| 2 | Presentation deck (≤ 10 min) | Submitted separately; storyline in [demo-script.md](demo-script.md) |
| 3 | Demo video (≤ 5 min, optional) | Submitted separately; script in [demo-script.md](demo-script.md) |
| 4 | Source code with README, deployment instructions and test cases | [GitHub repository](https://github.com/IGK-arch/SME-Finance-Copilot) · [README](../../README.md) (Windows, Linux, macOS setup; [VPS deployment](../runbooks/deploy.md)) · `tests/` (latest full run, 20 Oct 2026: 377 PASS / 4 PostgreSQL SKIP / 0 FAIL) · CI in `.github/workflows/ci.yml` |
| 5 | Security self-assessment (permission tiers, known risks) | [SECURITY_SELF_ASSESSMENT.md](SECURITY_SELF_ASSESSMENT.md), audit findings and fixes in [SECURITY_AUDIT.md](SECURITY_AUDIT.md) |
| 6 | Execution evidence (sandbox operation logs + demo video) | [EXECUTION_EVIDENCE.md](EXECUTION_EVIDENCE.md) (sandbox logs, Sepolia transaction hash) · raw `artifacts/golden-latest.json`, `artifacts/v03/e2e-latest.json` · demo video submitted separately |

## Scoring criteria (rules §3)

### Task completion (40%)

- All three Topic E capabilities: financing-option matching, cash-flow
  management with alerts, business financial analysis
  ([technical documentation §1](TECHNICAL_DOCUMENTATION.md#1-problem-and-scope)).
- Goes past advice to a completed, reconciled outcome: 5/5 actions settled,
  zero discrepancy, case closed only after reconciliation
  ([execution evidence](EXECUTION_EVIDENCE.md)).
- Real solver (OR-Tools CP-SAT) checked by an independent validator; real agent
  graph (LangGraph) with typed tools.

### Security & compliance (30%)

- Five permission tiers for the agent (read, compute, propose; approve and
  execute are human/worker only) and four human roles with separation of duties.
- Exact payload-hash approval with step-up, freshness checks, reservations,
  idempotency, kill switch, row-level security, hash-chained audit.
- Known-risk list K01–K16 with open, partly mitigated or accepted risks
  ([security self-assessment](SECURITY_SELF_ASSESSMENT.md)).

### Innovation & interaction (30%)

- One-problem home screen: problem → cause → options → choice → exact approval
  → execution → reconciled result.
- Options compared side by side, with honest INFEASIBLE reasons, and a what-if
  for one late or partial customer payment.
- Copilot as a context panel: result cards come from tool results, so the model
  cannot change a number on screen.
- Recovery from a lost bank response without double payment, shown live.
- English interface with Chinese counterparty data; Copilot evaluated on English and Chinese questions; layout works on phone, tablet and desktop.

### Challenge bonus (on-chain exploration, 0–5)

On-chain proof of the audit trail ([technical documentation §3.9](TECHNICAL_DOCUMENTATION.md#39-on-chain-proof-of-the-audit-trail)).
The head of the hash-chained audit log is published as a zero-value transaction on
a public testnet (Ethereum Sepolia by default). Anyone can later check that the
local records still produce the anchored hash, so even an administrator who
rewrites the anchored records and recomputes every hash can be detected against
a trusted saved transaction hash. Local records are needed for verification.
The payload contains a deterministic pseudonymous tenant tag, record count and
chain-head commitment; no business amounts or document text.

```bash
pip install -r requirements-onchain.txt
python -m scripts.anchor_audit wallet               # testnet address to fund from a faucet
python -m scripts.anchor_audit send                 # anchor the current chain head
python -m scripts.anchor_audit verify --tx 0x...    # check an anchor against local records
```

Transaction hashes are listed in [EXECUTION_EVIDENCE.md](EXECUTION_EVIDENCE.md#3-on-chain-anchors).

## Reproduce in five commands

```bash
pip install -r requirements.lock
python -m scripts.test            # regression
python -m scripts.check           # lint, types, format
python -m scripts.demo --lost-response
python -m scripts.e2e_v03 && python -m scripts.execution_log
```
