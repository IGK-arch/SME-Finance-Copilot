# Security self-assessment report

Topic E · SME Finance Copilot · version 0.3.0 · updated 20 Oct 2026 ·
<https://github.com/IGK-arch/SME-Finance-Copilot>

Scope: the code in this repository running on synthetic data with a simulated
bank (sandbox), either locally or on a single VPS behind HTTPS. No real money, real bank, real customer data or paid
service is connected. Every statement below points to code or a test that can be
re-run; nothing here is a legal, regulatory or bank certification.

## 1. Design principle

The language model is an advisor, never an actor. It can read scoped data, run
deterministic calculations and propose a plan. It cannot approve, send, cancel or
change money, policies or records. Every payment needs one exact approval by a
human OWNER for one exact payload, then a separate worker re-checks everything
before the sandbox bank is called.

```
model (read / compute / propose)  ──►  server validation  ──►  OWNER exact approval + step-up
        no money tools                   independent             one action, one payload hash
                                         validator
                                              │
                                              ▼
              reconciliation  ◄──  sandbox bank  ◄──  worker (re-checks, stable idempotency key)
```

## 2. Permission tiers

### 2.1 Agent (model) tiers

| Tier | What it allows | Agent tools | Who can trigger it |
|---|---|---|---|
| T0 · Read | Scoped, paginated reads of tenant data and documents (untrusted text) | `get_financial_snapshot`, `list_business_records`, `read_business_record`, `search_documents`, `get_evidence`, `get_plan_details`, `get_action_status`, `get_platform_capabilities` | Model, for OWNER/ACCOUNTANT runs |
| T1 · Compute | Deterministic calculations, no state change to facts | `calculate_business_metrics`, `forecast_cashflow`, `what_if_cashflow`, `screen_financing_products`, `simulate_financing`, `stress_test_plan` | Model |
| T2 · Propose | Create a validated plan or a pending proposal; nothing executes | `optimize_plan`, `prepare_action`, `propose_supplier_extension` | Model; result is a proposal only |
| T3 · Approve | Bind one action to one SHA-256 payload hash | none (no agent tool exists) | Human OWNER only, with step-up re-authentication |
| T4 · Execute | Reserve funds and send to the bank | none | Separate worker process, only after T3 |

The tool registry is in `finance/agents.py`; the tool list and read boundaries are
documented in [AGENT_CAPABILITIES.md](../AGENT_CAPABILITIES.md). Detail tools are
only exposed after the model has obtained matching record IDs, and the server
rejects fabricated or mismatched plan/action IDs.

### 2.2 Human role tiers

| Capability | OWNER | ACCOUNTANT | AUDITOR | ADMIN | Enforced in |
|---|:-:|:-:|:-:|:-:|---|
| Read workspace, reports, audit | ✓ | ✓ | ✓ | ✓ | `finance/store.py` `READ_ROLES` |
| Import / map data, review quarantine | ✓ | ✓ | – | – | `finance/ingestion.py`, `finance/mapping.py` |
| Start Copilot, compute options | ✓ | ✓ | – | – | `finance/copilot.py` `COPILOT_ROLES` |
| Change policy (reserve, limits) | ✓ | – | – | – | `finance/workspace.py:129` |
| Approve a payment (exact payload + step-up) | ✓ | – | – | – | `finance/execution.py` `approve`, `finance/digest_check.py` `step_up` |
| Revoke approval, cancel plan | ✓ | – | – | – | `finance/execution.py` `revoke`, `cancel_plan` |
| Stop new sends (kill switch) | ✓ | – | – | ✓ | `finance/execution.py` `stop` |
| Resume sends | ✓ (only after matched reconciliation) | – | – | – | `finance/execution.py` `stop`; test `test_resume_requires_matching_reconciliation` |

Tenant and role come from the membership record on every request, never from a
request field. Tests: `tests/test_audit_fixes.py::test_R4_R5_role_boundaries`,
`test_auditor_cannot_start_copilot`.

## 3. Controls implemented

