"""Authenticated loopback HTTP bridge to an owner's Strata over verified SSH.

No model installation, remote shell, public listener, or payment capability.
Install optional paramiko separately; --client-lib may name that installation.
"""

from __future__ import annotations

import argparse
import hmac
import http.client
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ALLOWED = {
    ("GET", "/health"),
    ("GET", "/v1/models"),
    ("GET", "/v1/status"),
    ("POST", "/v1/chat/completions"),
}
LIMIT = 1_000_000
CHAT_FIELDS = {
    "model",
    "messages",
    "tools",
    "tool_choice",
    "stream",
    "temperature",
    "max_tokens",
    "reasoning_effort",
}


def make_handler(transport, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.forward()

        def do_POST(self):
            self.forward()

        def reply(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def forward(self) -> None:
            if not hmac.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"),
                ("Bearer " + token).encode("utf-8"),
            ):
                self.reply(401, b'{"error":"BRIDGE_AUTH_REQUIRED"}')
                return
            if self.headers.get("Origin") or (self.command, self.path) not in ALLOWED:
                self.reply(403, b'{"error":"BRIDGE_ROUTE_DENIED"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= LIMIT or self.headers.get("Transfer-Encoding"):
                    self.reply(413, b'{"error":"BRIDGE_BODY_LIMIT"}')
                    return
                body = self.rfile.read(length) if length else None
                if self.command == "POST":
                    value = json.loads(body or b"{}")
                    # The platform executes its own tools. Strata MCP and vision/URL fetches
                    # are deliberately unavailable through this evaluation connection.
                    if (
                        not isinstance(value, dict)
                        or not set(value) <= CHAT_FIELDS
                        or value.get("stream") is not False
                        or value.get("tool_choice") not in (None, "auto", "none")
                        or not isinstance(value.get("messages"), list)
                        or any(
                            not isinstance(m, dict) or not isinstance(m.get("content", ""), str)
                            for m in value.get("messages", [])
                        )
                    ):
                        self.reply(400, b'{"error":"BRIDGE_TEXT_ONLY_NONSTREAM_REQUIRED"}')
                        return
                channel = transport.open_channel(
                    "direct-tcpip", ("127.0.0.1", 8080), ("127.0.0.1", 0), timeout=15
                )
                channel.settimeout(240)
                response = http.client.HTTPResponse(channel)
                try:
                    # HTTPConnection closes HTTP/1.0 sockets before reading their
                    # file object. Paramiko channels do not preserve that file's
                    # lifetime, so own the channel until the response is consumed.
                    header = (
                        f"{self.command} {self.path} HTTP/1.0\r\nHost: 127.0.0.1:8080\r\n"
                        "Content-Type: application/json; charset=utf-8\r\nConnection: close\r\n"
                        f"Content-Length: {len(body or b'')}\r\n\r\n"
                    )
                    channel.sendall(header.encode("ascii") + (body or b""))
                    response.begin()
                    result = response.read(LIMIT + 1)
                    if len(result) > LIMIT:
                        self.reply(502, b'{"error":"BRIDGE_RESPONSE_LIMIT"}')
                    elif 300 <= response.status < 400:
                        self.reply(502, b'{"error":"BRIDGE_REDIRECT_DENIED"}')
                    else:
                        self.reply(response.status, result)
                finally:
                    response.close()
                    channel.close()
            except Exception:
                self.reply(502, b'{"error":"BRIDGE_REQUEST_FAILED"}')

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Ignored local secret JSON")
    parser.add_argument("--client-lib", help="Separate optional Paramiko installation")
    args = parser.parse_args()
    if args.client_lib:
        sys.path.insert(0, str(Path(args.client_lib).resolve()))
    import importlib

    paramiko = importlib.import_module("paramiko")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    token = cfg["bridge_token"]
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("A random bridge token of at least 32 characters is required")
    credential_path = Path(cfg["credential_file"])
    credential = credential_path.read_text(encoding="utf-8-sig").strip()
    client = paramiko.SSHClient()
    client.load_host_keys(cfg["known_hosts"])
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    auth = (
        {"pkey": paramiko.PKey.from_path(credential_path)}
        if credential.startswith("-----BEGIN ")
        else {"password": credential}
    )
    client.connect(
        cfg["ssh_host"],
        port=cfg["ssh_port"],
        username=cfg["ssh_user"],
        timeout=15,
        auth_timeout=20,
        look_for_keys=False,
        allow_agent=False,
        **auth,
    )
    transport = client.get_transport()
    transport.set_keepalive(20)
    server = ThreadingHTTPServer(("127.0.0.1", cfg["local_port"]), make_handler(transport, token))
    server.daemon_threads = True

    def watch_connection():
        # A lost SSH session is never replaced with a different route/provider.
        while transport.is_active():
            threading.Event().wait(5)
        server.shutdown()

    threading.Thread(target=watch_connection, daemon=True).start()
    print(
        f"Strata SSH bridge ready on loopback port {cfg['local_port']} (authentication required)",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        client.close()


if __name__ == "__main__":
    main()
