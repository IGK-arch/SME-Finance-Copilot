# Local live-model comparison — 2026-10-12

Historical plan/result. The expanded October 13 platform suite and requested 14B
experiment are tracked in AGENT_PLATFORM_RESULTS.md and CONTINUATION.md. The E:
runtime footprint cap is now 20 GiB for the third model; the other resource
thresholds below are unchanged. This file preserves the earlier experiment's scope.

October 12 outcome: comparison completed, Qwen2.5 7B selected for experimental UI;
both models achieved 8/10 strict structural passes. Full regression: 151 PASSED.
See [LIVE_MODEL_RESULTS.md](LIVE_MODEL_RESULTS.md) for evidence, narrative failures
and the limits of this iterative evaluation. The following plan records the scope.

**Resumed by the user after the authorized reboot.** C: free space recovered to
16.75 GiB. The user requested models of at least 4B parameters and storage on E:.
Selected Qwen2.5 7B and Granite 3.3 8B; no smaller models will be downloaded.
See CONTINUATION.md for the previous partial experiment and resource incident.
No pagefile settings are changed. New launcher safeguards must pass before inference.

User authorized free local models on synthetic data. No cloud inference, paid API,
real financial action or real customer data is authorized. Existing workspaces and
their approvals/history must be preserved.

## P0 — runnable local integration

- Download pinned official portable Ollama into ignored `.runtime/ollama`, verify
  the published archive digest; bind loopback and disable cloud features.
- Compare installed Qwen2.5 7B and Granite 3.3 8B. Record exact manifests,
  quantization, runtime version and returned licenses rather than infer licenses.
- Extend the gateway with explicit local generation settings, measured usage,
  bounded time, invalid/truncated-response rejection and model identity on resume.
- Keep READ/COMPUTE/PROPOSE tools and independent approval/execution checks.
- Use one CPU-only Windows job with a 2 GiB aggregate committed-memory limit and
  kill-on-close; a named singleton prevents a second guarded server. Store weights,
  binaries and child TEMP/TMP on E:. Remove the verified installation archive.
- Refuse startup below 6 GiB free system disk / 10 GiB free RAM / 8 GiB commit
  headroom. Poll every 0.5 seconds and stop below 4 GiB free system disk, 20 GiB free workspace disk,
  5 GiB free RAM, 3 GiB commit headroom, or above 14 GiB runtime footprint.
  Disk polling is not a hard quota; GPU allocations and other apps are not bounded
  by the CPU job commit limit. Do not silently relax a failed resource limit.

Both models are now downloaded and their manifest/blob sizes verified. The user
confirmed the separate Claude VM download was intentional and requested continued
work on E:. The system-disk floor was explicitly revised from 12 to 4 GiB for that
decision. After the Granite GPU-load failure, CPU-only mmap with weight repacking
disabled replaces that profile; the job limit is now lower (2 GiB), and startup
reserves 6 GiB on C:. Runtime RAM/commit thresholds remain unchanged. See the runbook
for the preserved failed attempts, recovered disk space and successful CPU smoke.

## P1 — measured comparison and usable product

- Run the same Russian/English synthetic tasks through the real LangGraph for
  each model: cash, forecast, financing, objectives, clarification, evidence and
  hostile document instructions. Grade actual tool results and durable state.
- Preserve per-case inputs, visible responses, calls, measured latency/tokens and
  failures. Do not use another unmeasured LLM as the judge. Narrative correctness
  and broad generalization are explicitly limited where not objectively graded.
- Compare measured outcomes; configure a suitable local default and verify the
  existing UI against live inference. Never silently resume a mock workflow with
  a different provider/model.
- Run gateway/workflow/evaluation tests, full regression and quality checks;
  update model card, runbook, status and traceability with actual evidence.

## P2 — separate follow-up

Broader multi-company holdouts, repeated statistical evaluation, larger hardware,
training and OS/process isolation remain separate work. A small local task suite
does not prove production safety or overall P0/P1 completeness.

Hardware actually inspected: RTX 4060 Laptop GPU, 8,188 MiB VRAM; 33,492,422,656
bytes RAM. About 37 GB free on workspace drive before installation. Sequential
inference is intentional to avoid concurrent model memory pressure.

Requirements: I01/I08/I18/I24/I28/I30–I36 as applicable; existing T060–T068 and
workflow/approval/recovery regressions retain their precise original scope.
New live cases are separate evidence, not fabricated replacements for T001–T100.
