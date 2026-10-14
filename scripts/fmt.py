"""Developer helper: apply ruff format and the project's safe autofixes (no other effects)."""

from __future__ import annotations

import subprocess
import sys

TARGETS = ["finance", "sandbox", "scripts", "tests"]


def main() -> None:
    fix = subprocess.run(
        [sys.executable, "-m", "ruff", "check", *TARGETS, "--select", "F401", "--fix"]
    )
    fmt = subprocess.run([sys.executable, "-m", "ruff", "format", *TARGETS])
    raise SystemExit(fix.returncode or fmt.returncode)


if __name__ == "__main__":
    main()
