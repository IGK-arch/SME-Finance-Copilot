# Local model gateway and graph

Agent-tools-v2 extends the native registry with scoped paginated records, complete
detail/calculation reads, plan action IDs, selected proposals, what-if and pending
supplier extensions. See ../AGENT_CAPABILITIES.md. The October 12 comparisons below
are historical measurements of the preceding tool set, not a re-evaluation of v2.

`finance/gateway.py` implements the official Ollama native chat contract:
[chat](https://docs.ollama.com/api/chat) and installed model discovery `/api/tags`.
An exact installed model name is required; no model ID, weights or license is
invented. Real Qwen3 4B inference ran during an earlier experiment (4/10 structural
cases with a local template variant); its weights were removed after a resource
incident. Qwen2.5 7B and Granite 3.3 8B are now installed on E: at the user's request.
See LIVE_MODEL_PLAN.md and CONTINUATION.md for current resource/startup state.

October 13 update: Qwen2.5 14B Instruct Q3_K_S is installed on E: and its real
connectivity smoke passed. Twenty distinct synthetic platform/exploratory tasks
were attempted (21 attempts; one repeated resource interruption), with 240 seconds
per request and 600 cumulative seconds/task. Strict results:8 PASSED/13 FAILED
attempts. Assistant narrative review:6 complete,5 partial,7 failed,2 RAM-interrupted
scenarios. Q8/Q4 cache profiles are distinct and not a controlled comparison.
[Completed results](../LOCAL_14B_RESULTS.md) preserve all raw reports and limitations.
Current evidence and unchanged financial-state checks are in
[platform results](../AGENT_PLATFORM_RESULTS.md); cases and grading limits are in
[scenario inventory](../LOCAL_14B_SCENARIOS.md). The UI currently selects this
experimental 14B model; historical 7B/8B scores below do not establish 14B quality.

Default `MODEL_PROVIDER=mock` runs an explicitly labelled deterministic tool-call
fixture in the actual LangGraph engine. It does not understand arbitrary language.
`MODEL_PROVIDER=disabled` fails closed. There is no fallback from failed live calls.
The offline HTTP contract test uses a tiny local test server, not an Ollama model.

To opt into a separately provisioned local endpoint, set MODEL_PROVIDER=ollama,
MODEL_NAME to its exact installed name, MODEL_BASE_URL to http://127.0.0.1:PORT,
and ALLOW_LOCAL_MODEL_INFERENCE=true. Optional authentication is read from the env
variable named by `secret_env` (default SME_MODEL_SECRET), never the frontend.
Non-loopback URLs, redirects and proxies are refused. No paid provider is enabled.

Typed tools return financial calculations and source IDs; only READ/COMPUTE/PROPOSE
are available. Documents are untrusted text. No SQL, shell, secrets, payment or
policy-edit tool exists. Real exact approvals are a separate server authority.
Steps, context size, token bounds, per-call time and cumulative model time are
enforced. Paid API allowance is exactly zero. Usage is provider-reported for live
responses; billed cost is null for this local endpoint, not a fabricated monetary
metric. Graph invocation is bounded by the configured cumulative model budget plus
30 seconds and at most 80 transitions; its lease is the model budget plus 90 seconds.

LangGraph persists interrupts, tool events, approved payloads and observation state.
Clarification/resume is tested offline. A changed snapshot needs a refreshed exact
command and a new approval. Partial execution remains in the operational ledger.
Model narrative is labelled as narrative, not numeric evidence or settlement proof.

Historical `artifacts/live-smoke.json` is only a completed connectivity probe of a
now-removed Qwen3 model. It does not establish task quality or current availability.
The earlier custom-template task run is `artifacts/live-qwen4-template-v3.json`.
Current guarded comparison results are linked in LIVE_MODEL_RESULTS.md;
selection is based on actual runs, not metadata or model size. Novel tasks use actual LangGraph
and safe tools, not hand-written answers. Free-text narrative semantics are not
fully machine-graded. Small synthetic tasks do not prove production suitability.

Guarded Qwen2.5 7B baseline: 4/10 structural passes, median 3.868 seconds;
`artifacts/live-qwen7-guarded-v1.json`. Tool descriptions and server-enforced snapshot
prerequisites were then improved. Three diagnostic cases passed structurally in
`artifacts/live-qwen7-prerequisite-probe-v3.json`, but assistant review found a
Chinese answer to a Russian question and an incorrect claim about reserve inclusion.
See the companion `-review.json`. Those are real narrative failures despite structural
passes. These diagnostic results are historical, superseded by the completed
CPU comparison: Qwen 8/10 strict passes, median 64.063 s; corrected Granite 8/10,
median 90.693 s. Both still have narrative errors. Qwen is selected only for the
experimental sandbox UI. See [results](../LIVE_MODEL_RESULTS.md) and raw reports
live-comparison-cpu-final-v1.json / live-granite8-native-protocol-v2.json.
Granite's initial 1/10 was traced to native tool instructions omitted by its
official template when a custom system message exists. The provider-specific
adapter restores that format without changing app rules or parsing prose as tools.
Qwen results were reused; a regression test confirms its messages are unchanged.
The GPU attempt failed loading; current inference is CPU only with 2 GiB job,
mmap, batch 128 and no extra weight repacking. Comparison and the LIVE UI explicitly
use 120 seconds/request and 600 cumulative seconds/task; environment defaults remain
60/240. Narrative reviews are by the Codex assistant, not an independent human.
An additional baseline review is live-qwen7-baseline-review.json: its approval-boundary
case preserved server safety but produced a misleading willingness-to-pay narrative.
Structural safety is separate from an appropriate refusal in natural language.

Resource management: `scripts/local_llm.py` requires E: storage and one bounded
Windows job; see [runbook](../runbooks/local-llm.md). API startup and comparison
require a live resource guard. The runtime never changes system pagefile settings.
CPU memory constraints do not supply OS security isolation of simulator files.
