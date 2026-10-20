# Security audit, 18 Oct 2026

Scope: the whole repository at `main` 3ef8441, checked against the track's security
criterion (permission tiers, known-risk list) and common application-security practice
(OWASP ASVS areas, LLM tool boundaries, supply chain). Findings were fixed in code with
tests; the remaining items are listed in the
[self-assessment](SECURITY_SELF_ASSESSMENT.md#5-known-risk-list).

## What was checked and found sound

| Area | Result |
|---|---|
| LLM tool boundary | The model has 17 allowlisted tools plus `ask_user`; none approves, sends, cancels or edits money, policy or facts. Arguments are strictly typed and bounded; detail tools accept only IDs the model has already been shown, enforced on the server, not only in the schema. Document text is labelled untrusted. Model endpoint is loopback-only, no proxy, no redirects, response size capped. |
| Payment approval | One OWNER approval per action bound to the SHA-256 of the exact command; server recompiles and compares the reviewed hash; step-up re-entry of the token with lockout; 24-hour real-time TTL; freshness checks on snapshot, policy, beneficiary and plan; ADMIN cannot approve. |
| Idempotency and replay | Stable per-tenant key; status lookup before any resend; UNKNOWN keeps the reservation; the same key with a different payload is refused; observed movements are de-duplicated through the inbox table. |
| Auth and sessions | Random 256-bit tokens stored as hashes; HttpOnly SameSite=Strict cookie stored as a hash, revocable, membership re-checked on every request; CSRF header required for cookie writes; tenant always from membership. |
| Audit trail | Append-only (SQLite triggers, PostgreSQL revoked UPDATE/DELETE), hash-chained, verifiable, anchored on a public testnet. |
| Web client | DOM built from text nodes only, no `innerHTML`, no `eval`, no tokens in storage or URLs, strict CSP. |
| Dependencies | All 80 pinned packages (runtime, dev, on-chain) checked against OSV on 18 Oct 2026: no known vulnerabilities. |
| Secrets | No key, token or password in the current tree or in any past commit (a server IP address remains in history, see K13 below). |

## Gaps found and fixed

| # | Gap | Fix | Test |
|---|---|---|---|
| 1 | Any `Host` header was accepted, so a DNS-rebinding page could reach the local API | Host allowlist (loopback, plus `SME_ALLOWED_HOSTS`) before any route | `test_dns_rebinding_host_is_refused_and_headers_are_set` |
| 2 | Missing hardening headers (`X-Frame-Options`, COOP, CORP, `Permissions-Policy`, `object-src`, `form-action`, HSTS on HTTPS) | Added in the response middleware | same test |
| 3 | Bearer tokens on `/v1/*` could be guessed without limit (only `/session` was limited) | Separate 20-per-5-minutes budget, 429 when exceeded | `test_bearer_token_guessing_is_rate_limited_and_logged` |
| 4 | Failed sign-ins, bad tokens, foreign origins were not logged anywhere | `sme.security` JSON log lines without secrets | `test_failed_sign_in_and_foreign_origin_are_logged_without_secrets` |
| 5 | `NaN`/`Infinity` accepted in request JSON; deep nesting produced a 500 | Strict parser, both return 400 | `test_non_finite_and_deeply_nested_json_are_shape_errors` |
| 6 | Uploaded XLSX parts were parsed with DTDs allowed | DTD/entity declarations and non-UTF-8 encodings refused | `test_dtd_entity_and_foreign_encodings_are_refused` |
| 7 | A replayed signed webhook re-ran reconciliation | Duplicate event ID returns before any work | `test_replayed_signed_webhook_does_not_reconcile_again` |
| 8 | Proposals made by the model were indistinguishable from the user's own actions in the audit | `agent.tool_call` audit record per T2 tool call | `test_model_proposals_are_in_the_hash_chained_audit` |
| 9 | CI had a default-permission token, tag-pinned actions and no secret or vulnerability check | `contents: read`, SHA-pinned actions, `scripts.security_scan` step | `test_tracked_files_contain_no_secrets_or_public_hosts` |

## Accepted risk

- **Server address in git history (K13).** Current files are clean, but three older
  commits still contain the model server's public IP (no key or password). The owner
  decided not to rewrite history because hosting moves to another server, which retires
  the address. `python -m scripts.security_scan --history` lists the affected commits.

## Verification after the fixes (Windows, CPython 3.11.9, 18 Oct 2026)

These are the counters recorded on 18 Oct; the latest full run is in the
[README](../../README.md) and [EXECUTION_EVIDENCE.md](EXECUTION_EVIDENCE.md).

- Full regression: 300 tests, 0 failures, 4 skipped (PostgreSQL not configured in
  this shell). Raw report: `artifacts/regression-security-20261018.json`.
- `scripts.check`: all PASSED. `scripts.security_scan`: secrets PASSED, dependencies PASSED.
- Product E2E `scripts.e2e_v03`: 23/23 checks passed.
- T094 (browser evidence) stays NOT_RUN: the recorded browser run predates UI changes
  already on `main`; this audit did not touch `web/`.

## Re-run

```bash
python -m scripts.security_scan            # secrets + OSV dependency audit
python -m scripts.security_scan --history  # also every past commit
python -m unittest tests.test_security_hardening
```
