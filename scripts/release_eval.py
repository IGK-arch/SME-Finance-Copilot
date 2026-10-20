"""Frozen 100-case regression plus twenty new cases, one sequential LIVE queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

from finance.domain import Json, canonical, now, require
from finance.gateway import ChatGateway
from finance.workflows import SYSTEM, tool_schemas
from scripts.agent_edge_eval import evaluate_case as edge_eval
from scripts.agent_edge_scenarios import CASES as EDGES
from scripts.agent_eval import evaluate_case as challenge_eval
from scripts.agent_language_profile import localize
from scripts.agent_report import safety_checks
from scripts.agent_scenarios import CASES as CHALLENGES
from scripts.business_health_eval import language_matches
from scripts.health_challenge_eval import evaluate_case as health_eval
from scripts.live_compare import EXPLORATORY_CASES, PLATFORM_CASES, evaluate_case as platform_eval
from scripts.reasoning_eval import configurations, source_hashes
from scripts.release_challenge_scenarios import CASES as NEW
from scripts.strata_eval import check_resources


def suite() -> list[Json]:
    old = localize(CHALLENGES + PLATFORM_CASES + EXPLORATORY_CASES)
    return (
        [
            {
                "group": "regression100",
                "evaluator": "challenge"
                if c["id"] in {v["id"] for v in CHALLENGES}
                else "platform",
                "case": c,
            }
            for c in old
        ]
        + [{"group": "regression100", "evaluator": "edge", "case": c} for c in EDGES]
        + [{"group": "new20", "evaluator": c["evaluator"], "case": c} for c in NEW]
    )


def frozen_sources() -> dict[str, str]:
    values = source_hashes()
    for path in sorted(Path("contracts").glob("*.json")):
        values[path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def save(path: Path, value: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection", default=".runtime/strata-client/bridge.secret.json")
    parser.add_argument("--model", default="qwen3.8-flash-next-iq3_xxs")
    parser.add_argument("--reasoning", choices=["none", "medium"], required=True)
    parser.add_argument("--preregistration", required=True)
    parser.add_argument("--output")
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    registration = Path(args.preregistration)
    entries = suite()
    require(
        len(entries) == 120 and len({e["case"]["id"] for e in entries}) == 120,
        "EVAL_CASES",
        "Expected 120 unique cases",
    )
    connection = json.loads(Path(args.connection).read_text(encoding="utf-8"))
    os.environ["SME_MODEL_SECRET"] = connection["bridge_token"]
    config = configurations(args.model, int(connection["local_port"]), [args.reasoning])[
        args.reasoning
    ]
    manifest: Json = {
        "schema_version": 1,
        "registered_at": now(),
        "entries": entries,
        "source_hashes": frozen_sources(),
        "configuration": config.public(),
        "system_hash": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "tools_hash": hashlib.sha256(canonical(tool_schemas()).encode()).hexdigest(),
        "policy": "Primary failures retained; no fallback, guard bypass or production edits during run",
        "new_set_scope": "Author-created novel combinations, not independent external holdout",
    }
    if args.prepare:
        require(not registration.exists(), "EVAL_EXISTS", "Preregistration already exists")
        save(registration, manifest)
        print("PREREGISTERED 100 regression + 20 new EN/ZH; no model requests")
        return
    original = json.loads(registration.read_text(encoding="utf-8"))
    for key in ("entries", "source_hashes", "configuration", "system_hash", "tools_hash"):
        require(
            canonical(manifest[key]) == canonical(original[key]),
            "EVAL_SOURCE_CHANGED",
            f"Freeze mismatch: {key}",
        )
    if not args.output:
        parser.error("--output required")
    path = Path(args.output)
    directory = Path(".runtime/strata-eval") / path.stem
    require(not path.exists() and not directory.exists(), "EVAL_EXISTS", "Use new output/workspace")
    if args.cases:
        require(
            len(set(args.cases)) == len(args.cases)
            and set(args.cases) <= {e["case"]["id"] for e in entries},
            "EVAL_CASES",
            "Unknown/duplicate case selection",
        )
        entries = [e for e in entries if e["case"]["id"] in args.cases]
    gateway = ChatGateway(config)
    report: Json = {
        "schema_version": 1,
        "suite": "qwen-release-120-v1",
        "status": "RUNNING",
        "started_at": now(),
        "preregistration": registration.as_posix(),
        "preregistration_sha256": hashlib.sha256(registration.read_bytes()).hexdigest(),
        "configuration": config.public(),
        "source_hashes": original["source_hashes"],
        "cases": [e["case"] for e in entries],
        "runs": [],
    }

    def checkpoint() -> None:
        report["updated_at"] = now()
        report["summary"] = {
            "completed": len(report["runs"]),
            "planned": len(entries),
            "strict_counts": dict(Counter(r["grade"]["status"] for r in report["runs"])),
        }
        save(path, report)

    checkpoint()
    try:
        identity = gateway.describe()
        report["model_identity"] = identity
        report["server_at_start"] = check_resources(gateway._request("/v1/status"))
        checkpoint()
        if args.preflight:
            report["status"] = "PREFLIGHT_READY"
            return
        evaluators = {
            "edge": edge_eval,
            "health": health_eval,
            "challenge": challenge_eval,
            "platform": platform_eval,
        }
        for entry in entries:
            case = entry["case"]
            require(
                frozen_sources() == original["source_hashes"],
                "EVAL_SOURCE_CHANGED",
                "Frozen sources changed",
            )
            require(
                gateway.describe()["digest"] == identity["digest"],
                "MODEL_CHANGED",
                "Service identity changed",
            )
            resources = check_resources(gateway._request("/v1/status"))
            report["current_case"] = case["id"]
            checkpoint()
            run = evaluators[entry["evaluator"]](config, case, directory / case["id"])
            run.update(
                group=entry["group"],
                language=case.get("language", "unknown"),
                reasoning_effort=config.strata_reasoning_effort,
                server_before_case=resources,
            )
            if entry["group"] == "new20":
                state = (run.get("workflow") or {}).get("state", {})
                run["grade"]["checks"]["requested_language"] = language_matches(
                    state.get("summary", {}).get("model_text", ""),
                    case["language"],
                    state.get("outputs", []),
                )
                run["grade"]["status"] = (
                    "PASSED"
                    if all(run["grade"]["checks"].values()) and all(run["grade"]["safety"].values())
                    else "FAILED"
                )
            report["runs"].append(run)
            checkpoint()
            print(
                f"{len(report['runs'])}/{len(entries)} {case['id']} {run['grade']['status']} {run['elapsed_seconds']:.1f}s",
                flush=True,
            )
            require(
                bool(safety_checks(run)) and all(safety_checks(run).values()),
                "EVAL_SAFETY_FAILED",
                "Safety assertion failed; evaluation stopped",
            )
        report["status"] = "COMPLETED"
        report.pop("current_case", None)
        report["server_at_end"] = check_resources(gateway._request("/v1/status"))
    except BaseException as exc:
        report["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED"
        report["stopped_reason"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        report["finished_at"] = now()
        checkpoint()
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
