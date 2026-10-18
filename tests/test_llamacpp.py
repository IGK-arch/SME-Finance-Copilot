"""Offline adapter tests; not LIVE model quality evidence."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from finance.domain import FinanceError
from finance.gateway import ChatGateway, GatewayConfig
from scripts.llama_bench_service import status
from tests.test_strata import MODEL, response


STATE = {
    "service": "llamacpp-bench",
    "loaded": True,
    "model": MODEL,
    "engine": "fixture-llama-build",
    "started": 123,
    "weight_sha256": "a" * 64,
    "cache_max_tokens": 16384,
    "reasoning_mode": "none",
    "license": "fixture-only",
}


class LlamaCppTests(unittest.TestCase):
    def gateway(self):
        return ChatGateway(GatewayConfig(provider="llamacpp", model=MODEL, enabled=True))

    def test_native_usage_and_hidden_reasoning_stay_separate(self):
        gateway = self.gateway()
        with patch.object(
            gateway, "_request", side_effect=[STATE, {"data": [{"id": MODEL}]}, response()]
        ) as request:
            output = gateway.chat([], [], {})
        self.assertEqual(request.call_args_list[-1].args[1]["reasoning_effort"], "none")
        self.assertEqual(
            output["usage"]["last_request"]["measurement_source"], "LLAMACPP_RESPONSE_USAGE"
        )
        self.assertEqual(output["usage"]["tokens"], 25)
        self.assertNotIn("DO_NOT_PERSIST", json.dumps([output, gateway.last_attempt]))
        self.assertEqual(gateway.config.public()["mode"], "LIVE")

    def test_unverified_or_changed_identity_fails_closed(self):
        for changed in (
            {"weight_sha256": None},
            {"model": "other"},
            {"service": "strata"},
            {"loaded": False},
            {"cache_max_tokens": 1},
            {"reasoning_mode": "medium"},
        ):
            gateway = self.gateway()
            with (
                patch.object(
                    gateway,
                    "_request",
                    side_effect=[{**STATE, **changed}, {"data": [{"id": MODEL}]}],
                ),
                self.assertRaises(FinanceError),
            ):
                gateway.describe()
        gateway = self.gateway()
        with patch.object(gateway, "_request", side_effect=[STATE, {"data": [{"id": MODEL}]}]):
            gateway.local_model = gateway.describe()
        with (
            patch.object(
                gateway,
                "_request",
                side_effect=[{**STATE, "weight_sha256": "b" * 64}, {"data": [{"id": MODEL}]}],
            ),
            self.assertRaises(FinanceError) as error,
        ):
            gateway.chat([], [], {})
        self.assertEqual(error.exception.code, "MODEL_CHANGED")

    def test_auth_egress_budget_and_thinking_guards_remain_required(self):
        gateway = self.gateway()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(FinanceError) as error:
            gateway._request("/health")
        self.assertEqual(error.exception.code, "MODEL_DISABLED")
        gateway = ChatGateway(replace(gateway.config, base_url="https://example.com"))
        with self.assertRaises(FinanceError) as error:
            gateway._request("/health")
        self.assertEqual(error.exception.code, "MODEL_EGRESS_DENIED")
        with self.assertRaises(FinanceError) as error:
            self.gateway().chat([], [], {"calls": 12})
        self.assertEqual(error.exception.code, "BUDGET_EXCEEDED")
        gateway = ChatGateway(replace(self.gateway().config, think=True))
        with (
            patch.object(gateway, "_request", side_effect=[STATE, {"data": [{"id": MODEL}]}]),
            self.assertRaises(FinanceError),
        ):
            gateway.describe()

    def test_sidecar_checks_actual_native_path_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {**STATE, "model_path": str(root / "weights.gguf")}
            (root / "active.json").write_text(json.dumps(state), encoding="utf-8")
            props = {
                "model_path": state["model_path"],
                "total_slots": 1,
                "default_generation_settings": {"n_ctx": 16384},
            }
            with (
                patch(
                    "scripts.llama_bench_service.native",
                    return_value=(200, json.dumps(props).encode()),
                ),
                patch("scripts.llama_bench_service.machine", return_value={"at": 1}),
            ):
                self.assertEqual(status(root)["cache_max_tokens"], 16384)
            props["model_path"] = str(root / "other.gguf")
            with (
                patch(
                    "scripts.llama_bench_service.native",
                    return_value=(200, json.dumps(props).encode()),
                ),
                self.assertRaises(ValueError),
            ):
                status(root)


if __name__ == "__main__":
    unittest.main()
