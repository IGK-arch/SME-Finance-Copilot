"""Make a clean copy of the repository for submission, without infrastructure details."""


from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Public-looking addresses only: not loopback, not version strings like "0.1.43.1".
IPV4 = re.compile(r"(?<![\d.])(?!127\.)(?!0\.)(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
SSH_PORT = re.compile(r'("ssh_port"\s*:\s*)\d+')
SSH_HOST_PORT = re.compile(r"(<gpu-host>):\d{2,5}")
TEXT = {".md", ".json", ".txt", ".py", ".js", ".yaml", ".yml", ".toml", ".csv", ".html"}


def scrub(text: str) -> tuple[str, int]:
    text, a = IPV4.subn("<gpu-host>", text)
    text, b = SSH_PORT.subn(r"\g<1>0", text)
    text, c = SSH_HOST_PORT.subn(r"\g<1>:<ssh-port>", text)
    return text, a + b + c


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    out = Path(parser.parse_args().out).resolve()
    if out.exists():
        print(f"{out} already exists; choose a new directory", file=sys.stderr)
        return 1
    files = (
        subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True)
        .stdout.decode("utf-8")
        .split("\0")
    )
    changed = 0
    for name in filter(None, files):
        source, target = Path(name), out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in TEXT:
            raw = source.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                shutil.copy2(source, target)
                continue
            clean, hits = scrub(text)
            if hits:
                changed += 1
                print(f"scrubbed {hits:>3} value(s): {name}")
            target.write_bytes(clean.encode("utf-8"))
        else:
            shutil.copy2(source, target)
    print(f"Copied {len(list(filter(None, files)))} tracked files to {out}; {changed} scrubbed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
