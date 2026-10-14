"""Validate recorded CUA evidence; this command does not launch a browser."""

import hashlib
import json
from pathlib import Path


def load() -> list[dict]:
    path = Path("artifacts/browser-smoke.json")
    if not path.exists():
        return []
    report = json.loads(path.read_text(encoding="utf-8"))
    names = {"app.js", "style.css", "index.html"}
    valid = set(report.get("webHashes", {})) == names and bool(report.get("screenshots"))
    valid = valid and all(
        hashlib.sha256((Path("web") / name).read_bytes()).hexdigest() == report["webHashes"][name]
        for name in names
    )
    valid = valid and all(
        (Path("artifacts") / name).is_file() for name in report.get("screenshots", [])
    )
    valid = (
        valid and bool(report.get("checks")) and all(v is True for v in report["checks"].values())
    )
    return [report] if valid else []


def main() -> None:
    evidence = load()
    print(
        json.dumps(
            {
                "mode": "VERIFY_RECORDED_CUA_EVIDENCE_NOT_A_NEW_BROWSER_RUN",
                "status": "PASSED" if evidence else "NOT_RUN_OR_STALE",
                "artifacts": [e["test_id"] for e in evidence],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if evidence else 1)


if __name__ == "__main__":
    main()
