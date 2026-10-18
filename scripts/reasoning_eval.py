"""Fixed-budget Strata comparison. Fresh workspaces, immutable runs, no retry substitution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from finance.domain import Json, canonical, now, require
from finance.gateway import ChatGateway, GatewayConfig
from finance.workflows import SYSTEM, tool_schemas
from scripts.agent_edge_scenarios import CASES as EDGES
from scripts.agent_edge_eval import evaluate_case as evaluate_edge
from scripts.agent_eval import evaluate_case as evaluate_challenge
from scripts.agent_language_profile import localize
from scripts.agent_scenarios import CASES as CHALLENGES
from scripts.live_compare import PLATFORM_CASES, EXPLORATORY_CASES, evaluate_case
from scripts.strata_eval import check_resources


def configurations(model: str, port: int, efforts: list[str]) -> dict[str, GatewayConfig]:
    return {
        effort: GatewayConfig(
            provider="strata",
            model=model,
            base_url=f"http://127.0.0.1:{port}",
            enabled=True,
            context_tokens=16384,
            output_tokens=2048,
            timeout_seconds=120,
            max_elapsed_seconds=240,
            max_steps=12,
            max_tokens=128000,
            think=effort != "none",
            strata_reasoning_effort=effort,
        )
        for effort in efforts
    }


def source_hashes() -> dict[str, str]:
    paths = sorted(
        {p for root in ("finance", "sandbox", "scripts") for p in Path(root).glob("*.py")}
    )
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--suite", choices=["legacy", "edge"], required=True)
    parser.add_argument(
        "--efforts", nargs="+", choices=["none", "low", "medium", "high"], required=True
    )
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.output)
    directory = Path(".runtime/strata-eval") / path.stem
    if path.exists() or directory.exists():
        parser.error("Use a new report/workspace name; previous attempts are immutable")
    if len(set(args.efforts)) != len(args.efforts):
        parser.error("Duplicate effort")
    cases = (
        EDGES if args.suite == "edge" else localize(CHALLENGES + PLATFORM_CASES + EXPLORATORY_CASES)
    )
    if args.cases and set(args.cases) - {c["id"] for c in cases}:
        parser.error("Unknown case")
    cases = [c for c in cases if not args.cases or c["id"] in args.cases]
    cfg = json.loads(Path(args.connection).read_text(encoding="utf-8"))
    os.environ["SME_MODEL_SECRET"] = cfg["bridge_token"]
    configs = configurations(args.model, int(cfg["local_port"]), args.efforts)
    gateway = ChatGateway(next(iter(configs.values())))
    report: Json = {
        "schema_version": 1,
        "suite": "reasoning-" + args.suite,
        "language_profile": "en-zh",
        "status": "RUNNING",
        "started_at": now(),
        "configurations": {e: c.public() for e, c in configs.items()},
        "source_hashes": source_hashes(),
        "cases": cases,
        "runs": [],
        "system_hash": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "tools_hash": hashlib.sha256(canonical(tool_schemas()).encode()).hexdigest(),
        "ordering": "Case order fixed; effort order reversed on odd case indices",
        "limitations": [
            "Synthetic development cases, not held-out production acceptance",
            "Same definitions and budgets; independent fresh fixtures have random record IDs",
            "Warm sequential server; no concurrent capacity or cold-start measurement",
            "Reasoning text is not persisted or replayed; per-call reasoning comparison",
            "Strict tool/state grade is not complete prose semantics; separate review required",
            "Resource guard remains 5 GiB free server RAM and 2 GiB free local disk",
            "Service identity metadata is not a weight-file hash",
        ],
    }

    def save() -> None:
        report["summary"] = {
            "completed": len(report["runs"]),
            "planned": len(cases) * len(configs),
            "by_effort": {
                e: dict(
                    Counter(
                        r["grade"]["status"] for r in report["runs"] if r["reasoning_effort"] == e
                    )
                )
                for e in configs
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    try:
        identity = gateway.describe()
        report["model_identity"] = identity
        report["server_at_start"] = check_resources(gateway._request("/v1/status"))
        save()
        for index, c in enumerate(cases):
            efforts = args.efforts if index % 2 == 0 else list(reversed(args.efforts))
            for effort in efforts:
                require(
                    source_hashes() == report["source_hashes"],
                    "EVAL_SOURCE_CHANGED",
                    "Sources changed; start a new explicit segment",
                )
                require(
                    gateway.describe()["digest"] == identity["digest"],
                    "MODEL_CHANGED",
                    "Strata instance changed; start a new segment",
                )
                resources = check_resources(gateway._request("/v1/status"))
                evaluator = (
                    evaluate_edge
                    if args.suite == "edge"
                    else evaluate_challenge
                    if c["id"] in {v["id"] for v in CHALLENGES}
                    else evaluate_case
                )
                run = evaluator(configs[effort], c, directory / effort / c["id"])
                run["reasoning_effort"] = effort
                run["server_before_case"] = resources
                run["answer_reference_check"] = (run.get("workflow") or {}).get("state", {}).get(
                    "summary", {}
                ).get("answer_validation") or {"status": "NOT_RUN"}
                report["runs"].append(run)
                save()
                print(
                    f"{effort} {c['id']}: {run['grade']['status']} ({run['elapsed_seconds']:.1f}s)",
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
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
