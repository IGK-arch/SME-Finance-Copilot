# CLAUDE.md — orientation map (read this first, then only what the task needs)

SME Finance Copilot, Topic E. Local synthetic SME cash workspace: import → facts → snapshot →
forecast → OR-Tools plan → independent validator → exact owner approval → worker → independent
sandbox → reconciliation. Version label 0.2.0 in pyproject; code is at the **v0.3 iteration**
(owner main-path cabinet). Status: PARTIAL, synthetic/sandbox only, MOCK model by default.
Answer the owner in Russian. Code, UI copy and docs are English unless a doc is `*_RU.md`.

## Do NOT read unless the task requires it (expensive)
- `MASTER_SPEC.md` (300 KB), `SME_Finance_Copilot_Master_Spec.docx`, `sources/R*` — original spec.
- `docs/TECHNICAL_REPORT_RU.md` (100 KB) — describes v0.2.0; this file supersedes it for orientation.
- `SME_Copilot_v0_3_Audit_UX_Package/` — already applied; IDs V03-01…25 live in `checklists/v03_acceptance.json`.
- `artifacts/*.json` raw runs, `.runtime/`, `.venv/`, `.mypy_cache/`, `__pycache__/`, `web/legacy/`.
- `docs/LOCAL_14B_*`, `docs/LIVE_MODEL_*`, `docs/AGENT_PLATFORM_RESULTS.md` — historical 14B evaluation.

## Where things are
| Area | File | Notes |
|---|---|---|
| Money/time/errors | `finance/domain.py` | int minor units, `minor()`, `utc()`, `digest()`, `FinanceError(code,msg)`, `require()` |
| Storage | `finance/store.py`, `finance/postgres.py` | same SQL dialect; `objects(tenant,kind,object_id,payload)` is append-only KV used for new features (no migrations) |
| Import (strict CSV) | `finance/ingestion.py` | `import_csv`, quarantine, `snapshot()` (writes snapshot object) |
| Import wizard | `finance/mapping.py` | CSV/XLSX → mapping → preview → commit via `import_csv`; ambiguous dates/decimals are errors |
| Calculations | `finance/compute.py` | `forecast`, `obligation_flows` (supports `obligation_shocks`, `customer_shocks`), `financing`, `candidate`, oracle `optimize` |
| Planner | `finance/planner.py` | CP-SAT `solve`; `OBJECTIVES` + `objective_scope()` shared with oracle (keep both in sync) |
| Validator | `finance/validation.py` | independent; never call compute/planner from it |
| Execution | `finance/execution.py` | `command/approve/prepare/deliver/refresh`; real-time approval TTL (`approval_ttl` objects) |
| Worker | `finance/worker.py` | `enqueue`, `work_once`; status lookup before any resend |
| Owner read models | `finance/cases.py` | home, case events (OPENED/PROBLEM_CHANGED/OPTIONS_COMPUTED/OPTION_SELECTED/CLOSED), options, review, timeline, activity, alerts, what-if, user context |
| Approve reviewed payload | `finance/digest_check.py` | browser sends only payload hash; server recompiles and compares |
| Copilot glue | `finance/copilot.py` | background runs, server-verified context, result cards from tool events |
| Agent graph/tools | `finance/workflows.py`, `finance/agents.py`, `finance/agent_data.py`, `finance/gateway.py` | `ChatGateway` providers: mock / disabled / ollama |
| HTTP | `finance/asgi.py` (FastAPI, `/session` cookie auth, `/assets/*`, `/legacy`), `finance/api.py` (`dispatch` + `v03_route`) | |
| UI | `web/index.html`, `ui.js` (h(), api(), chart, formatting), `pages.js` (pages + Dialog), `copilot.js`, `app.js` (router/session), `style.css` (tokens on `:root`) | |
| Sandbox | `sandbox/world.py`, `sandbox/server.py` | separate process + `private/world.db` |
| Runtime/harness | `scripts/runtime.py`, `scripts/serve.py`, `scripts/task.py` | |

API added in v0.3: `GET /v1/home`, `GET /v1/case`, `POST /v1/case/{options,select,what-if}`,
`GET /v1/review/{plan}/{action}`, `POST /v1/review/{plan}/{action}/approve`, `GET /v1/timeline/{action}`,
`GET /v1/plans/{id}/progress`, `GET /v1/activity`, `POST /v1/imports/{preview,commit}`,
`GET /v1/copilot/{run}`, `GET|POST /v1/context`, `POST /session`, `POST /session/logout`.

## Invariants (never break; tests guard them)
Integer minor units, no float money. Invoice/expected receipt ≠ cash. Facts versioned, observed vs
effective time. Validator independent of solver. One exact OWNER approval per action, bound to payload
hash; no approve-all; LLM never approves/sends. Reservations, stable idempotency key, UNKNOWN keeps
reserve, status lookup before resend. Tenant from membership only. No secrets/tokens in outputs, URLs,
localStorage. LIVE failure never falls back to MOCK. Case is RESOLVED only after plan COMPLETED + matched
reconciliation. Statuses honest: NOT_RUN / DEFERRED_MODEL never reported as PASSED.