| Area | Control | Evidence |
|---|---|---|
| Authentication | Membership token exchanged for an 8-hour HttpOnly, SameSite=Strict session cookie stored as a hash; logout revokes; membership re-checked per request | `finance/asgi.py` `/session` |
| Step-up for money | Browser approval requires re-entering the owner token; legacy browser money routes are closed | `finance/digest_check.py`; test `test_S01_browser_session_needs_step_up_and_no_legacy_route` |
| Exact approval | Server recompiles the command and compares the reviewed payload hash; one approval per action, no approve-all; 24-hour real-time TTL; revocable | `finance/digest_check.py`, `finance/execution.py`; tests T071–T073 |
| Freshness | Approval rejected if facts, policy, beneficiary or plan changed after the command was built | `tests/test_audit_fixes.py` R-series |
| Financial limits | Hard reserve; annualised cost cap is a hard solver constraint; validator re-checks independently | `finance/planner.py`, `finance/validation.py`; test `test_S02_cost_cap_is_a_hard_constraint` |
| Independent validation | Validator never calls the solver or its trajectory code | `finance/validation.py` |
| Idempotency | Stable key per tenant/action; status lookup before any resend; UNKNOWN keeps the reserve | `finance/worker.py`; E2E `lost_response_single_attempt` |
| Atomicity | Approval check, reservation, outbox and job in one transaction | `finance/execution.py` `prepare` |
| Tenant isolation | PostgreSQL FORCE row-level security keyed on `session_user`; immutable ledger/source rows | `finance/postgres.py`, ADR 0003 |
| Audit trail | Every audit record stores the actor role and is hash-chained; tampering is detected | `finance/store.py` `verify_audit`, `scripts/verify_audit.py`; test `test_S06_audit_records_actor_and_detects_tampering` |
| On-chain anchor | Chain head published on a public testnet; mainnet refused; only OWNER/ADMIN may anchor; only hashes leave the machine; testnet wallet holds no business money | `finance/anchor.py`; `tests/test_anchor.py` |
| Prompt injection | Documents are labelled untrusted; no tool can be added by document text; model has no SQL, shell, secret or payment tool | `SECURITY.md`; injection tests in `tests/` |
| Web | CSP `style-src 'self'`, DOM built from text nodes (no `innerHTML` with data), same-origin check, no tokens in localStorage or URLs | `web/ui.js`, `finance/asgi.py` |
| Honest status | SUBMITTED is never shown as paid; case is RESOLVED only after settlement and matched reconciliation | `finance/cases.py`; E2E `case_resolved_only_after_reconciliation` |
| Model fallback | A failing live model is recorded as a failed run, never silently replaced by MOCK | test `test_R8_unreachable_model_is_recorded_as_failed_run` |
| Webhooks | Optional HMAC-SHA256 signed wakeup with 300 s window; body is never trusted for balances; a replayed event ID does no work | `finance/hooks.py`; test `test_replayed_signed_webhook_does_not_reconcile_again` |
| DNS rebinding | `Host` must be a loopback name (or one listed in `SME_ALLOWED_HOSTS`); other hosts get 400 before any route runs | `finance/asgi.py` `host_allowed`; `tests/test_security_hardening.py` |
| Security headers | CSP with `object-src 'none'`, `form-action 'self'`, `frame-ancestors 'none'`; `X-Frame-Options`, COOP, CORP, `Permissions-Policy`, `nosniff`, `no-referrer`, `no-store`; HSTS when served over HTTPS | `finance/asgi.py` |
| Brute force | Failed sign-ins and failed API bearer tokens each lock after 20 failures in 5 minutes (429); step-up locks after 5 wrong confirmations | `finance/asgi.py` `FailureLimiter`, `finance/digest_check.py` |
| Security logging | Failed sign-ins, bad tokens, lockouts, foreign origins/hosts, missing CSRF header and rejected sessions go to the `sme.security` logger as JSON lines without tokens, cookies or bodies | `finance/asgi.py` `security_event` |
| Agent audit | Every model-initiated proposal (`optimize_plan`, `prepare_action`, `propose_supplier_extension`) adds an `agent.tool_call` record to the hash-chained audit, marked `executed: false` | `finance/agents.py`; test `test_model_proposals_are_in_the_hash_chained_audit` |
| Input parsing | JSON refuses `NaN`/`Infinity`; deep nesting is a 400, not a 500; workbook XML must be plain UTF-8 with no DTD or entity declarations (XXE, entity expansion) | `finance/asgi.py` `parse_body`, `finance/mapping.py` `safe_xml` |
| Supply chain | Pinned `requirements.lock`; license inventory; CI runs a secret scan and an OSV vulnerability audit of every pinned package; CI actions pinned to commit SHAs with a read-only token | `scripts/security_scan.py`, `scripts/licenses.py`, `.github/workflows/ci.yml` |

## 4. Compliance considerations

- **Data minimisation and residency.** All data is synthetic and stays on the
  machine that runs the application; no third-party API receives financial data. The
  optional self-hosted model is reached only through an authenticated SSH bridge
  that exposes chat endpoints and no financial tools.
- **Human in the loop.** No autonomous money movement: every action has a human
  OWNER approval of the exact amount, recipient and terms.
- **Explainability.** Each number carries snapshot ID, calculation version and
  source references; options show why they are infeasible.
- **No advice claims.** Financing products are labelled DEMO; eligibility is not
  lender approval; scenarios are uncalibrated and not probabilities of default.
- **Separation of duties.** ACCOUNTANT prepares, OWNER approves, AUDITOR reads,
  ADMIN can stop sends but cannot approve payments.

## 5. Known-risk list

