"""Run existing synthetic LangGraph scenarios on an owner's Strata via SSH bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path

from finance.domain import Json, canonical, now, require
from finance.gateway import ChatGateway, GatewayConfig
from finance.workflows import SYSTEM, tool_schemas
from scripts.live_compare import CASES, EXPLORATORY_CASES, PLATFORM_CASES, evaluate_case
from scripts.agent_scenarios import CASES as CHALLENGE_CASES
from scripts.agent_eval import evaluate_case as evaluate_challenge


def check_resources(status: Json) -> Json:
    machine = status.get("machine") or {}
    ram = machine.get("ram") or {}
    total, used, at = ram.get("total_gib"), ram.get("used_gib"), machine.get("at")
    require(
        all(type(v) in {int, float} for v in (total, used, at)),
        "MODEL_RESOURCE_GUARD",
        "Fresh server RAM telemetry is required",
    )
    assert (
        isinstance(total, (float, int))
        and isinstance(used, (float, int))
        and isinstance(at, (float, int))
    )
    # Integer server timestamps can lead the client clock slightly. Wait for
    # that timestamp rather than accepting future telemetry or widening its TTL.
    ahead = at - time.time()
    if 0 < ahead <= 2:
        time.sleep(ahead + 0.05)
    require(
        0 <= time.time() - at <= 60 and total >= used >= 0,
        "MODEL_RESOURCE_GUARD",
        "Fresh server RAM telemetry is required",
    )
    require(total - used >= 5, "MODEL_RESOURCE_GUARD", "Server free RAM below 5 GiB")
    require(
        shutil.disk_usage(Path.cwd()).free >= 2 * 1024**3,
        "MODEL_RESOURCE_GUARD",
        "Workspace disk reserve below 2 GiB",
    )
    return machine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", required=True, help="Ignored bridge secret configuration")
    parser.add_argument("--model", required=True, help="Exact /v1/models ID")
    parser.add_argument(
        "--suite",
        nargs="+",
        choices=["baseline", "platform", "exploratory", "challenge"],
        default=["platform", "exploratory"],
    )
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--language-profile", choices=["source", "en-zh"], default="source")
    parser.add_argument(
        "--reasoning-effort", choices=["none", "low", "medium", "high"], default="none"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.output)
    directory = Path(".runtime/strata-eval") / path.stem
    if path.exists() or directory.exists():
        parser.error("Choose a new output name; previous outcomes are immutable")
    connection = json.loads(Path(args.connection).read_text(encoding="utf-8"))
    os.environ["SME_MODEL_SECRET"] = connection["bridge_token"]
    config = GatewayConfig(
        provider="strata",
        model=args.model,
        base_url=f"http://127.0.0.1:{int(connection['local_port'])}",
        enabled=True,
        context_tokens=16384,
        output_tokens=2048,
        timeout_seconds=120,
        max_elapsed_seconds=240,
        max_steps=12,
        max_tokens=128000,
        think=args.reasoning_effort != "none",
        strata_reasoning_effort=args.reasoning_effort,
    )
    suites = {
        "baseline": CASES,
        "platform": PLATFORM_CASES,
        "exploratory": EXPLORATORY_CASES,
        "challenge": CHALLENGE_CASES,
    }
    candidates = {c["id"]: c for suite in args.suite for c in suites[suite]}
    if args.cases and set(args.cases) - candidates.keys():
        parser.error("Unknown case in selected suites")
    selected = [c for key, c in candidates.items() if not args.cases or key in args.cases]
    if args.language_profile == "en-zh":
        from scripts.agent_language_profile import localize

        selected = localize(selected)
    gateway = ChatGateway(config)
    identity = gateway.describe()
    before = check_resources(gateway._request("/v1/status"))
    report: Json = {
        "schema_version": 1,
        "language_profile": args.language_profile,
        "suite": "strata-langgraph-v1",
        "status": "RUNNING",
        "started_at": now(),
        "configuration": config.public(),
        "model_identity": identity,
        "system_hash": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "tools_hash": hashlib.sha256(canonical(tool_schemas()).encode()).hexdigest(),
        "source_hashes": {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
            for name in (
                "finance/gateway.py",
                "finance/answers.py",
                "finance/answer_quality.py",
                "finance/strata.py",
                "finance/workflows.py",
                "finance/agents.py",
                "finance/agent_data.py",
                "finance/store.py",
                "finance/workspace.py",
                "finance/compute.py",
                "finance/ingestion.py",
                "finance/execution.py",
                "finance/worker.py",
                "finance/digest_check.py",
                "finance/planner.py",
                "finance/validation.py",
                "scripts/live_compare.py",
                "scripts/strata_eval.py",
                "scripts/agent_language_profile.py",
                "scripts/strata_bridge.py",
                "scripts/agent_scenarios.py",
                "scripts/agent_eval.py",
            )
        },
        "server_at_start": before,
        "cases": selected,
        "runs": [],
        "limitations": [
            "Synthetic development cases; no company holdout or production-quality claim",
            "Tool/state checks are graded automatically; narrative requires separate review",
            "No model payment approval/dispatch or real business data; challenge operation fixtures use scripted synthetic OWNER approvals BEFORE agent observation",
            "Identity fingerprint is service metadata, not a cryptographic weight hash",
            "Resident warm model; different configuration/hardware from historical 14B runs",
            "RAM reserve checked between cases; no new OS memory limit installed",
        ],
    }

    def save() -> None:
        counts = Counter(r["grade"]["status"] for r in report["runs"])
        report["summary"] = {
            "completed": len(report["runs"]),
            "planned": len(selected),
            "strict_counts": dict(counts),
            "answer_reference_counts": dict(
                Counter(
                    r.get("answer_reference_check", {}).get("status", "NOT_RUN")
                    for r in report["runs"]
                )
            ),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    try:
        for case in selected:
            require(
                gateway.describe()["digest"] == identity["digest"],
                "MODEL_CHANGED",
                "Strata instance changed during evaluation",
            )
            machine = check_resources(gateway._request("/v1/status"))
            evaluator = (
                evaluate_challenge
                if case["id"] in {c["id"] for c in CHALLENGE_CASES}
                else evaluate_case
            )
            item = evaluator(config, case, directory / case["id"])
            item["answer_reference_check"] = (item.get("workflow") or {}).get("state", {}).get(
                "summary", {}
            ).get("answer_validation") or {
                "status": "NOT_RUN",
                "scope": "No completed answer-reference check; not evidence of success",
            }
            item["server_before_case"] = machine
            report["runs"].append(item)
            save()
            print(
                f"{case['id']}: {item['grade']['status']} ({item['elapsed_seconds']:.1f}s)",
                flush=True,
            )
        report["status"] = "COMPLETED"
    except BaseException as exc:
        report["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED"
        report["stopped_reason"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        report["finished_at"] = now()
        save()
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
