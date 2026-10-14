from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from finance.domain import Config, uid
from scripts.runtime import Runtime, run_golden


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lost-response", action="store_true")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    Config.from_environment()
    with tempfile.TemporaryDirectory(prefix="sme_demo_") as temporary:
        with Runtime(Path(temporary)) as runtime:
            result = run_golden(runtime, args.lost_response)
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    filename = destination / (uid("golden") + ".json")
    filename.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "golden-latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "evidence": str(filename.resolve()),
                "evaluation": result["independent_evaluation"],
                "reconciliation": result["reconciliation"],
                "plan_status": result["plan_status"],
            },
            indent=2,
        )
    )
    if not result["independent_evaluation"]["success"] or not result["reconciliation"]["matched"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
