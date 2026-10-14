"""Fresh source/database/venv rehearsal with pinned local wheels; no inference."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from finance.domain import now


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    commands = []
    with tempfile.TemporaryDirectory(prefix="sme_fresh_rehearsal_") as temporary:
        root = Path(temporary).resolve()
        require_parent = root.parent
        if not root.is_relative_to(require_parent) or root == require_parent:
            raise RuntimeError("Unexpected rehearsal path")
        source = root / "source"
        source.mkdir()
        for folder in ("finance", "sandbox", "scripts", "web", "contracts", "fixtures"):
            shutil.copytree(
                project / folder,
                source / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        environment = root / "venv"
        command = [sys.executable, "-m", "venv", str(environment)]
        result = subprocess.run(command, capture_output=True, text=True)
        commands.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr,
            }
        )
        if result.returncode:
            raise RuntimeError("Fresh venv creation failed: " + result.stderr)
        candidates = [
            environment / relative
            for relative in ("Scripts/python.exe", "bin/python.exe", "bin/python")
        ]
        executable = next((path for path in candidates if path.is_file()), None)
        if executable is None:
            raise RuntimeError("Fresh venv interpreter is unavailable in known runtime layouts")
        command = [
            str(executable),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(project / ".runtime/wheelhouse"),
            "-r",
            str(project / "requirements.lock"),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        commands.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr,
            }
        )
        if result.returncode:
            raise RuntimeError("Pinned wheel install failed: " + result.stderr)
        command = [
            str(executable),
            "-c",
            "import json,platform,importlib.metadata; print(json.dumps({'python':platform.python_version(),'installed_packages':[d.metadata['Name'] for d in importlib.metadata.distributions()]}))",
        ]
        result = subprocess.run(command, cwd=source, capture_output=True, text=True)
        commands.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr,
            }
        )
        command = [
            str(executable),
            "-m",
            "scripts.demo",
            "--lost-response",
            "--output",
            str(root / "evidence"),
        ]
        result = subprocess.run(command, cwd=source, capture_output=True, text=True)
        commands.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr,
            }
        )
        evidence_path = root / "evidence/golden-latest.json"
        evidence = (
            json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence_path.exists()
            else None
        )
        report = {
            "at": now(),
            "status": "PASSED"
            if evidence
            and evidence["independent_evaluation"]["success"]
            and all(c["exit_code"] == 0 for c in commands)
            else "FAILED",
            "commands": commands,
            "independent_evaluation": evidence["independent_evaluation"] if evidence else None,
            "scope": "Copied fresh source, fresh venv installed from pinned offline wheels, fresh independent databases; CP-SAT golden + lost response",
            "not_run": ["External CI", "Production deployment", "Git release tag"],
        }
        destination = project / "artifacts/rehearsal.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "report": str(destination),
                    "status": report["status"],
                    "evaluation": report["independent_evaluation"],
                },
                indent=2,
            )
        )
        if report["status"] != "PASSED":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
