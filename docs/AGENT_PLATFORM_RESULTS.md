# Expanded agent platform verification — 2026-10-13

Contract agent-tools-v2. Current work is synthetic and local, with independent
sandbox execution. Implementation coverage: [AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md).

## Deterministic checks

`scripts.test --output artifacts/regression-agent-data-v3.json` with the existing
PostgreSQL test configuration: **163 PASSED**, 144.756 seconds. Original acceptance:
**96 PASSED / 4 NOT_RUN**. `scripts.check`: all five checks PASSED. These are actual
offline/integration checks, not measurements of model quality. Source handoff hashes
and existing workspace history are preserved.

Coverage includes 29 scoped data collections, history/detail pagination, source ACL,
revoked membership/role changes, real plan/action IDs, exact selected-action approval
and single-action independent settlement, read-only quality diagnosis, saved compute
results, hypothetical scenarios and conditional extension requests. The four original
open targets are T023/T031/T032 research and T097 OS isolation.

## LIVE evidence and revision boundaries

- `live-platform-probe-v1.json`: resource stop; preserved guard evidence in
  `live-platform-resource-stop.json`.
- `live-platform-probe-v2.json`: two failures, wrong detail arguments and saved-plan
  timeout. Visible-record prerequisites and bounded CPU timeout were subsequently added.
- `live-platform-qwen-v3.json`: five completed failed cases, then interrupted after
  code corrections. The explicit interruption is in
  `live-platform-qwen-v3-interruption.json`; raw RUNNING is stale. This run used the
  older quality gate and plan projection. It is not a measurement of the final revision.
- `live-platform-qwen7-v4.json`: interrupted after eight completed cases when the
  guard detected only 268,492,800 free bytes on C:. A later external OS reboot ended
  the sessions. Original score 2/8; corrected whole-evidence grading yields 3/8 in
  the separate `live-platform-qwen7-v4-regrade.json`. Extension has no finalized
  case result; private-document was NOT_RUN. Raw stale RUNNING is superseded by
  `live-platform-qwen7-v4-interruption.json`; all raw failures remain preserved.
- Qwen2.5 14B Instruct Q3_K_S downloaded on E: following the user's request;
  pull completed with exit code 0 after digest verification. Local metadata in
  `qwen14-installed.json`: 14.8B, Q3_K_S, 6,659,609,509 bytes, tools capability,
  returned Apache 2.0 license. Digest:
  `c8f457c1f8f593fb2e47d9ea5e5951454f2837420b5abe0b075c650f59e2ada8`.
  Connectivity smoke PASSED (12.628 s). Expanded suite completed:20 distinct
  cases /21 attempts,8 strict passes. Assistant review:6 complete,5 partial,
  7 failed,2 RAM-interrupted scenarios (3 interruptions including retry).
  Q8/Q4 KV-cache profiles and all seven raw reports remain separate. Full results:
  [LOCAL_14B_RESULTS.md](LOCAL_14B_RESULTS.md), including successful computations
  followed by final-answer timeouts, missed tools and rejected invented IDs.
  Official tag:
  <https://ollama.com/library/qwen2.5:14b-instruct-q3_K_S>. Installed identity/license
  and actual guard outcome are kept separate from a model recommendation.

The platform suite checks details, invoice semantics, rejected import rows, fact
versions, saved-action preparation, partial/delayed receipts, document continuation,
operation controls, pending extensions and restricted documents. Each run records
tool results, source hashes, actual provider usage, errors and unchanged financial
state. It never grants payment approval. Natural-language review remains separate
from automatic tool/state checks. This is development evaluation, not a held-out
benchmark or independent human assessment.

## Resource and environment scope

CPU only, mapped E: weights, one loaded model/request, 8192 context, 1024 output,
240 seconds/request and 600 cumulative model seconds/task. No cloud or billed API.
The larger model uses Q3_K_S while 7B uses Q4_K_M, so size is not the only variable.
The E: runtime footprint cap increased from 14 to 20 GiB solely to store the third
model. Startup/runtime memory and disk-free reserves and the 2 GiB process-tree
private-commit cap are unchanged. It does not cap all mapped physical memory.
The 7B run overlaps the model download; latency is not a controlled speed benchmark.
This task did not alter Windows pagefile settings or unrelated files. After the
external reboot, Windows reports a 9728 MiB pagefile on E:. Fresh startup reserves
were ~18.5 GiB RAM/~25.5 GiB commit; desktop workload during inference is uncontrolled.

API and existing PostgreSQL workspace were restored without reseeding; the user
manually refreshed the browser, then existing OWNER login succeeded. Experimental
LIVE UI displays 14B. Supplementary browser query completed:317.297 s,2 model calls,
4775 reported tokens. Correct cash/date, but snapshot_id mislabelled as source_id:
PARTIAL. Evidence:browser-qwen14-expanded.json, workflow JSON and screenshot.

Latest harness checks:11 evaluator tests PASSED (0.021 s); preceding combined
evaluator/resource run:16 PASSED (0.988 s), including6 unchanged resource checks.
All five scripts.check checks passed; quality-qwen14-final.json. These supplement
the earlier163-test financial regression and do not redate it.
Q4 cache is opt-in; actual KV432MiB vs816MiB, context8192 unchanged. Three reserve
stops remain failures; limits were not lowered. See local-llm runbook.
