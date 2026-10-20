# Open decisions and production blockers

| ID | Owner role | Status / impact | Next action |
|---|---|---|---|
| OPEN-01 | Project owner | Official international homepage deadline checked 19 Oct; detailed brief/rubric differences and hidden tasks remain unconfirmed | Confirm applicable international brief; see PRE_SUBMISSION_AUDIT_RU.md |
| OPEN-02 | Project owner | Git repo exists and is private; security PR #4 open; deck contains team placeholders | Pin release commit, arrange judge access, verify eligibility and fill actual team details |
| OPEN-03 | Data reviewer | No external datasets loaded; licenses/access unknown | Audit downloaded files/splits/rights before any use |
| OPEN-04 | Integration owner | Synthetic CSV/XLSX mapping supported; independent sandbox adapter only | Obtain consented export samples and versioned real-provider specifications before integration |
| OPEN-05 | Domain reviewer | B2B synthetic parameters uncalibrated | Review 2–5 authorized anonymized examples with an accountant |
| OPEN-06 | Product reviewer | DEMO catalog only | Verify real sources, all terms, expiry, rights and adapter capabilities |
| OPEN-07 | Security/legal reviewer | Production scope/consent/region obligations unknown | Separate production review before real data or financial operations |
| OPEN-08 | Model reviewer | Default MOCK; self-hosted Qwen selected and historical LIVE measured; exact weight licence/identity not proved by runtime alias | Retain selected model; verify actual weight provenance/licence and current LIVE readiness |
| OPEN-09 | Evaluation owner | Selected Qwen current medium120 completed 20 Oct:89/100+7/20, all120 reviewed; prior none88+5 and historical medium92 retained. Production regression366PASS/4PG SKIP and E2E23MOCK remain prior; no fresh PG/UI/LIVE approval-execution lifecycle | Fix measured defects and run release gates; preserve all primary failures. See QWEN_MEDIUM_120_20261020_RU.md and PRE_SUBMISSION_AUDIT_RU.md |
| OPEN-10 | Execution owner | K15 / AUD-01 fixed and verified for synthetic sandbox, 19 Oct: 15 targeted PASS, regression 311 PASS / 4 PG SKIP, E2E 23/23 | See SETTLEMENT_FIX_20261019_RU.md; dispute resolution and historical repair remain unsupported, real adapters require their own settlement contract |
| OPEN-11 | Agent owner | Implemented 19 Oct: typed Business health in metrics, forecast, what-if, capability discovery, saved record reads and Copilot card; AUD-05 integration gap closed | See BUSINESS_HEALTH_AGENT_20261019_RU.md for fresh regression and selected-Qwen EN/ZH outcomes; narrative limitations tracked in OPEN-12 |
| OPEN-12 | Model reviewer | Current medium: main100 strict89, semantic81 COMPLETE/joint78; new20 strict7, semantic5 COMPLETE/joint3. Four output2048 truncations; missed mixed requirements/full reads, entity/source-scope errors, reserve-adjustment suggestion in prose; recorded state protections unchanged | P0 explicit task/entity/completion contract, semantic binding and text-safety; P1 bounded completion/reconciliation evidence, then paired120 and independent holdout. No global reasoning switch proven. See QWEN_MEDIUM_120_20261020_RU.md |

Owner roles are responsibilities, not invented team member names. These blockers
do not prevent the synthetic single-company milestone. No real financial operation,
notification, paid service or real-data transfer is authorized by this document.
