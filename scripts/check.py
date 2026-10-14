"""Record actual independent lint/type/syntax/format commands and exit codes."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from finance.domain import Json, now


def main() -> None:
    checks = [
        (
            "python_syntax",
            [sys.executable, "-m", "compileall", "-q", "finance", "sandbox", "scripts", "tests"],
        ),
        *[
            ("javascript_syntax:" + path.as_posix(), ["node", "--check", path.as_posix()])
            for path in sorted(Path("web").rglob("*.js"))
        ],
        (
            "ruff",
            [
                "ruff",
                "check",
                "finance",
                "sandbox",
                "scripts",
                "tests",
                "--select",
                "E9,F63,F7,F82,F401,F841",
            ],
        ),
        ("mypy", ["mypy", "finance", "sandbox", "scripts", "--check-untyped-defs"]),
        ("format", ["ruff", "format", "--check", "finance", "sandbox", "scripts", "tests"]),
    ]
    records: list[Json] = []
    for name, command in checks:
        if command[0] in {"ruff", "mypy"}:
            command = [sys.executable, "-m"] + command
        if not shutil.which(command[0]):
            records.append(
                {
                    "name": name,
                    "command": command,
                    "status": "NOT_RUN",
                    "reason": "Tool not installed",
                }
            )
            continue
        run = subprocess.run(command, capture_output=True, text=True)
        records.append(
            {
                "name": name,
                "command": command,
                "status": "PASSED" if run.returncode == 0 else "FAILED",
                "exit_code": run.returncode,
                "output": run.stdout + run.stderr,
            }
        )
    path = Path("artifacts/quality-results.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": now(), "checks": records}, indent=2), encoding="utf-8")
    print(json.dumps({r["name"]: r["status"] for r in records}, indent=2))
    raise SystemExit(1 if any(r["status"] == "FAILED" for r in records) else 0)


if __name__ == "__main__":
    main()
