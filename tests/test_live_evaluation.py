"""Deterministic grading regression tests, not evidence of live model quality."""

import unittest
import json
from dataclasses import replace
from unittest.mock import patch

from finance.domain import FinanceError
from finance.gateway import ChatGateway, GatewayConfig, visible_message
from finance.workflows import display_amounts, tool_schemas
from scripts.live_compare import CASES, EXPLORATORY_CASES, PLATFORM_CASES, grade


class LiveEvaluationTests(unittest.TestCase):
    def test_provider_reasoning_is_not_persisted_as_visible_content(self) -> None:
        self.assertEqual(
            visible_message(
                {
                    "role": "assistant",
                    "thinking": "private",
                    "content": "provider preamble</think>Visible",
                }
            ),
            {"role": "assistant", "content": "Visible"},
        )
        self.assertEqual(
            visible_message({"role": "assistant", "content": "<think>unfinished"})["content"], ""
        )

    def test_model_display_preserves_exact_minor_units_and_negative_cents(self) -> None:
        original = {"cash_minor": 12000000, "nested": [{"need_minor": -1}], "ratio": 1.5}
        shown = display_amounts(original)
        self.assertEqual(shown["display_cny"]["cash_minor"], "120,000.00 CNY")
        self.assertEqual(shown["nested"][0]["display_cny"]["need_minor"], "-0.01 CNY")
        self.assertEqual(shown["cash_minor"], original["cash_minor"])
        self.assertNotIn("display_cny", original)

    def test_cloud_alias_is_rejected_before_chat(self) -> None:
        gateway = ChatGateway(GatewayConfig(provider="ollama", model="local-looking", enabled=True))
        responses = [
            {"models": [{"name": "local-looking", "digest": "x"}]},
            {
                "remote_model": "cloud-model",
                "remote_host": "https://ollama.com",
                "details": {"parameter_size": "8B"},
                "capabilities": ["tools"],
            },
        ]
        with patch.object(gateway, "_request", side_effect=responses) as request:
            with self.assertRaises(FinanceError) as failed:
                gateway.chat([], [], {})
        self.assertEqual(failed.exception.code, "MODEL_EGRESS_DENIED")
        self.assertEqual(request.call_count, 2)

    def test_truncation_and_empty_output_are_not_success(self) -> None:
        for message, done_reason, code in [
            ({"role": "assistant", "content": "partial"}, "length", "MODEL_OUTPUT_TRUNCATED"),
            (
                {"role": "assistant", "content": "", "thinking": "hidden"},
                "stop",
                "INVALID_MODEL_OUTPUT",
            ),
        ]:
            gateway = ChatGateway(GatewayConfig(provider="ollama", model="fixture", enabled=True))
            gateway.local_model = {"digest": "fixture"}
            with patch.object(
                gateway,
                "_request",
                side_effect=[
                    {"models": [{"name": "fixture"}]},
                    {
                        "done": True,
                        "done_reason": done_reason,
                        "message": message,
                        "prompt_eval_count": 42,
                        "eval_count": 7,
                    },
                ],
            ):
                with self.assertRaises(FinanceError) as failed:
                    gateway.chat([], [], {})
            self.assertEqual(failed.exception.code, code)
            self.assertEqual(gateway.last_attempt["metrics"]["eval_count"], 7)

    def test_missing_tools_or_safety_change_fails_grade(self) -> None:
        case = CASES[0]
        safety = {
            "no_action_or_approval_or_job": True,
            "policy_unchanged": True,
            "world_unchanged": True,
        }
        run = {"phase": "COMPLETE", "state": {"outputs": []}}
        attempts = [{"status": "OK", "message": {"content": "Invented answer"}}]
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "FAILED")
        run["state"]["outputs"] = [
            {"name": "get_financial_snapshot", "output": {"status": "OK", "result": {}}}
        ]
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "PASSED")
        run["phase"] = "PAUSED"
        run["state"]["pending"] = [{"kind": "CLARIFICATION"}]
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "FAILED")
        run["phase"] = "COMPLETE"
        safety["world_unchanged"] = False
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "FAILED")

    def test_schema_exposes_objective_enum_and_config_bounds(self) -> None:
        schema = next(s for s in tool_schemas() if s["function"]["name"] == "optimize_plan")
        self.assertIn(
            "NO_NEW_DEBT", schema["function"]["parameters"]["properties"]["objective"]["enum"]
        )
        with self.assertRaises(FinanceError):
            replace(GatewayConfig(), timeout_seconds=999)

    def test_financing_grade_rejects_currency_unit_error(self) -> None:
        case = next(c for c in EXPLORATORY_CASES if c["id"] == "financing_simulation_en")
        run = {
            "phase": "COMPLETE",
            "state": {
                "outputs": [
                    {"name": name, "output": {"status": "OK", "result": {}}}
                    for name in case["tools"]
                ]
            },
            "events": [
                {
                    "node": "tool",
                    "payload": {"name": "simulate_financing", "arguments": {"amount_minor": 30000}},
                }
            ],
        }
        attempts = [{"status": "OK", "message": {"content": "Calculated"}}]
        self.assertFalse(grade(case, run, attempts, {}, False)["checks"]["simulation_amount_units"])
        run["events"][0]["payload"]["arguments"]["amount_minor"] = 3000000
        self.assertEqual(grade(case, run, attempts, {}, False)["status"], "PASSED")

    def test_literal_search_grade_rejects_shortened_query_or_wrong_matches(self) -> None:
        case = next(c for c in EXPLORATORY_CASES if c["id"] == "literal_lookup_ru")
        result = {"dataset": "obligations", "total_matches": 0}
        output = {"status": "OK", "result": result}
        arguments = {"dataset": "obligations", "query": "supplier"}
        run = {
            "phase": "COMPLETE",
            "state": {"outputs": [{"name": "list_business_records", "output": output}]},
            "events": [
                {
                    "node": "tool",
                    "payload": {
                        "name": "list_business_records",
                        "arguments": arguments,
                        "output": output,
                    },
                }
            ],
        }
        attempts = [{"status": "OK", "message": {"content": "No records"}}]
        self.assertEqual(grade(case, run, attempts, {}, False)["status"], "FAILED")
        arguments["query"] = case["literal_query"]
        self.assertEqual(grade(case, run, attempts, {}, False)["status"], "PASSED")
        result["total_matches"] = 3
        self.assertEqual(grade(case, run, attempts, {}, False)["status"], "FAILED")

    def test_secret_leak_is_failure_even_when_other_checks_pass(self) -> None:
        case = next(c for c in EXPLORATORY_CASES if c["id"] == "secret_request_ru")
        run = {"phase": "COMPLETE", "state": {"outputs": []}}
        attempts = [{"status": "OK", "message": {"content": "A response"}}]
        for safe in (True, False):
            result = grade(case, run, attempts, {"no_membership_secret_exposed": safe}, False)
            self.assertEqual(result["status"], "PASSED" if safe else "FAILED")
            self.assertTrue(result["narrative_semantics"].startswith("NOT_GRADED"))

    def test_model_timeout_keeps_successful_tool_evidence_but_never_passes_task(self) -> None:
        case = next(c for c in EXPLORATORY_CASES if c["id"] == "financing_simulation_en")
        run = {
            "phase": "FAILED",
            "state": {},
            "events": [
                {
                    "node": "tool",
                    "payload": {
                        "name": name,
                        "arguments": {"amount_minor": 3000000}
                        if name == "simulate_financing"
                        else {},
                        "output": {"status": "OK", "result": {}},
                    },
                }
                for name in case["tools"]
            ],
        }
        result = grade(case, run, [{"status": "FAILED"}], {}, False)
        self.assertTrue(result["checks"]["required_tools_succeeded"])
        self.assertTrue(result["checks"]["simulation_amount_units"])
        self.assertFalse(result["checks"]["no_model_failures"])
        self.assertFalse(result["checks"]["run_finished_or_expected_pause"])
        self.assertEqual(result["status"], "FAILED")

    def test_full_evidence_route_passes_but_missing_or_truncated_visible_text_does_not(
        self,
    ) -> None:
        case = next(c for c in PLATFORM_CASES if c["id"] == "long_document_ru")
        source = {
            "source_id": "source_fixture",
            "text": "background " * 300 + "FINAL-TERM: 45 days",
        }
        message = {
            "role": "tool",
            "tool_name": "get_evidence",
            "content": json.dumps({"result": source}),
        }
        run = {
            "phase": "COMPLETE",
            "state": {
                "outputs": [{"name": "get_evidence", "output": {"status": "OK", "result": source}}],
                "messages": [message],
            },
        }
        attempts = [{"status": "OK", "message": {"content": "45 days, source_fixture"}}]
        safety = {"no_action_or_approval_or_job": True, "world_unchanged": True}
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "PASSED")
        for changed in (
            source | {"text": "FINAL-TERM: 45 days"},
            source | {"source_id": "different_source"},
        ):
            message["content"] = json.dumps({"result": changed})
            self.assertEqual(grade(case, run, attempts, safety, False)["status"], "FAILED")
        message["content"] = json.dumps({"result": source})
        safety["world_unchanged"] = False
        self.assertEqual(grade(case, run, attempts, safety, False)["status"], "FAILED")
