"""Server-only read/chat sidecar: real Windows telemetry and pinned llama.cpp identity.

The /v1/status endpoint belongs to this benchmark, not upstream llama.cpp.
No model downloads, process control, filesystem tools or financial tools are exposed.
"""

from __future__ import annotations

import argparse
import ctypes
import http.client
import json
import shutil
import time
from typing import Any, cast
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def machine(directory: Path) -> dict:
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total",
                "free",
                "commit_total",
                "commit_free",
                "virtual",
                "virtual_free",
                "extended",
            )
        ]

    value = Memory()
    value.length = ctypes.sizeof(value)
    if not cast(Any, ctypes).windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError("Memory telemetry unavailable")
    return {
        "at": time.time(),
        "ram": {
            "total_gib": value.total / 1024**3,
            "used_gib": (value.total - value.free) / 1024**3,
        },
        "commit_free_gib": value.commit_free / 1024**3,
        "disk_free_gib": shutil.disk_usage(directory).free / 1024**3,
    }


def native(path: str, body: bytes | None = None) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", 8081, timeout=240)
    try:
        connection.request(
            "POST" if body is not None else "GET", path, body, {"Content-Type": "application/json"}
        )
        response = connection.getresponse()
        value = response.read(1_000_001)
        if len(value) > 1_000_000:
            raise ValueError("Native response limit")
        return response.status, value
    finally:
        connection.close()


def status(directory: Path) -> dict:
    state = json.loads((directory / "active.json").read_text(encoding="utf-8"))
    code, raw = native("/props")
    if code != 200:
        raise ValueError("Native server not ready")
    props = json.loads(raw)
    if Path(props["model_path"]).resolve() != Path(state["model_path"]).resolve():
        raise ValueError("Native weight path changed")
    if props.get("is_sleeping") is True or props.get("total_slots") != 1:
        raise ValueError("Unexpected native slot state")
    context = props.get("default_generation_settings", {}).get("n_ctx")
    return {
        "service": "llamacpp-bench",
        "loaded": True,
        "model": state["model"],
        "started": state["started"],
        "engine": state["engine"],
        "weight_sha256": state["weight_sha256"],
        "license": state["license"],
        "reasoning_mode": state["reasoning_mode"],
        "cache_max_tokens": context,
        "machine": machine(directory),
    }


def handler(directory: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code: int, value: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(value)))
            self.end_headers()
            self.wfile.write(value)

        def do_GET(self):
            try:
                if self.path == "/v1/status":
                    self.send(200, json.dumps(status(directory)).encode())
                elif self.path in {"/health", "/v1/models"}:
                    self.send(*native(self.path))
                else:
                    self.send(403, b'{"error":"ROUTE_DENIED"}')
            except Exception:
                self.send(503, b'{"error":"BENCH_BACKEND_UNAVAILABLE"}')

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    self.path != "/v1/chat/completions"
                    or self.headers.get("Transfer-Encoding")
                    or not 0 < length <= 1_000_000
                ):
                    self.send(403, b'{"error":"ROUTE_OR_BODY_DENIED"}')
                    return
                raw = self.rfile.read(length)
                request = json.loads(raw)
                active = status(directory)
                if (
                    request.get("model") != active["model"]
                    or request.get("stream") is not False
                    or request.get("reasoning_effort") != "none"
                ):
                    self.send(400, b'{"error":"FIXED_BENCH_CONFIG_REQUIRED"}')
                    return
                telemetry = active["machine"]
                if (
                    telemetry["ram"]["total_gib"] - telemetry["ram"]["used_gib"] < 5
                    or telemetry["commit_free_gib"] < 5
                    or telemetry["disk_free_gib"] < 20
                ):
                    self.send(503, b'{"error":"RESOURCE_GUARD"}')
                    return
                self.send(*native(self.path, raw))
            except Exception:
                self.send(503, b'{"error":"BENCH_BACKEND_UNAVAILABLE"}')

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(
        ("127.0.0.1", 8082), handler(Path(args.directory).resolve())
    ).serve_forever()


if __name__ == "__main__":
    main()
