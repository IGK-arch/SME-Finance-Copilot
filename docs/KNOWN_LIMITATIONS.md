# Known limitations

The product is a working prototype on synthetic data. These are its current
boundaries; security risks with severities and mitigations are in the
[known-risk list](submission/SECURITY_SELF_ASSESSMENT.md#5-known-risk-list).

## Data and integrations

- Company records, financing products and the bank are synthetic. There is no real
  bank, lender, payment rail, ERP or notification connector.
- A real bank adapter would need its own authenticated settlement-identity contract,
  compliance review and failure tests.
- Financing terms are DEMO products; eligibility checks are not lender approval.
- Import supports CSV/XLSX and text PDF; there is no OCR, and document search is lexical.

## Calculations

- Forecast delay scenarios are uncalibrated and are not probabilities of default.
- Plan optimisation is exact over a finite candidate grid, not a claim of real-world optimality.
- Business analysis is descriptive; profit and loss is not computed from bank data.

## Model

- The default model is a deterministic MOCK. An optional self-hosted LLM was
  measured on synthetic scenarios; its prose can still contain semantic errors
  even when tool calls and on-screen numbers are correct.
- The served model is identified by service metadata, not by a weight-file hash.

## Operations

- No secret vault, SSO or per-user accounts; roles are bearer membership tokens.
- The sandbox's private files are separated by process, not by OS-level isolation.
- No compensating payments or external cancellation; a payment in UNKNOWN state
  keeps its reserve until the bank status is observed.
- Alerts have no acknowledgement or debounce workflow.
- On-chain anchoring uses a public testnet only.
- PostgreSQL integration tests run only when a test database is configured.
