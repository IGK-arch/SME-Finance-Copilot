"""Local allowlisted task runner for remote development sessions.

Started manually by the owner on the development machine:
    .venv\\Scripts\\python.exe -m scripts.devbridge

It polls .runtime/devbridge/queue/*.json and runs ONLY the task kinds below with
this project's own interpreter. It never runs shell strings, never deletes data
outside its own queue/out folders and never touches .runtime/pg-workspace except
through the read-only serve task chosen explicitly. Stop it with Ctrl+C.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / ".runtime" / "devbridge"
QUEUE, OUT = BRIDGE / "queue", BRIDGE / "out"
PY = sys.executable
SAFE = re.compile(r"^[A-Za-z0-9_.:/=\-]{1,120}$")
WORKSPACES = {"dev": ".runtime/v03-dev", "pg": ".runtime/pg-workspace", "e2e": ".runtime/v03-e2e"}
servers: dict[str, subprocess.Popen] = {}


def env() -> dict[str, str]:
    value = dict(os.environ)
    pg = ROOT / ".runtime" / "postgres" / "cluster.secret.json"
    if pg.exists():
        value.setdefault("SME_POSTGRES_TEST_CONFIG", str(pg))
    value["PYTHONIOENCODING"] = "utf-8"
    return value


def command(task: dict) -> tuple[list[str] | None, str | None]:
    kind = task.get("kind")
    args = [str(a) for a in task.get("args", [])]
    if any(not SAFE.match(a) for a in args):
        raise ValueError("unsafe argument")
    if kind == "module":  # python -m scripts.<x> / tests.<x> / unittest
        module = str(task.get("module", ""))
        if not re.match(r"^(scripts\.[a-z0-9_]+|unittest|tests\.[a-z0-9_]+)$", module):
            raise ValueError("module not allowed")
        if module == "scripts.devbridge":
            raise ValueError("recursive bridge")
        return [PY, "-m", module, *args], None
    if kind == "serve":
        name = str(task.get("workspace"))
        if name not in WORKSPACES:
            raise ValueError("unknown workspace")
        port = int(task.get("port", 8080))
        if not 8000 <= port <= 8999:
            raise ValueError("port")
        return [
            PY,
            "-m",
            "scripts.serve",
            "--port",
            str(port),
            "--directory",
            WORKSPACES[name],
            *args,
        ], f"serve-{port}"
    if kind == "stop":
        return None, f"serve-{int(task.get('port', 8080))}"
    raise ValueError("unknown kind")


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()


def handle(path: Path) -> None:
    task_id = path.stem
    result: dict = {"id": task_id, "started": time.time()}
    try:
        task = json.loads(path.read_text("utf-8"))
        argv, server = command(task)
        if task.get("kind") == "stop":
            proc = servers.pop(server or "", None)
            if proc:
                kill_tree(proc)
            result.update(status="STOPPED" if proc else "NOT_RUNNING")
        elif server:
            if server in servers and servers[server].poll() is None:
                result.update(status="ALREADY_RUNNING", pid=servers[server].pid)
            else:
                assert argv is not None
                log = open(OUT / f"{server}.log", "ab")
                servers[server] = subprocess.Popen(
                    argv, cwd=ROOT, env=env(), stdout=log, stderr=subprocess.STDOUT
                )
                result.update(status="STARTED", pid=servers[server].pid, log=f"{server}.log")
        else:
            assert argv is not None
            timeout = min(int(task.get("timeout", 1800)), 3600)
            done = subprocess.run(argv, cwd=ROOT, env=env(), capture_output=True, timeout=timeout)
            (OUT / f"{task_id}.log").write_bytes(done.stdout + b"\n--- stderr ---\n" + done.stderr)
            result.update(status="DONE", returncode=done.returncode, log=f"{task_id}.log")
    except Exception as error:  # report, never crash the loop
        result.update(status="ERROR", error=f"{type(error).__name__}: {error}")
    result["finished"] = time.time()
    (OUT / f"{task_id}.json").write_text(json.dumps(result), "utf-8")
    path.unlink(missing_ok=True)
    print(
        f"[devbridge] {task_id}: {result.get('status')} {result.get('returncode', '')}", flush=True
    )


def main() -> None:
    QUEUE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"[devbridge] watching {QUEUE} (Ctrl+C to stop; servers are stopped too)", flush=True)
    try:
        while True:
            for path in sorted(QUEUE.glob("*.json")):
                handle(path)
            time.sleep(1)
    finally:
        for proc in servers.values():
            kill_tree(proc)


if __name__ == "__main__":
    main()
