"""Offline protocol/authority tests; fixture outputs are never model quality evidence."""

import json
import socket
import threading
import time
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from finance.domain import Config, FinanceError
from finance.gateway import ChatGateway, GatewayConfig
from finance.strata import wire_messages
from scripts.strata_bridge import make_handler
from scripts.strata_eval import check_resources


MODEL = "strata-offline-contract-fixture"
STATUS = {
    "service": "strata",
    "model": MODEL,
    "loaded": True,
    "engine": "fixture-version",
    "started": 10,
    "cache_max_tokens": 32768,
}


def response(content="Проверка", calls=None, reason="stop"):
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": reason,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": calls,
                    "reasoning_content": "DO_NOT_PERSIST",
                },
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
    }


class StrataTests(unittest.TestCase):
    def gateway(self):
        return ChatGateway(GatewayConfig(provider="strata", model=MODEL, enabled=True))

    def test_native_calls_usage_and_ordered_result_ids(self):
        calls = [
            {
                "id": "call_a",
                "type": "function",
                "function": {"name": "get_cash", "arguments": "{}"},
            },
            {
                "id": "call_b",
                "type": "function",
                "function": {"name": "get_fact", "arguments": '{"id":"账款"}'},
            },
        ]
        gateway = self.gateway()
        with patch.object(
            gateway,
            "_request",
            side_effect=[STATUS, {"data": [{"id": MODEL}]}, response(None, calls, "tool_calls")],
        ) as request:
            output = gateway.chat([{"role": "user", "content": "Cash?"}], [], {})
        self.assertEqual(request.call_args_list[-1].args[1]["tool_choice"], "none")
        self.assertEqual(output["usage"]["tokens"], 25)
        self.assertEqual(
            output["message"]["tool_calls"][1]["function"]["arguments"], {"id": "账款"}
        )
        self.assertNotIn("DO_NOT_PERSIST", json.dumps(output))
        messages = [
            output["message"],
            {"role": "tool", "tool_name": "get_cash", "content": "{}"},
            {"role": "tool", "tool_name": "get_fact", "content": "{}"},
        ]
        wire = wire_messages(messages)
        self.assertEqual([m["tool_call_id"] for m in wire[1:]], ["call_a", "call_b"])
        self.assertIsInstance(wire[0]["tool_calls"][0]["function"]["arguments"], str)
        for malformed in (messages[:2], messages[:1] + messages[2:]):
            with self.assertRaises(FinanceError):
                wire_messages(malformed)

    def test_truncation_invalid_usage_and_arguments_are_failures(self):
        truncated = response(reason="length")
        no_usage = response()
        no_usage.pop("usage")
        wrong_counts = response()
        wrong_counts["usage"]["total_tokens"] = 999
        malformed_calls = response(
            None,
            [{"id": "x", "type": "function", "function": {"name": "get_cash", "arguments": "[]"}}],
            "tool_calls",
        )
        for body, expected in [
            (truncated, "MODEL_OUTPUT_TRUNCATED"),
            (no_usage, "MODEL_USAGE_MISSING"),
            (wrong_counts, "MODEL_USAGE_MISSING"),
            (malformed_calls, "INVALID_MODEL_OUTPUT"),
        ]:
            gateway = self.gateway()
            with (
                patch.object(
                    gateway, "_request", side_effect=[STATUS, {"data": [{"id": MODEL}]}, body]
                ),
                self.assertRaises(FinanceError) as error,
            ):
                gateway.chat([], [], {})
            self.assertEqual(error.exception.code, expected)

    def test_model_or_instance_change_is_not_silent(self):
        gateway = self.gateway()
        with patch.object(gateway, "_request", side_effect=[STATUS, {"data": [{"id": MODEL}]}]):
            gateway.local_model = gateway.describe()
        self.assertIsNone(gateway.local_model["weight_digest"])
        with (
            patch.object(
                gateway,
                "_request",
                side_effect=[STATUS | {"started": 11}, {"data": [{"id": MODEL}]}],
            ),
            self.assertRaises(FinanceError) as error,
        ):
            gateway.chat([], [], {})
        self.assertEqual(error.exception.code, "MODEL_CHANGED")
        with (
            patch.object(
                gateway,
                "_request",
                side_effect=[STATUS | {"model": "other"}, {"data": [{"id": "other"}]}],
            ),
            self.assertRaises(FinanceError) as error,
        ):
            gateway.describe()
        self.assertEqual(error.exception.code, "MODEL_NOT_INSTALLED")

    def test_preflight_failure_does_not_duplicate_previous_measurements(self):
        from scripts.live_compare import MeasuredGateway

        gateway = MeasuredGateway(self.gateway().config)
        with patch.object(
            gateway,
            "_request",
            side_effect=[STATUS, {"data": [{"id": MODEL}]}, response()],
        ):
            gateway.chat([], [], {})
        with patch.object(gateway, "_request") as request, self.assertRaises(FinanceError):
            gateway.chat([], [], {"tokens": gateway.config.max_tokens})
        request.assert_not_called()
        self.assertEqual(gateway.attempts[1]["provider_measurement"], {"status": "NOT_SENT"})
        self.assertEqual(gateway.attempts[0]["provider_measurement"]["metrics"]["eval_count"], 5)

    def test_opt_in_token_and_egress_controls(self):
        with patch.dict(
            "os.environ",
            {
                "MODEL_PROVIDER": "strata",
                "MODEL_NAME": MODEL,
                "ALLOW_LOCAL_MODEL_INFERENCE": "true",
                "ALLOW_SERVER_MODEL_INFERENCE": "false",
            },
            clear=True,
        ):
            self.assertFalse(GatewayConfig.environment().enabled)
            self.assertEqual(Config.from_environment().model_provider, "strata")
        for config, expected in [
            (replace(self.gateway().config, enabled=False), "MODEL_DISABLED"),
            (replace(self.gateway().config, base_url="https://example.com"), "MODEL_EGRESS_DENIED"),
            (self.gateway().config, "MODEL_DISABLED"),
        ]:
            with patch.dict("os.environ", {}, clear=True), self.assertRaises(FinanceError) as error:
                ChatGateway(config).chat([], [], {})
            self.assertEqual(error.exception.code, expected)

    def test_utf8_http10_bridge_auth_and_route_boundary(self):
        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({"text": "Париж / 苏州"}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)

        class Transport:
            def open_channel(self, kind, destination, source, timeout):
                assert kind == "direct-tcpip" and destination == ("127.0.0.1", 8080)
                return socket.create_connection(backend.server_address)

        bridge = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(Transport(), "fixture-only-token")
        )
        threads = [threading.Thread(target=s.serve_forever) for s in (backend, bridge)]
        for thread in threads:
            thread.start()
        opener = build_opener(ProxyHandler({}))
        url = f"http://127.0.0.1:{bridge.server_port}"
        try:
            for path, headers, expected in [
                ("/health", {}, 401),
                ("/health", {"Authorization": "Bearer caf\u00e9"}, 401),
                ("/load", {"Authorization": "Bearer fixture-only-token"}, 403),
                (
                    "/health",
                    {
                        "Authorization": "Bearer fixture-only-token",
                        "Origin": "https://other.example",
                    },
                    403,
                ),
            ]:
                with self.assertRaises(HTTPError) as error:
                    opener.open(Request(url + path, headers=headers), timeout=5)
                self.assertEqual(error.exception.code, expected)
            with opener.open(
                Request(url + "/health", headers={"Authorization": "Bearer fixture-only-token"}),
                timeout=5,
            ) as reply:
                self.assertEqual(json.loads(reply.read())["text"], "Париж / 苏州")
            for payload in (
                {"stream": False, "messages": [], "strata_mcp": True},
                {"stream": False, "messages": [], "extra_body": {"mcp": True}},
                {"stream": True, "messages": []},
                {"stream": False, "messages": [], "tool_choice": "required"},
                {"stream": False, "messages": [{"content": [{"type": "image_url"}]}]},
            ):
                with self.assertRaises(HTTPError) as error:
                    opener.open(
                        Request(
                            url + "/v1/chat/completions",
                            data=json.dumps(payload).encode(),
                            headers={"Authorization": "Bearer fixture-only-token"},
                        ),
                        timeout=5,
                    )
                self.assertEqual(error.exception.code, 400)
        finally:
            for server in (bridge, backend):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()

    def test_resource_gate_waits_for_small_clock_lead_without_accepting_future_data(self):
        status = {"machine": {"at": 101, "ram": {"total_gib": 64, "used_gib": 48}}}
        with (
            patch("scripts.strata_eval.time.time", side_effect=[100, 101.1]),
            patch("scripts.strata_eval.time.sleep") as sleep,
            patch("scripts.strata_eval.shutil.disk_usage") as disk,
        ):
            disk.return_value.free = 10 * 1024**3
            self.assertEqual(check_resources(status), status["machine"])
            sleep.assert_called_once_with(1.05)
        for timestamp in (101, 103):
            with (
                patch("scripts.strata_eval.time.time", return_value=100),
                patch("scripts.strata_eval.time.sleep"),
                self.assertRaises(FinanceError),
            ):
                check_resources({"machine": status["machine"] | {"at": timestamp}})

    def test_resource_gate_rejects_low_or_stale_server_memory(self):
        status = {"machine": {"at": time.time(), "ram": {"total_gib": 64, "used_gib": 48}}}
        with patch("scripts.strata_eval.shutil.disk_usage") as disk:
            disk.return_value.free = 10 * 1024**3
            self.assertEqual(check_resources(status), status["machine"])
            for item in (
                {"at": time.time(), "ram": {"total_gib": 64, "used_gib": 60}},
                {"at": time.time() - 61, "ram": {"total_gib": 64, "used_gib": 48}},
            ):
                with self.assertRaises(FinanceError):
                    check_resources({"machine": item})


if __name__ == "__main__":
    unittest.main()
