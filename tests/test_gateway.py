"""Offline HTTP contract fixture; these tests do not run or evaluate a real model."""

import json
import threading
import unittest
from unittest.mock import patch
from http.client import RemoteDisconnected
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from finance.domain import FinanceError
from finance.gateway import ChatGateway, GatewayConfig, GRANITE_TOOL_PROTOCOL


class GatewayTests(unittest.TestCase):
    def test_granite_protocol_preserves_rules_and_does_not_change_qwen_messages(self) -> None:
        messages = [
            {"role": "system", "content": "Read synthetic data only. Never approve payments."},
            {"role": "user", "content": "Read cash"},
        ]
        tools = [{"type": "function", "function": {"name": "get_financial_snapshot"}}]
        for family in ("granite", "qwen2"):
            gateway = ChatGateway(GatewayConfig(provider="ollama", model="fixture", enabled=True))
            gateway.local_model = {"details": {"family": family}}
            with patch.object(
                gateway,
                "_request",
                side_effect=[
                    {"models": [{"name": "fixture"}]},
                    {
                        "done": True,
                        "message": {"role": "assistant", "content": "test fixture"},
                        "prompt_eval_count": 20,
                        "eval_count": 2,
                    },
                ],
            ) as request:
                gateway.chat(messages, tools, {})
            sent = request.call_args.args[1]["messages"]
            if family == "granite":
                self.assertTrue(sent[0]["content"].startswith(messages[0]["content"]))
                self.assertIn(GRANITE_TOOL_PROTOCOL, sent[0]["content"])
            else:
                self.assertEqual(sent, messages)
            self.assertNotIn(GRANITE_TOOL_PROTOCOL, messages[0]["content"])

    def test_ollama_contract_tool_calls_usage_and_no_fallback(self) -> None:
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"models":[{"name":"offline-contract-fixture"}]}')

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(payload)
                self.send_response(200)
                self.end_headers()
                if self.path == "/api/show":
                    self.wfile.write(
                        b'{"details":{"parameter_size":"fixture"},"capabilities":["tools"]}'
                    )
                    return
                self.wfile.write(
                    json.dumps(
                        {
                            "done": True,
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "get_financial_snapshot",
                                            "arguments": {},
                                        }
                                    }
                                ],
                            },
                            "prompt_eval_count": 20,
                            "eval_count": 7,
                        }
                    ).encode()
                )

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = GatewayConfig(
                provider="ollama",
                model="offline-contract-fixture",
                base_url=f"http://127.0.0.1:{server.server_port}",
                enabled=True,
            )
            output = ChatGateway(config).chat([{"role": "user", "content": "Read cash"}], [], {})
            self.assertEqual(output["usage"]["tokens"], 27)
            self.assertEqual(
                output["message"]["tool_calls"][0]["function"]["name"], "get_financial_snapshot"
            )
            chat_request = next(r for r in requests if "messages" in r)
            self.assertFalse(chat_request["stream"])
            self.assertFalse(chat_request["think"])
            self.assertEqual(chat_request["options"]["num_ctx"], 8192)
            self.assertEqual(chat_request["options"]["num_gpu"], 0)
            self.assertEqual(chat_request["options"]["num_batch"], 128)
            self.assertTrue(chat_request["options"]["use_mmap"])
            self.assertEqual(chat_request["model"], "offline-contract-fixture")
            with self.assertRaisesRegex(FinanceError, "exactly match"):
                ChatGateway(replace(config, model="not-installed")).chat([], [], {})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        with self.assertRaises(FinanceError) as failed:
            ChatGateway(config).chat([], [], {})
        self.assertEqual(failed.exception.code, "MODEL_UNAVAILABLE")

    def test_connection_reset_is_a_typed_failure_without_fallback(self) -> None:
        gateway = ChatGateway(GatewayConfig(provider="ollama", model="fixture", enabled=True))
        for error in (ConnectionResetError(10054, "reset"), RemoteDisconnected("closed")):
            with self.subTest(error=type(error).__name__):
                with patch("finance.gateway.build_opener") as opener:
                    opener.return_value.open.side_effect = error
                    with self.assertRaises(FinanceError) as failed:
                        gateway.chat([], [], {})
                self.assertEqual(failed.exception.code, "MODEL_UNAVAILABLE")
                self.assertIs(failed.exception.__cause__, error)

    def test_T065_steps_tokens_time_and_no_paid_cost_enforced(self) -> None:
        # CPU detail prompts may opt into 240s per call; the task still caps at 600s.
        self.assertEqual(GatewayConfig(timeout_seconds=240).timeout_seconds, 240)
        for values in ({"timeout_seconds": 241}, {"max_elapsed_seconds": 601}):
            with self.assertRaises(FinanceError):
                GatewayConfig(**values)
        cases = [
            (GatewayConfig(max_steps=1), {"calls": 1}, "BUDGET_EXCEEDED"),
            (GatewayConfig(max_tokens=100), {}, "BUDGET_EXCEEDED"),
            (GatewayConfig(max_elapsed_seconds=1), {"elapsed_seconds": 1}, "BUDGET_EXCEEDED"),
            (GatewayConfig(max_billed_cost_minor=1), {}, "MODEL_COST_POLICY_DENIED"),
            (GatewayConfig(provider="paid_provider"), {}, "MODEL_COST_POLICY_DENIED"),
        ]
        for config, usage, code in cases:
            with self.subTest(config=config), self.assertRaises(FinanceError) as failed:
                ChatGateway(config).chat([], [], usage)
            self.assertEqual(failed.exception.code, code)

    def test_remote_model_endpoint_is_denied(self) -> None:
        gateway = ChatGateway(
            GatewayConfig(
                provider="ollama", model="fixture", enabled=True, base_url="https://example.com"
            )
        )
        with self.assertRaises(FinanceError) as failed:
            gateway.chat([], [], {})
        self.assertEqual(failed.exception.code, "MODEL_EGRESS_DENIED")
