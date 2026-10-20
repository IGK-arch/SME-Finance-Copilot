# Free local inference on E:

User authorized free local models, then requested at least 4B parameters after the
storage incident. Initial models: Qwen2.5 7B and Granite 3.3 8B, Q4_K_M and Apache
2.0. On October 13 the user requested a larger model: Qwen2.5 14B Instruct Q3_K_S
(catalog: 14.8B parameters, 6.7 GB, Apache 2.0). Preserve exact installed metadata,
digest and license in evaluation reports; a catalog claim is not a completed test.
Only synthetic inputs are authorized. No cloud inference, paid APIs or real payments.

## Storage and resource limits

The launcher requires this repository on E:. Binaries, weights and child TEMP/TMP
are under `.runtime/ollama`; CUDA JIT cache is also redirected there, capped at
128 MiB. No Windows service or global environment is installed.
The verified installer archive is deleted after extraction. Ollama's existing small
per-user identity files remain in C:\Users\admin\.ollama. Windows owns its system
pagefile on C: at the earlier checkpoint. After an external OS reboot on October 13,
inspection found E:\pagefile.sys at 9728 MiB. This task did not change those settings;
moving model files alone does not move the pagefile.

`scripts.resource_guard` uses a Windows job with a 2 GiB aggregate CPU committed-memory
limit, 8-process ceiling and kill-on-close. A Python child waits for assignment before
launching Ollama. A named singleton and occupied-port check prevent a second guarded
server. Breakaway is disabled. There is no fallback to an unguarded process or new port.

Before startup: at least 6 GiB free system disk, 10 GiB free physical RAM and 8 GiB
commit headroom. While running, checks every 0.5 seconds stop the job below 4 GiB
free system disk, 20 GiB
free E:, 5 GiB free RAM or 3 GiB commit headroom; a runtime footprint above 20 GiB also
stops it. The E: footprint cap was raised from 14 to 20 GiB for the explicitly
requested third model; memory, C: and free-E: reserves were not reduced. Pull
preflight reserves another 5 GiB for 7B/8B or 7 GiB for the 14B tag. These checks are polling guards,
not filesystem quotas; concurrent applications can consume space between checks.
The job bounds CPU commitment, not GPU VRAM or unrelated processes. Windows peak
counters may include denied allocations; the allocation rejection is tested directly.
If limits fail, preserve the diagnostic and investigate; do not silently increase them.

The original 12 GiB system-disk reserve was revised to 4 GiB after the user confirmed
their separate Claude download and requested continued work on E:. No Claude files
were changed. Free disk space, free physical RAM and commit headroom are independent:
more space on E: alone does not satisfy a failed Windows memory preflight.

After a Granite GPU load failed under the former 6 GiB job, C: briefly fell to
0.77 GiB free and recovered to about 6.3 GiB after shutdown. Pagefile allocation
remained 8704 MiB; the precise temporary allocation on C: was not identified.
That attempt is preserved in artifacts/live-granite8-gpu-failed.json.
The current profile disables CUDA/HIP discovery and Vulkan, requests num_gpu=0,
use_mmap=true and batch 128. LLAMA_ARG_REPACK=0 disables an extra ~3.6 GiB CPU copy
of Granite weights. Weights are mapped from E:; mapped physical RAM is not the same
as committed private memory. The 2 GiB job does not cap total physical RAM use.
CPU smoke passed in artifacts/live-granite8-cpu-smoke-v3.json (batch 32 for that
probe); comparisons use batch 128 identically for both models.
Atomic status replacement retries brief Windows sharing failures for at most one
second, then fails closed. A stale RUNNING file never overrides its heartbeat age.

Guard evidence is `.runtime/ollama/guard-status.json`, logs `server.log`. The server
loads at most one model, one request in parallel, context 8192, flash attention and
q8_0 KV cache. Inference requests keep the current model loaded for 60 seconds;
comparison explicitly unloads before and after each model. No automatic downloads.
Use `scripts.local_llm stop MODEL` to unload immediately; Ctrl+C in the guarded
server terminal stops its whole process tree. Downloaded files stay on E: for reuse.

## Provision and run

```powershell
.venv\Scripts\python.exe -m scripts.local_llm status
.venv\Scripts\python.exe -m scripts.local_llm install
.venv\Scripts\python.exe -m scripts.local_llm serve
# In another terminal, sequentially:
.venv\Scripts\python.exe -m scripts.local_llm pull qwen2.5:7b
.venv\Scripts\python.exe -m scripts.local_llm pull granite3.3:8b
.venv\Scripts\python.exe -m scripts.local_llm pull qwen2.5:14b-instruct-q3_K_S
.venv\Scripts\python.exe -m scripts.local_llm list
.venv\Scripts\python.exe -m scripts.local_llm ps
```

Pinned portable runtime v0.40.3, 1,468,053,171 bytes, SHA256
`e5ecff02dfc7cae8ddf6d6b7a7ac5f727ffeedf4491f44ae75ff5b0820dbbbd5`.
The installer validates size/digest and bounded archive paths before extraction.
This verifies the official release digest, not a vendor code-signature claim.

