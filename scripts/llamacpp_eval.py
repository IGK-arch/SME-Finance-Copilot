"""Run the frozen 74+26 EN/ZH suite through native llama.cpp, with no semantic analysis."""

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
from scripts.agent_edge_eval import evaluate_case as edge_eval
from scripts.agent_edge_scenarios import CASES as EDGES
from scripts.agent_eval import evaluate_case as document_eval
from scripts.agent_language_profile import localize
from scripts.agent_report import safety_checks
from scripts.agent_scenarios import CASES as DOCUMENTS
from scripts.live_compare import EXPLORATORY_CASES, PLATFORM_CASES, evaluate_case as platform_eval
from scripts.reasoning_eval import source_hashes
from scripts.strata_eval import check_resources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cases", nargs="*")
    args = parser.parse_args()
    output = Path(args.output)
    directory = Path(".runtime/multimodel-eval") / output.stem
    if output.exists() or directory.exists():
        parser.error("New report/workspace required; previous attempts are immutable")
    frozen = json.loads(
        Path("artifacts/strata-reasoning-100-comparison-20261017.json").read_text(encoding="utf-8")
    )["cases"]
    cases = localize(DOCUMENTS + PLATFORM_CASES + EXPLORATORY_CASES) + EDGES
    require(
        canonical({c["id"]: c for c in cases}) == canonical({c["id"]: c for c in frozen}),
        "EVAL_CASE_CHANGED",
        "Original 100 definitions must be unchanged",
    )
    if args.cases:
        if set(args.cases) - {c["id"] for c in cases}:
            parser.error("Unknown case")
        cases = [c for c in cases if c["id"] in args.cases]
    connection = json.loads(Path(args.connection).read_text(encoding="utf-8"))
    os.environ["SME_MODEL_SECRET"] = connection["bridge_token"]
    config = GatewayConfig(
        provider="llamacpp",
        model=args.model,
        enabled=True,
        base_url=f"http://127.0.0.1:{connection['local_port']}",
        context_tokens=16384,
        output_tokens=2048,
        timeout_seconds=120,
        max_elapsed_seconds=240,
        max_steps=12,
        max_tokens=128000,
        think=False,
    )
    gateway = ChatGateway(config)
    report: Json = {
        "schema_version": 1,
        "status": "RUNNING",
        "started_at": now(),
        "suite": "frozen-100-en-zh",
        "configuration": config.public(),
        "cases": cases,
        "runs": [],
        "source_hashes": source_hashes(),
        "system_hash": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "tools_hash": hashlib.sha256(canonical(tool_schemas()).encode()).hexdigest(),
        "analysis_status": "DEFERRED_BY_USER",
        "reasoning_effort": "none",
        "limitations": [
            "Quantized GGUF, not BF16 quality",
            "Fixed existing budgets; no retry substitution",
            "AUDITOR case is rejected before inference",
            "Different runtime from original Strata baseline",
            "No retained reasoning history; temperature zero",
        ],
    }

    def save() -> None:
        report["summary"] = {
            "completed": len(report["runs"]),
            "planned": len(cases),
            "counts": dict(Counter(r["grade"]["status"] for r in report["runs"])),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)

    save()
    try:
        identity = gateway.describe()
        report["model_identity"] = identity
        save()
        for case in cases:
            require(
                source_hashes() == report["source_hashes"],
                "EVAL_SOURCE_CHANGED",
                "Source freeze changed",
            )
            require(
                gateway.describe()["digest"] == identity["digest"],
                "MODEL_CHANGED",
                "Model instance changed",
            )
            resources = check_resources(gateway._request("/v1/status"))
            evaluator = (
                edge_eval
                if case["id"] in {c["id"] for c in EDGES}
                else document_eval
                if case["id"] in {c["id"] for c in DOCUMENTS}
                else platform_eval
            )
            run = evaluator(config, case, directory / case["id"])
            run.update(reasoning_effort="none", server_before_case=resources)
            report["runs"].append(run)
            save()
            print(
                f"{len(report['runs'])}/{len(cases)} {case['id']} {run['grade']['status']}",
                flush=True,
            )
            safety = safety_checks(run)
            require(
                all(safety.values()),
                "EVAL_SAFETY_FAILED",
                "Stop queue for a failed safety assertion",
            )
        report["status"] = "COMPLETED"
    except BaseException as exc:
        report.update(status="FAILED", stopped_reason=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        report["finished_at"] = now()
        save()


if __name__ == "__main__":
    main()
