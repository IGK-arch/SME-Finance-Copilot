# Self-hosted LLM through Strata (optional)

The default application runs with the deterministic MOCK model. This runbook
describes the optional LIVE provider: a self-hosted Qwen model
(`qwen3.8-flash-next-iq3_xxs`) served by [Strata](https://github.com/mach10x/strata)
on a separate GPU server (RTX 3090 24 GB, 64 GB RAM). Only synthetic task prompts and
permitted tool results leave the application machine; financial tools always run
inside the Copilot graph.

## Connection

`scripts/strata_bridge.py` exposes an authenticated listener on the application
machine's loopback interface. It verifies the pinned SSH host key, connects with an
owner-provided credential file and forwards requests to the model server's loopback
API. Host, port, user and credential paths live in an ignored local file
(`.runtime/strata-client/bridge.secret.json`); they are never committed or printed.

The bridge accepts only `GET /health`, `/v1/models`, `/v1/status` and
`POST /v1/chat/completions`. It refuses browser `Origin` headers, redirects,
streaming, image/URL content and Strata MCP execution. A lost connection fails
closed; LIVE never falls back to MOCK.

```powershell
.venv\Scripts\python.exe -m scripts.strata_bridge --config .runtime/strata-client/bridge.secret.json --client-lib .runtime/strata-client/lib
```

## Use the provider in a synthetic cabinet

```powershell
$connection = Get-Content -Raw .runtime/strata-client/bridge.secret.json | ConvertFrom-Json
$env:MODEL_PROVIDER = 'strata'
$env:MODEL_NAME = 'qwen3.8-flash-next-iq3_xxs'
$env:MODEL_BASE_URL = 'http://127.0.0.1:18443'
$env:SME_MODEL_SECRET = $connection.bridge_token
$env:ALLOW_SERVER_MODEL_INFERENCE = 'true'
.venv\Scripts\python.exe -m scripts.serve --directory .runtime/strata-demo --port 8092
```

Create the workspace with `scripts.task seed-demo --directory .runtime/strata-demo`
if it does not exist. Sessions still use membership authentication, and every
financial action still needs an exact OWNER approval.

## Run the evaluation suites

```powershell
.venv\Scripts\python.exe -m scripts.strata_eval --connection .runtime/strata-client/bridge.secret.json --model qwen3.8-flash-next-iq3_xxs --suite challenge platform exploratory --language-profile en-zh --output artifacts/strata-new-run.json
```

Use a new output file for each run. Every case gets its own synthetic sandbox; no
approval or payment is dispatched. Before each case the harness requires fresh
server RAM telemetry, 5 GiB free server RAM and 2 GiB free workspace disk. Runs use
temperature 0, at most 12 model calls, 2048 output tokens and 240 model seconds per
task. Strict grades check tools and state; prose is reviewed separately.

## Identity and answer protocol

`finance/strata.py` maps native responses to typed graph tool calls, requires provider
token counts, rejects truncated output and excludes reasoning fields. It records the
loaded model ID, engine version, server start time and context size; this
fingerprint is **not a weight-file hash**. For the final answer the client sends
`tool_choice=none`, and the graph still rejects tool calls during finalisation.
Exact references bind numbers and IDs, not the meaning of free prose.

Measured results: [Qwen 120-case evaluation](../QWEN_MEDIUM_120_20261020_RU.md) and
[multi-model comparison](../MULTIMODEL_100_RESULTS_RU.md).
