"""Explicit portable Ollama setup on E:, guarded singleton server, no implicit pull."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen
import zipfile

from scripts.resource_guard import (
    GIB,
    RUNTIME_LIMIT_BYTES,
    ResourceLimitError,
    Singleton,
    WindowsJob,
    check_resources,
    resource_snapshot,
)

ROOT = Path(__file__).resolve().parents[1] / ".runtime" / "ollama"
MODEL_DOWNLOAD_RESERVES = {
    "qwen2.5:7b": 5 * GIB,
    "granite3.3:8b": 5 * GIB,
    "qwen2.5:14b-instruct-q3_K_S": 7 * GIB,
}
MODELS = set(MODEL_DOWNLOAD_RESERVES)
ARCHIVE_URL = "https://github.com/ollama/ollama/releases/download/v0.40.3/ollama-windows-amd64.zip"
ARCHIVE_BYTES = 1468053171
ARCHIVE_SHA256 = "e5ecff02dfc7cae8ddf6d6b7a7ac5f727ffeedf4491f44ae75ff5b0820dbbbd5"


def checked_root() -> Path:
    root = ROOT.resolve()
    if root != ROOT or root.drive.upper() != "E:":
        raise ResourceLimitError("This launcher requires the project's .runtime/ollama on E:")
    root.mkdir(parents=True, exist_ok=True)
    return root


def local_environment(root: Path) -> dict[str, str]:
    cache_type = os.environ.get("SME_OLLAMA_KV_CACHE_TYPE", "q8_0")
    if cache_type not in {"q8_0", "q4_0"}:
        raise ResourceLimitError("SME_OLLAMA_KV_CACHE_TYPE must be q8_0 or q4_0")
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("OLLAMA_"):
            del env[key]
    temp = root / "temp"
    temp.mkdir(exist_ok=True)
    cuda_cache = root / "cuda-cache"
    cuda_cache.mkdir(exist_ok=True)
    env.update(
        OLLAMA_HOST="127.0.0.1:11434",
        OLLAMA_MODELS=str(root / "models"),
        OLLAMA_NO_CLOUD="1",
        OLLAMA_CONTEXT_LENGTH="8192",
        OLLAMA_NUM_PARALLEL="1",
        OLLAMA_MAX_LOADED_MODELS="1",
        OLLAMA_MAX_QUEUE="1",
        OLLAMA_KEEP_ALIVE="60s",
        OLLAMA_LOAD_TIMEOUT="60s",
        OLLAMA_FLASH_ATTENTION="1",
        OLLAMA_KV_CACHE_TYPE=cache_type,
        OLLAMA_VULKAN="false",
        TEMP=str(temp),
        TMP=str(temp),
        CUDA_CACHE_PATH=str(cuda_cache),
        CUDA_CACHE_MAXSIZE=str(128 * 1024**2),
        CUDA_VISIBLE_DEVICES="-1",
        HIP_VISIBLE_DEVICES="-1",
        LLAMA_ARG_REPACK="0",
        # The bundled llama-server otherwise retains an additional prompt cache
        # (default maximum 8192 MiB). Preserve context, not idle prompt copies.
        LLAMA_ARG_CACHE_RAM="0",
    )
    return env


def write_status(root: Path, report: dict) -> None:
    report["updated_unix"] = time.time()
    temp = root / "guard-status.tmp"
    temp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Windows readers/antivirus may briefly hold the destination without delete
    # sharing. Retry atomically for at most one second; persistent failure still
    # closes the job, rather than leaving an unmonitored model process running.
    for attempt in range(26):
        try:
            temp.replace(root / "guard-status.json")
            break
        except PermissionError:
            if attempt == 25:
                raise
            time.sleep(0.04)


def require_guard(root: Path) -> None:
    try:
        status = json.loads((root / "guard-status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResourceLimitError("Start scripts.local_llm serve first") from exc
    if status.get("status") != "RUNNING" or time.time() - status.get("updated_unix", 0) > 15:
        raise ResourceLimitError("No current guarded model server; refusing operation")


def install(root: Path) -> None:
    executable = root / "bin" / "ollama.exe"
    if executable.exists():
        raise ResourceLimitError("Portable runtime already exists; no replacement performed")
    check_resources(resource_snapshot(root), starting=True, extra_bytes=4 * GIB)
    archive = root / "ollama-windows-amd64.zip"
    if archive.exists():
        raise ResourceLimitError("Archive exists; inspect it before restarting installation")
    digest = hashlib.sha256()
    total = 0
    with urlopen(ARCHIVE_URL, timeout=30) as response, archive.open("xb") as output:
        while chunk := response.read(4 * 1024**2):
            total += len(chunk)
            if total > ARCHIVE_BYTES:
                raise ResourceLimitError("Archive exceeded pinned size")
            check_resources(resource_snapshot(root))
            output.write(chunk)
            digest.update(chunk)
    if total != ARCHIVE_BYTES or digest.hexdigest() != ARCHIVE_SHA256:
        raise ResourceLimitError("Archive size/digest mismatch; extraction refused")
    destination = root / "bin"
    if destination.exists():
        raise ResourceLimitError("Extraction destination already exists; no overwrite performed")
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if sum(e.file_size for e in entries) > 3 * GIB:
            raise ResourceLimitError("Unpacked archive exceeds budget")
        for entry in entries:
            target = (destination / entry.filename).resolve()
            if (
                not target.is_relative_to(destination)
                or ((entry.external_attr >> 16) & 0o170000) == 0o120000
            ):
                raise ResourceLimitError("Unsafe archive member")
        for entry in entries:
            check_resources(resource_snapshot(root))
            bundle.extract(entry, destination)
    if not executable.is_file():
        raise ResourceLimitError("Archive does not contain expected runtime")
    (root / "installation.json").write_text(
        json.dumps(
            {
                "url": ARCHIVE_URL,
                "bytes": total,
                "sha256": digest.hexdigest(),
                "installed_at_unix": time.time(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    archive.unlink()  # Only this verified, newly downloaded archive, under checked E: root.
    print("Verified portable runtime installed on E:; installation archive removed", flush=True)


def serve(root: Path) -> int:
    with Singleton("Local\\SMEFinanceOllamaServer11434"):
        check_resources(resource_snapshot(root), starting=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        report: dict = {
            "status": "STARTING",
            "launcher_pid": os.getpid(),
            "job_memory_limit_bytes": 2 * GIB,
            "runtime_limit_bytes": RUNTIME_LIMIT_BYTES,
            "poll_seconds": 0.5,
            "initial": resource_snapshot(root),
            "minimum": {},
            "peak_job_commit_bytes": 0,
            "peak_runtime_bytes": 0,
            "runtime_options": {
                key: value
                for key, value in local_environment(root).items()
                if key.startswith("OLLAMA_")
                or key
                in {
                    "TEMP",
                    "TMP",
                    "CUDA_CACHE_PATH",
                    "CUDA_CACHE_MAXSIZE",
                    "CUDA_VISIBLE_DEVICES",
                    "HIP_VISIBLE_DEVICES",
                    "LLAMA_ARG_REPACK",
                    "LLAMA_ARG_CACHE_RAM",
                }
            },
        }
        write_status(root, report)
        process = None
        try:
            with (root / "server.log").open("a", encoding="utf-8") as log, WindowsJob() as job:
                process = job.start(
                    [str(root / "bin" / "ollama.exe"), "serve"],
                    env=local_environment(root),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                report.update(status="RUNNING", child_pid=process.pid)
                print(
                    "Guarded CPU Ollama on 127.0.0.1:11434; 2 GiB process-tree commit limit",
                    flush=True,
                )
                while process.poll() is None:
                    sample = resource_snapshot(root)
                    report["latest"] = sample
                    report["peak_job_commit_bytes"] = max(
                        report["peak_job_commit_bytes"], job.peak_bytes()
                    )
                    report["peak_runtime_bytes"] = max(
                        report["peak_runtime_bytes"], sample["runtime_bytes"]
                    )
                    for key, value in sample.items():
                        if key != "runtime_bytes":
                            report["minimum"][key] = min(report["minimum"].get(key, value), value)
                    check_resources(sample)
                    write_status(root, report)
                    time.sleep(0.5)
                report.update(status="STOPPED", exit_code=process.returncode)
        except KeyboardInterrupt:
            report.update(status="STOPPED", reason="User interrupted launcher")
        except BaseException as exc:
            report.update(status="FAILED", reason=str(exc))
            raise
        finally:
            if process is not None:
                process.wait(timeout=10)
            write_status(root, report)
        return report.get("exit_code", 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["install", "status", "serve", "pull", "list", "ps", "stop"]
    )
    parser.add_argument("model", nargs="?")
    args = parser.parse_args()
    root = checked_root()
    if args.command == "status":
        print(json.dumps(resource_snapshot(root), indent=2))
        return
    if args.command == "install":
        with Singleton("Local\\SMEFinanceOllamaProvisioning"):
            install(root)
        return
    if not (root / "bin" / "ollama.exe").is_file():
        parser.error("Run explicit scripts.local_llm install first")
    if args.command == "serve":
        raise SystemExit(serve(root))
    if args.command in {"pull", "stop"} and not args.model:
        parser.error("An exact model name is required")
    if args.command == "pull" and args.model not in MODELS:
        parser.error("Model is not in the explicitly selected local comparison allowlist")
    require_guard(root)
    with Singleton("Local\\SMEFinanceOllamaProvisioning"):
        check_resources(
            resource_snapshot(root),
            extra_bytes=MODEL_DOWNLOAD_RESERVES[args.model] if args.command == "pull" else 0,
        )
        command = [str(root / "bin" / "ollama.exe"), args.command] + (
            [args.model] if args.model else []
        )
        with WindowsJob(GIB) as job:
            process = job.start(command, env=local_environment(root))
            raise SystemExit(process.wait())


if __name__ == "__main__":
    main()