## UI conventions
DOM via `UI.h()` text nodes only (no innerHTML with data). CSP `style-src 'self'`: no inline `style=""`
strings — use `style: {…}` objects (CSSOM) or classes. Amounts: display strings come from the server
(`money()` → `{minor, minor_str, display}`); client exact math only via `UI.minorText`/`UI.parseMajor` (BigInt).
Dates shown in Asia/Shanghai (`UI.day/time`), real timestamps via `UI.real` (en-GB). Pages filter null
children with `put()`. Theme: warm ivory/near-black; accent token `--accent`; no third-party logos/fonts.

## How to run things on this machine (important — saves time)
- Windows host, project `E:\projects\SME Finance Copilot\SME_Finance_Copilot_Codex_Handoff\sme_codex_handoff`.
  Linux VM (`device_bash`) sees it at `$HOME/mnt/sme_codex_handoff`; VM has python3.10/node but **no project
  deps and no PyPI**. The cloud container has no PyPI either. Windows `.venv` (Python 3.11.9) is the only runtime.
- Commands run through the owner-started allowlisted runner `scripts/devbridge.py` (owner runs
  `.\.venv\Scripts\python.exe -m scripts.devbridge`). Submit a JSON task into `.runtime/devbridge/queue/`,
  read `.runtime/devbridge/out/<id>.json|.log`. Kinds: `module` (`scripts.*`, `tests.*`, `unittest`),
  `serve` (workspaces `dev`=.runtime/v03-dev, `pg`=.runtime/pg-workspace, `e2e`; ports 8000–8999), `stop`.
  If no output appears within seconds, the runner is not running — ask the owner to start it.
- Helper (recreate in VM `$HOME/bridge.py` if missing): writes `queue/<id>.json`, waits, prints result + log tail.
- Dev cabinet: serve `dev` on 8090; login token in `.runtime/v03-dev/local-login.secret.json` (OWNER; test value,
  never echo it in chat). `pg-workspace` is the owner's data: read-only browsing only, never seed/reset.
- Writing big files: `device_bash` heredocs fail above ~40 KB (E2BIG). Write in the cloud under
  `/mnt/user-data/outputs/…` and copy with `device_commit_files`. Small edits: python read-modify-write in VM.
- From the Linux VM deleting files in the folder is disabled; move strays into `.runtime/devbridge/out/`.
  (A Claude session running directly on the Windows host can use PowerShell, git and `.venv` directly.)
- Browser checks: built-in browser pane at `http://127.0.0.1:8090`; screenshots fail while the pane is
  hidden — use `get_page_text`/JS measurements, ask the owner for Ctrl+Shift+B when images are needed.
  Hard-reload (`location.reload()`) after CSS/JS changes; restart the server after Python changes.

## Verify (pick the smallest relevant set)
- Targeted: `{"kind":"module","module":"unittest","args":["tests.test_v03"]}` (~15 s).
- Full regression incl. PostgreSQL (~150 s): `scripts.test --output artifacts/v03/regression-v03.json`.
- Lint/types/format: `scripts.fmt` (ruff fix+format) then `scripts.check` (must be all PASSED).
- Product path E2E (~20 s): `scripts.e2e_v03` → `artifacts/v03/e2e-latest.json`.
- Matrix: `scripts.report_v03` → `docs/ACCEPTANCE_MATRIX_V03.md` (reads artifacts only).
- Browser evidence `artifacts/v03/browser-v03.json` is valid only while `webHashes` match current `web/*`;
  after UI edits it becomes stale (T094 drops to NOT_RUN) until re-recorded.

## Current state (update this block when it changes)
- Git: repo initialised on the Windows host (`main`), remote `origin` = github.com/IGK-arch/SME-Finance-Copilot
  (private). `.gitattributes` is `* -text` (bytes stored as-is: hashed files/fixtures must not change EOL).
  Git commands run directly from PowerShell on the host; no devbridge needed.
- Last full run (14 Oct, after UX pass): 176 PASSED, 1 FAILED, 4 SKIPPED (PostgreSQL not configured in that
  shell). The failure is T100: `AGENTS.md` got an orientation header on 14 Oct, so its hash no longer matches
  `docs/HANDOFF_INVENTORY.json` (owner to decide: re-hash or revert). T094 PASSED with fresh browser evidence;
  e2e 21/21; check all PASSED.
- 14 Oct UX pass: boot splash, loading/error/not-found states with retry, phone/tablet bottom tab bar (≤860px),
  charts drawn at on-screen width (12px labels, collision-free dates), compact metrics ≤520px, custom file
  picker, owner-facing dates as "Thu 8 Oct" in server texts (`cases._day`), favicon. Verified on a throwaway
  workspace (`scripts.serve --directory <temp>` on 8091) because the dev token must not be read by Claude.
- Open: V03-07 server filters for agent reads, V03-21 unrelated-change
  tolerance, V03-22 isolation/backup, alerts ack/debounce, migrate `/legacy` tools (allocation, raw CSV),
  bump version to 0.3.0 + refresh TECHNICAL_REPORT_RU, usability study. LIVE items wait for the target model.
- Plans/decisions: `docs/V03_PLAN.md`, `docs/adr/0005-v03-owner-main-path.md`, `docs/KNOWN_LIMITATIONS.md`.
