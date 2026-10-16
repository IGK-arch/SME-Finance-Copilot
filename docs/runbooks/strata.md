# Strata on the owner server

The 14 Oct 2026 connection reuses an existing Windows Strata installation. No
model weights were downloaded by this integration. The engine stays on the
server; only synthetic task prompts and permitted tool results cross SSH.

## Verified installation

- Windows 10 Pro, Xeon E5-2666 v3, 64 GB RAM, RTX 3090 24 GB, driver 591.74.
- Installation: `C:\Strata-main`; weights: `C:\Strata-data\models\IQ3_XXS`.
- Engine 0.1.43.1; `/v1/models` ID `qwen3.8-flash-next-iq3_xxs`.
- Loaded engine context: 131072 tokens; vision installed, but this connection accepts text only.
- Remote API listens on `127.0.0.1:8080`. No firewall/public API changes were made.

The requested project is [mach10x/strata](https://github.com/mach10x/strata).
Its [installation guide](https://github.com/mach10x/strata/blob/main/docs/INSTALL.md)
describes a much larger download than a typical 14B model. Check free disk and
resident resources before any future model installation; do not reinstall over
the running server just to reconnect Copilot.

## Connection and credentials

On 15 Oct the owner supplied a new public SSH endpoint: `user@195.208.16.1:45161`.
Port 40769 is obsolete. The existing pinned server key also verified the new port;
no accept-any-host-key policy was used. The local bridge port remains 18443.

`scripts/strata_bridge.py` exposes only an authenticated loopback listener on this
machine, port 18443. It verifies the SSH host key, connects with the owner-provided
credential file and opens SSH direct-tcpip channels to remote loopback port 8080.
The owner-provided `SSH_key.txt` is excluded from Git. Never print its contents.

The bridge accepts only GET `/health`, `/v1/models`, `/v1/status`, and POST
`/v1/chat/completions`. It refuses browser Origin headers, redirects, streaming,
image/URL content and Strata MCP execution. Financial tools run in the Copilot
graph. A lost SSH connection fails closed; it does not fall back to MOCK.

Private connection settings are in `.runtime/strata-client/bridge.secret.json`:
`ssh_host`, `ssh_port`, `ssh_user`, `credential_file`, `known_hosts`, `local_port`,
`bridge_token`. Paths are local; the bridge token is random and at least 32
characters. The remote instance currently uses no API key and is accessible only
on its loopback interface; the local bridge requires its own token.

Paramiko 4.0.0 was installed separately in `.runtime/strata-client/lib`, leaving
the application virtual environment unchanged. On a fresh setup:

```powershell
.venv\Scripts\python.exe -m pip install --target .runtime/strata-client/lib --no-cache-dir paramiko==4.0.0
.venv\Scripts\python.exe -m scripts.strata_bridge --config .runtime/strata-client/bridge.secret.json --client-lib .runtime/strata-client/lib
```

Keep one bridge instance per port. A background Windows launch must use
`Start-Process -WindowStyle Hidden`; record its PID and verify its command line
before stopping it. Stopping the bridge does not stop the remote model.

## Run the scenario suites

```powershell
.venv\Scripts\python.exe -m scripts.strata_eval --connection .runtime/strata-client/bridge.secret.json --model qwen3.8-flash-next-iq3_xxs --suite platform exploratory --output artifacts/strata-new-run.json
```

Use a new output filename for each run. `--cases` selects existing case IDs.
The runner reuses the existing scenario definitions and `evaluate_case()` grader;
it creates a separate synthetic financial sandbox per case under
`.runtime/strata-eval/<report-name>`. No approval or payment dispatch is performed.
It records requests through hashes, visible answers, tool calls, usage, failures,
source hashes and the current server's reported resources.

The guard requires fresh RAM telemetry, at least 5 GiB free server RAM and 2 GiB
free on the workspace disk before each case. This is a between-case check, not an
OS allocation limit or GPU reservation. It does not close unrelated programs.
For a server timestamp up to two seconds ahead, the runner waits until that time
and then applies the same zero-to-sixty-second age check. Larger clock leads or
still-future data fail closed; RAM and disk thresholds are unchanged.

These runs use a resident model, temperature 0, reasoning off, max output 2048,
12 calls, 120 seconds per request and 240 model seconds per task. The configured
context requirement is 16384; the server's loaded context remains 131072.
Automatic strict grades measure tool/state conditions; review financial amounts,
dates, citations, language and completion separately. Hardware and settings differ
from the historical 14B runs, so the scores are not a controlled model comparison.
The first measured run is documented in [STRATA_RESULTS_RU.md](../STRATA_RESULTS_RU.md).

## Use the provider in a synthetic cabinet

The default application mode stays MOCK. To opt in within one shell:

```powershell
$connection = Get-Content -Raw .runtime/strata-client/bridge.secret.json | ConvertFrom-Json
$env:MODEL_PROVIDER = 'strata'
$env:MODEL_NAME = 'qwen3.8-flash-next-iq3_xxs'
$env:MODEL_BASE_URL = 'http://127.0.0.1:18443'
$env:SME_MODEL_SECRET = $connection.bridge_token
$env:ALLOW_SERVER_MODEL_INFERENCE = 'true'
$env:MODEL_TIMEOUT_SECONDS = '120'
$env:MODEL_MAX_ELAPSED_SECONDS = '240'
$env:MODEL_CONTEXT_TOKENS = '16384'
$env:MODEL_OUTPUT_TOKENS = '2048'
.venv\Scripts\python.exe -m scripts.serve --directory .runtime/strata-demo --port 8092
```

Create `strata-demo` with `scripts.task seed-demo --directory .runtime/strata-demo`
only if it does not exist. The owner's `pg-workspace` is not a test workspace.
Do not echo `$connection` or environment secrets. The session still uses normal
membership authentication and each financial action still needs exact OWNER approval.
The cabinet created on 14 Oct was resumed with the 15 Oct fixes at
`http://127.0.0.1:8092` after the final scenario run, without seed/reset.
Health/home/root/auth checks are in `artifacts/strata-cabinet-final-20261015.json`.
Verify the listener and its command line each session; do not start a duplicate.
Its login token is in
`.runtime/strata-demo/local-login.secret.json` (OWNER). HTTP health and home reads
passed; this is not a new browser walkthrough. The cabinet keeps the existing
64000-token task budget, while the evaluation uses an explicit 128000-token budget.

## Identity and limitations

`finance/strata.py` translates the native response into typed graph tool calls,
preserving call IDs across results. It requires provider token counts, rejects
truncated outputs and excludes reasoning fields. It checks loaded model ID,
engine version, server start time and context. The saved digest fingerprints
those service-instance fields; it is **not a weight-file hash**. Weight SHA256
and local-file license verification remain unmeasured. A server restart requires
a fresh workflow even if it reloads the same named model.

`scripts.doctor --live` and `scripts.live_compare` remain the Ollama-specific
launchers; use `scripts.strata_eval` for this server. OCR, image evaluation,
concurrent capacity, target-model completion gates and production deployment are
outside this connection test.

## Final-answer protocol (15 Oct)

For final text, the client sends `tool_choice=none`; agent calls use `auto`.
The bridge rejects other choices. Leading system rules close tools; observed
results are included as untrusted data without native prior-call tags, since the
installed Strata converter demotes late system messages. The graph still rejects
tool calls during finalization: a provider flag is not an authorization boundary.
Exact references bind numbers/IDs, not arbitrary prose meaning. See
[final scenario report](../STRATA_FINAL_SCENARIOS_20261015_RU.md) for the measured
results and remaining semantic errors. Do not overwrite historical raw reports.


## Expanded tool/document checks (15 Oct)

The new development suite contains 54 cases; it complements the unchanged
20 platform/exploratory cases. Run on synthetic data only, after verifying the
existing bridge and model identity. Preserve every output with a fresh name:

```powershell
.venv\Scripts\python.exe -m scripts.strata_eval --connection .runtime/strata-client/bridge.secret.json --model qwen3.8-flash-next-iq3_xxs --suite challenge platform exploratory --language-profile en-zh --output artifacts/strata-expanded-NEW.json
```

Use `--cases <id> <id>` for a declared subset. The harness checks fresh server
RAM telemetry, a 5 GiB free RAM reserve and 2 GiB free workspace disk before each
case, and records exact tool traces, source hashes, model identity and failures.
Keep 12 calls / 128000 task tokens / 16384 context / 2048 output / 240 seconds
per task; raising limits changes the comparison. No paid services or new weights.

`python -m scripts.agent_report --before <baseline.json> --after <complete.json>
--output <comparison.json> --markdown <report.md> --review <review.json>
--answers <answers.md>` derives coverage and side-by-side grades from artifacts.
Full prose needs separate review even when strict checks pass. A replay using
`scripts.answer_repair_eval` only tests a saved final draft, not the workflow.
See `../AGENT_CHALLENGE_DESIGN_RU.md`, `../STRATA_CHALLENGE_RESULTS_RU.md` and
`../STRATA_CHALLENGE_FIXES_RU.md` for the corpus and honest proof boundaries.

## Owner language constraint (15 Oct)

For subsequent LIVE tests, use --language-profile en-zh: 54 English and 20
Chinese prompts, including clarification replies. The original corpus remains
multilingual; quoted company names and evidence are data, not Russian test
prompts. Case IDs retain their historical suffixes. Translation leaves all
fixtures, oracle values and grading requirements intact, but comparison with an
earlier source-language run is not a controlled same-prompt comparison.

The v5 runtime adds bounded read-completion checks and typed operation status
context. These are not general semantic or Chinese-intent guarantees. A failed
answer remains failed; do not replace missing prose or relax exact approvals.
