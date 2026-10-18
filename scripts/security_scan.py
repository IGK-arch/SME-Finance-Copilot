"""Repository security scan: committed secrets, public host addresses, vulnerable pins.

    python -m scripts.security_scan                 # tracked files + OSV dependency audit
    python -m scripts.security_scan --offline       # skip the network audit (NOT_RUN)
    python -m scripts.security_scan --history       # also scan every commit's added lines

Findings print the file, line and rule, never the matched value. Exit code 1 when a
check FAILED. A NOT_RUN audit (no network) is reported as such, never as PASSED.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import urllib.request
from pathlib import Path

from finance.domain import Json, now

RULES: dict[str, re.Pattern[str]] = {
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "api_secret_key": re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{24,}\b"),
    "hex_private_key": re.compile(r"(?i)private[_ ]?key[\"']?\s*[:=]\s*[\"']?(0x)?[0-9a-f]{64}\b"),
    "bearer_literal": re.compile(
        r"(?i)authorization[\"']?\s*[:=]\s*[\"']bearer [A-Za-z0-9._~+/-]{20,}"
    ),
}
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".docx", ".pdf", ".xlsx", ".zip", ".db"}
OSV_URL = "https://api.osv.dev/v1/querybatch"
LOCK_FILES = ("requirements.lock", "requirements-dev.lock", "requirements-onchain.txt")


def public_ipv4(text: str) -> list[str]:
    """Globally routable IPv4 literals. Version strings like 0.1.43.1 are not global."""
    found = []
    for match in IPV4.finditer(text):
        try:
            address = ipaddress.IPv4Address(match.group(1))
        except ValueError:
            continue
        if address.is_global:
            found.append(str(address))
    return found


def scan_text(text: str, allowed_ips: set[str]) -> list[Json]:
    findings: list[Json] = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule, pattern in RULES.items():
            if pattern.search(line):
                findings.append({"line": number, "rule": rule})
        for address in public_ipv4(line):
            if address not in allowed_ips:
                findings.append({"line": number, "rule": "public_ipv4"})
    return findings


def tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [Path(p) for p in output.split("\0") if p]


def scan_files(files: list[Path], allowed_ips: set[str]) -> list[Json]:
    findings = []
    for path in files:
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        if path.stat().st_size > 5_000_000:
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        findings += [{"file": path.as_posix()} | f for f in scan_text(text, allowed_ips)]
    return findings


def scan_history(allowed_ips: set[str]) -> list[Json]:
    """Added lines of every commit on every ref; reports commit and file, not the value."""
    log = subprocess.run(
        ["git", "log", "--all", "-p", "--no-textconv", "--no-color", "--format=commit %h"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="replace")
    findings: list[Json] = []
    commit = path = ""
    seen: set[tuple[str, str, str]] = set()
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line[7:]
        elif line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for f in scan_text(line[1:], allowed_ips):
                key = (commit, path, f["rule"])
                if key not in seen:
                    seen.add(key)
                    findings.append({"commit": commit, "file": path, "rule": f["rule"]})
    return findings


def pins(paths: tuple[str, ...]) -> list[tuple[str, str]]:
    result = set()
    for name in paths:
        path = Path(name)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", line.strip())
            if match:
                result.add((match.group(1), match.group(2)))
    return sorted(result)


def osv_audit(packages: list[tuple[str, str]], timeout: float = 60) -> Json:
    body = {
        "queries": [
            {"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in packages
        ]
    }
    request = urllib.request.Request(
        OSV_URL, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            results = json.load(response)["results"]
    except (OSError, ValueError, KeyError) as exc:
        return {"status": "NOT_RUN", "reason": f"OSV unreachable: {type(exc).__name__}"}
    vulnerable = [
        {"package": n, "version": v, "ids": [x["id"] for x in r.get("vulns") or []]}
        for (n, v), r in zip(packages, results)
        if r.get("vulns")
    ]
    return {
        "status": "FAILED" if vulnerable else "PASSED",
        "checked": len(packages),
        "vulnerable": vulnerable,
        "source": "osv.dev",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--output", default="artifacts/security-scan.json")
    args = parser.parse_args()
    allowed = set(json.loads(Path("checklists/security_scan_allow.json").read_text())["ipv4"])
    secrets = scan_files(tracked_files(), allowed)
    report: Json = {
        "at": now(),
        "secrets": {"status": "FAILED" if secrets else "PASSED", "findings": secrets},
        "dependencies": {"status": "NOT_RUN", "reason": "--offline"}
        if args.offline
        else osv_audit(pins(LOCK_FILES)),
    }
    if args.history:
        history = scan_history(allowed)
        report["history"] = {"status": "FAILED" if history else "PASSED", "findings": history}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in report.items() if isinstance(v, dict)}, indent=2))
    for section in ("secrets", "dependencies", "history"):
        for item in (report.get(section) or {}).get("findings", []) or (
            report.get(section) or {}
        ).get("vulnerable", []):
            print(section, json.dumps(item))
    return 1 if any(isinstance(v, dict) and v["status"] == "FAILED" for v in report.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
