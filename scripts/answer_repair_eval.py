"""Paired replay of saved failed final drafts; not a complete scenario evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from finance import answers
from finance.domain import canonical, now, require
from finance.gateway import ChatGateway, GatewayConfig
from finance.workflows import model_result
from scripts.live_compare import MeasuredGateway
from scripts.strata_eval import check_resources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--connection", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), "IMMUTABLE_RESULT", "Choose a new output path")
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    require(source["status"] == "COMPLETED", "INCOMPLETE_RUN", "Use a completed source run")
    connection = json.loads(Path(args.connection).read_text(encoding="utf-8"))
    os.environ["SME_MODEL_SECRET"] = connection["bridge_token"]
    config = GatewayConfig(
        provider="strata",
        enabled=True,
        model=source["configuration"]["model"],
        base_url=f"http://127.0.0.1:{int(connection['local_port'])}",
        context_tokens=16384,
        output_tokens=2048,
        timeout_seconds=120,
        max_steps=1,
        max_tokens=128000,
        max_elapsed_seconds=120,
    )
    control = ChatGateway(config)
    identity = control.describe()
    require(
        identity["digest"] == source["model_identity"]["digest"],
        "MODEL_CHANGED",
        "Paired replay requires the same service instance",
    )
    report = {
        "status": "RUNNING",
        "started_at": now(),
        "source": args.input,
        "source_hash": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
        "model_identity": identity,
        "configuration": config.public(),
        "answer_code_hash": hashlib.sha256(Path(answers.__file__).read_bytes()).hexdigest(),
        "runs": [],
        "scope": "One final-writing call per saved failed draft; no workflow/tool execution, no new fact, approval or payment. This is NOT a full scenario rerun.",
    }

    def save() -> None:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    try:
        for run in source["runs"]:
            state = (run.get("workflow") or {}).get("state", {})
            check = (state.get("summary") or {}).get("answer_validation") or {}
            if check.get("status") != "REJECTED":
                continue
            last = run["attempts"][-1].get("message", {})
            draft = last.get("content", "")
            if not draft or last.get("tool_calls"):
                continue
            check_resources(control._request("/v1/status"))
            require(
                control.describe()["digest"] == identity["digest"],
                "MODEL_CHANGED",
                "Instance changed",
            )
            refs = answers.references([model_result(o["output"]) for o in state.get("outputs", [])])
            draft_index = len(run["attempts"]) - 1
            # Pair against the draft before the original repair, when present;
            # do not quietly give a nearly-correct second draft a third chance.
            if len(run["attempts"]) >= 2:
                previous = run["attempts"][-2].get("message", {})
                previous_text = previous.get("content", "")
                if (
                    previous_text
                    and not previous.get("tool_calls")
                    and answers.render(previous_text, refs)["status"] == "REJECTED"
                ):
                    draft = previous_text
                    draft_index -= 1
            diagnostic = answers.render(draft, refs)
            messages = answers.context(
                state["messages"],
                refs,
                final=True,
                repair=diagnostic["errors"],
                unbound_literals=diagnostic.get("unbound_literals", []),
            )
            gateway = MeasuredGateway(config)
            response = gateway.chat(messages, [], {})
            checked = answers.render(response["message"].get("content", ""), refs)
            if response["message"].get("tool_calls"):
                checked = {"status": "REJECTED", "errors": ["Tools closed"]}
            report["runs"].append(
                {
                    "case_id": run["case_id"],
                    "original_attempt_index": draft_index,
                    "original_draft_hash": hashlib.sha256(draft.encode()).hexdigest(),
                    "repair_context_hash": hashlib.sha256(canonical(messages).encode()).hexdigest(),
                    "original_check": diagnostic,
                    "replay_check": checked,
                    "attempts": gateway.attempts,
                }
            )
            save()
            print(run["case_id"] + ": " + checked["status"], flush=True)
        report["status"] = "COMPLETED"
    except BaseException as exc:
        report["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED"
        report["stopped_reason"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        report["finished_at"] = now()
        save()


if __name__ == "__main__":
    main()