Severity is for a hypothetical production deployment; in the current local
synthetic setup the impact is limited to demo data.

| ID | Risk | Severity | Current mitigation | Status |
|---|---|---|---|---|
| K01 | Host or database administrator can replace the database, including the hash-chained audit | High → Medium | Hash chain detects edits by non-admins; the chain head is anchored on a public testnet (`scripts.anchor_audit`), so a consistent rewrite of anchored records is detected. Records after the last anchor stay unprotected until the next anchor | Partly mitigated |
| K02 | API and worker share one PostgreSQL tenant role; no worker-only grant set | Medium | RLS still limits both to one tenant | Open |
| K03 | Simulator and LangGraph SQLite files are not in separately permissioned containers; no OS-level isolation of private simulator truth | Medium | Process separation and tools never expose private world state | Open |
| K04 | Credentials live in ignored local files, not a secret vault | Medium | `.gitignore`, no secrets in outputs/URLs/localStorage | Open (by design for local demo) |
| K05 | No SSO or per-user accounts; roles are bearer membership tokens | Medium for hosting, Low locally | The application binds to 127.0.0.1; public hosting goes through Caddy with Let's Encrypt HTTPS, HSTS and a host check (`SME_PUBLIC_ORIGIN`); tokens are exchanged for HttpOnly SameSite=Strict sessions; lockouts and security logging | Partly mitigated |
| K06 | Live model prose can still contain semantic errors even when tool calls pass | Medium | Result cards come from tool results, not prose; exact money references are validated; failures recorded in evaluation reports | Open, measured |
| K07 | Prompt injection through imported documents against a live model | Medium | No dangerous tools exist; documents labelled untrusted; historical EN/ZH LIVE attack scenarios and failures are recorded, but no independent robustness guarantee | Partly mitigated |
| K08 | Document parser has time/size bounds but no OS memory sandbox | Low | Subprocess with resource limits | Open |
| K09 | No compensating payments or external cancellation; UNKNOWN reserves cannot be force-released | Low (safety over liquidity) | Status lookup by stable key | Accepted |
| K10 | Business analysis is descriptive; P&L is not computed from bank data | Low | Labelled `INSUFFICIENT_DATA` | Accepted |
| K11 | Alerts have no acknowledgement/debounce workflow | Low | Alerts are idempotent per rule/subject | Open |
| K12 | Testnet wallet key is stored in the ignored workspace folder | Low (testnet coins only) | Separate from business credentials; mainnet refused by chain-id check | Accepted |
| K13 | The model server's public IP address remains in old commits; current tracked-file scan found no matching secrets, while history reports public-IP findings | Low | The address is not a credential: the model host accepts only key-authenticated SSH with a pinned host key, and keys live in ignored files. Current files contain no address; `scripts.security_scan --history` lists the old commits. Scanner coverage does not prove the absence of every possible secret | Accepted (owner decision 18 Oct: history not rewritten) |
| K14 | Sign-in and token lockouts are global per process, so repeated bad attempts can delay legitimate sign-in for five minutes | Low locally | Loopback binding; separate budgets for browser sign-in and API tokens | Accepted |
| K15 | Incorrect settlement identity previously allowed false SETTLED and early reserve release | High for real integration; synthetic-only impact here | Exact identity check before allocation/completion; durable tenant-scoped issue, reserve retention and send/resume block; 15 targeted tests and full regression/E2E passed. No automatic dispute clearing or historical repair | Fixed for the synthetic adapter, 19 Oct; real adapters require a separate contract/review |
| K16 | On a shared public demo, everyone holding the same role token acts on the same synthetic company | Low (synthetic data, sandbox bank) | Give reviewers the least role they need (AUDITOR for read-only); step-up still required for approvals; a fresh seeded workspace can replace it. The optional public demo key (`SME_DEMO_LOGIN_ROLE`, off by default, never ADMIN) shows one role's token on the sign-in page; it is meant only for this synthetic, sandbox-only demo | Accepted for the demo |

## 6. How to verify

```bash
python -m scripts.test        # full regression
python -m scripts.check       # ruff, mypy, format, JS syntax
python -m scripts.e2e_v03     # product path through server + worker + sandbox
python -m scripts.verify_audit --directory .runtime/workspace   # audit chain
```

Latest full run (20 Oct 2026, Windows 11, CPython 3.11.9): **381 tests, 377 PASSED,
4 PostgreSQL SKIPPED, 0 failed**, including 15 settlement-identity and 11
security-hardening tests. Product E2E: 23/23 PASSED (MOCK model). Golden scenario: 5/5
actions, zero cash difference. `scripts.check`: 9/9 PASSED. PostgreSQL row-level
security tests run only with `SME_POSTGRES_TEST_CONFIG` set and were skipped here.
Raw report: `artifacts/release-20261020/regression.json`.