For the existing PostgreSQL workspace, preserve its history:

```powershell
.venv\Scripts\python.exe -m scripts.postgres start
$env:MODEL_TIMEOUT_SECONDS='240'
$env:MODEL_MAX_ELAPSED_SECONDS='600'
.venv\Scripts\python.exe -m scripts.serve --port 8080 --directory .runtime/pg-workspace --model qwen2.5:7b
```

`--model` requires a fresh running guard and installed local weights with tool support.
The application defaults to explicitly labelled MOCK without live opt-in. Start a new
workflow for a different model; existing checkpoints pin provider/model/digest.
Use the workspace's existing membership credentials; do not reset or reseed it.

## Measured comparison

```powershell
$env:MODEL_PROVIDER='ollama'
$env:ALLOW_LOCAL_MODEL_INFERENCE='true'
$env:MODEL_NAME='qwen2.5:7b'
$env:MODEL_TIMEOUT_SECONDS='240'
$env:MODEL_MAX_ELAPSED_SECONDS='600'
.venv\Scripts\python.exe -m scripts.live_compare --models qwen2.5:7b granite3.3:8b --repeats 1 --output artifacts/live-comparison-NEW.json
```

Choose a new output name. Isolated synthetic workspaces are saved under
`.runtime/live-eval`. Reports contain exact model identity/license, visible answers,
actual tools, latency, returned token counts, errors and guard snapshots. Unmeasured
failed requests remain unmeasured. No paid API cost is invented. The benchmark does
not approve or execute payments and verifies unchanged policy/world and zero actions.
Structural pass does not grade arbitrary financial prose; review narratives separately.
A small synthetic suite is not a company holdout or a production safety certificate.

For expanded platform access use `--suite platform` with the same environment:
`scripts.live_compare --suite platform --models qwen2.5:7b --output artifacts/live-platform-NEW.json`.
Ten synthetic cases exercise details, versions, review rows, saved action preparation,
what-if, document continuation, operation controls, extension proposals and role ACL.
`--cases` selects diagnostic cases; keep those separate from a complete suite and
preserve failed/resource-stopped runs. Do not run a second model or heavy regression
concurrently. A pending extension is not a confirmed changed due date.

Gateway environment defaults remain 60 seconds/request and 240 cumulative seconds;
the CPU commands above explicitly use 240/600 seconds, 8192 context and 1024 output
tokens. `think=false` is requested; providers may not honor it. Tagged
reasoning is filtered from visible reports; empty or truncated output fails explicitly.
The graph deadline is cumulative time plus 30 seconds, lease plus 90. No mock fallback.

## Primary references

- https://docs.ollama.com/windows
- https://docs.ollama.com/faq
- https://docs.ollama.com/api/chat
- https://github.com/ollama/ollama/releases/tag/v0.40.3
- https://ollama.com/library/qwen2.5:7b
- https://ollama.com/library/granite3.3:8b
- https://ollama.com/library/qwen2.5:14b-instruct-q3_K_S
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
- https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html
- https://github.com/ollama/ollama/blob/main/api/types.go
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

The expanded platform probe exceeded the former 120-second request deadline.
Current CPU examples opt into 240 seconds/request (maximum) while the total model
budget stays 600 seconds/task. Historical October 12 comparisons used 120/600; do
not directly interpret new elapsed times as a model speed comparison. Memory,
system-disk and process limits and lack of paid/remote inference remain unchanged.
The separately documented E: runtime footprint increase only permits storing the
third model. A request to test with current memory does not disable the guard.

For ten additional categories use `--suite exploratory` with the installed 14B tag.
See scenario inventory for all twenty tasks and grading
limits. Run sequentially and preserve each failed attempt. Never turn an automatic
tool/state pass into a claim that all natural-language assertions are correct.

## Optional smaller KV cache for constrained 14B testing

Two expanded Q8-cache runs reached the unchanged free-RAM floor. The user chose
continuation with current memory and protection. The launcher now disables the
bundled llama-server's additional idle prompt cache (LLAMA_ARG_CACHE_RAM=0). Its
installed --help confirms this setting. Default KV precision remains q8_0; opt in
to q4_0 only in the guarded server shell:

```powershell
$env:SME_OLLAMA_KV_CACHE_TYPE='q4_0'
.venv\Scripts\python.exe -m scripts.local_llm serve
```

Only q8_0/q4_0 are allowed. Context remains 8192, CPU only, one request/model and
all RAM/commit/disk/job limits stay unchanged. On actual 14B load the runtime log
reported KV buffer 432 MiB (previous Q8: 816 MiB), disabled prompt cache and 8192
context; see artifacts/qwen14-kv4-runtime.json. Q4 KV can change response precision;
keep these reports separate from Q8-cache results. Do not infer equal answer quality
from lower memory. Official description: https://docs.ollama.com/faq
