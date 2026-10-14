"""Loopback-only capability-separated sandbox service."""

from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from sandbox.world import World, WorldError


def make_server(
    world: World, port: int, credentials: dict[str, str], tenant: str
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # Never log headers/capabilities.

        def do_POST(self) -> None:
            self.handle_request()

        def do_GET(self) -> None:
            self.handle_request()

        def handle_request(self) -> None:
            path = urlparse(self.path).path
            scope = (
                "admin"
                if path.startswith("/admin/")
                else "execute"
                if path == "/commands"
                else "observe"
            )
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            allowed = [credentials[scope]] + (
                [credentials["execute"]] if scope == "observe" else []
            )
            if not any(hmac.compare_digest(supplied, token) for token in allowed):
                self.reply(403, {"error": "Capability denied"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 1_000_000:
                    raise WorldError("Body too large")
                value = json.loads(self.rfile.read(length)) if length else {}
                if "tenant" in value and value["tenant"] != tenant:
                    raise WorldError("Tenant denied")
                if path == "/observation" and self.command == "GET":
                    result = world.observation(tenant)
                elif path == "/status" and self.command == "POST":
                    result = world.status(tenant, value["stable_key"])
                elif path == "/commands" and self.command == "POST":
                    result = world.submit(tenant, value["command"], value.get("fault", "none"))
                elif path == "/admin/seed" and self.command == "POST":
                    world.seed(value)
                    result = {"status": "SEEDED_SYNTHETIC_WORLD"}
                elif path == "/admin/advance" and self.command == "POST":
                    result = world.advance(tenant, value["clock"])
                elif path == "/admin/external" and self.command == "POST":
                    world.external_movement(tenant, value["delta"], value["reference"])
                    result = {"status": "SYNTHETIC_MOVEMENT_RECORDED"}
                elif path == "/admin/evaluate" and self.command == "POST":
                    result = world.evaluate(tenant, value["reserve_minor"])
                elif path == "/admin/extension" and self.command == "POST":
                    result = world.extension_decision(
                        tenant,
                        value["request_id"],
                        value["obligation_id"],
                        value["due_at"],
                        value["accepted"],
                    )
                else:
                    self.reply(404, {"error": "Unsupported sandbox path"})
                    return
                self.reply(200, result)
            except TimeoutError:
                self.reply(503, {"error": "Response unavailable; outcome unknown"})
            except (WorldError, ValueError, KeyError, TypeError) as exc:
                self.reply(409, {"error": str(exc)})

        def reply(self, code: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--tenant", default="demo_company")
    args = parser.parse_args()
    creds = json.loads(os.environ["SME_SANDBOX_CAPABILITIES"])
    server = make_server(World(args.db), args.port, creds, args.tenant)
    print(f"Sandbox listening on 127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
