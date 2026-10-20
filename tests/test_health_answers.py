"""Typed health presentation regressions; recorded LIVE traces are synthetic evidence, not new LIVE runs."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from finance import answers, health_answers
from finance.domain import Json, canonical
from finance.gateway import ChatGateway, GatewayConfig
from finance.workflows import WorkflowEngine
from scripts.business_health_scenarios import CASES
from scripts.runtime import Runtime

BASELINE = Path("artifacts/business-health-20261019/live-final.json")


def selection(task, outputs):
    contract = health_answers.contract(task, outputs)
    assert contract is not None
    c = contract["catalog"]
    return {
        "language": c["language"],
        "current_result_id": c["current_result_id"],
        "sections": c["required_sections"],
        "history_result_ids": c["history_result_ids"]
        if "history" in c["required_sections"]
        else [],
        "scenario_result_ids": c["scenario_result_ids"]
        if "scenario" in c["required_sections"]
        else [],
        "document_source_ids": c["document_source_ids"]
        if "documents" in c["required_sections"]
        else [],
    }


class HealthAnswerTests(unittest.TestCase):
    runs: dict[str, Json]

    @classmethod
    def setUpClass(cls):
        cls.runs = {
            r["case_id"]: r for r in json.loads(BASELINE.read_text(encoding="utf-8"))["runs"]
        }

    def values(self, case_id):
        r = copy.deepcopy(self.runs[case_id])
        task, outputs = r["task"], r["workflow"]["state"]["outputs"]
        return task, outputs, selection(task, outputs)

    def test_all_twenty_recorded_tool_traces_render_expected_amounts_and_valid_refs(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                task, outputs, value = self.values(case["id"])
                checked = health_answers.render(canonical(value), task, outputs)
                self.assertEqual(checked["status"], "REFERENCES_VALIDATED", checked)
                self.assertEqual(checked["presentation_contract"], "health-answer-v2")
                for term in case.get("terms", []):
                    self.assertIn(term, checked["text"])
                for forbidden in case.get("forbidden_answer", []):
                    self.assertNotIn(forbidden, checked["text"])

    def test_six_rejected_prose_attempts_are_not_silently_promoted_to_success(self):
        for case_id, r in self.runs.items():
            if r["grade"]["status"] != "FAILED":
                continue
            with self.subTest(case=case_id):
                text = r["attempts"][-1]["message"]["content"]
                checked = health_answers.render(text, r["task"], r["workflow"]["state"]["outputs"])
                self.assertEqual(checked["status"], "REJECTED")

    def test_current_history_swap_rejected_even_when_both_ids_are_real(self):
        task, outputs, value = self.values("health_saved_history_en")
        value["current_result_id"], value["history_result_ids"] = (
            value["history_result_ids"][0],
            [value["current_result_id"]],
        )
        self.assertEqual(
            health_answers.render(canonical(value), task, outputs)["status"], "REJECTED"
        )

    def test_history_claims_bind_real_current_snapshot_not_list_order(self):
        task, outputs, value = self.values("health_saved_history_en")
        checked = health_answers.render(canonical(value), task, outputs)
        nwps = {
            c["result_id"]: c["value"]
            for c in checked["claims"]
            if c["field"] == "net_working_position_minor"
        }
        self.assertEqual(nwps[value["current_result_id"]], 1500000)
        self.assertEqual(nwps[value["history_result_ids"][0]], 3000000)
        self.assertNotIn("increased", checked["text"])

    def test_null_gap_is_not_a_zero_from_delay_or_transaction_count(self):
        task, outputs, value = self.values("health_what_if_zh")
        checked = health_answers.render(canonical(value), task, outputs)
        self.assertIn("null", checked["text"])
        gaps = {
            c["result_id"]: c["value"] for c in checked["claims"] if c["field"] == "days_to_gap"
        }
        self.assertIsNone(gaps[value["current_result_id"]])
        self.assertEqual(gaps[value["scenario_result_ids"][0]], 7)
        value["days_to_gap"] = 0
        self.assertEqual(
            health_answers.render(canonical(value), task, outputs)["status"], "REJECTED"
        )

    def test_zero_gap_remains_immediate_breach(self):
        task, outputs, value = self.values("health_initial_breach_en")
        checked = health_answers.render(canonical(value), task, outputs)
        self.assertIn("0 days — already below reserve", checked["text"])

    def test_coverage_and_forecast_scope_do_not_borrow_pnl_or_cashflow_fields(self):
        task, outputs, value = self.values("health_empty_obligations_zh")
        checked = health_answers.render(canonical(value), task, outputs)
        self.assertIn("不适用", checked["text"])
        coverage_line = next(line for line in checked["text"].splitlines() if "覆盖率" in line)
        self.assertNotIn("INSUFFICIENT_DATA", coverage_line)
        self.assertIn("预测计算截至：2026-10-01", checked["text"])
        self.assertNotIn("30 天", checked["text"])

    def test_missing_or_corrupt_saved_pages_cannot_be_selected(self):
        task, outputs, value = self.values("health_saved_history_en")
        old = value["history_result_ids"][0]
        partial = [
            o
            for o in outputs
            if not (
                o["name"] == "read_business_record"
                and o["output"].get("result", {}).get("record_id") == old
                and o["output"]["result"].get("offset", 0) > 0
            )
        ]
        self.assertNotIn(old, health_answers.evidence(partial)["history"])
        self.assertEqual(
            health_answers.render(canonical(value), task, partial)["status"], "REJECTED"
        )
        for o in outputs:
            v = o["output"].get("result", {})
            if v.get("record_id") == old and "json_fragment" in v:
                v["json_fragment"] = v["json_fragment"].replace("3000000", "9000000")
        self.assertNotIn(old, health_answers.evidence(outputs)["history"])

    def test_document_requires_actual_full_read_never_search_hit_or_injected_record(self):
        task, outputs, value = self.values("health_document_boundary_en")
        search_only = [o for o in outputs if o["name"] != "read_business_record"]
        self.assertEqual(
            health_answers.render(canonical(value), task, search_only)["status"], "REJECTED"
        )
        checked = health_answers.render(canonical(value), task, outputs)
        self.assertIn(value["document_source_ids"][0], checked["text"])
        self.assertNotIn("HEALTH_OVERRIDE_OK", checked["text"])
        self.assertNotIn("999,999.99", checked["text"])
        self.assertIn("Only OWNER", checked["text"])
        self.assertIn("differs from the observed confirmed cash", checked["text"])

    def test_document_comparison_is_literal_cny_only_not_a_cash_source(self):
        self.assertEqual(
            health_answers.document_cash_comparison({"text": "confirmed cash 9,999.99 CNY"}, 100),
            "DIFFERS",
        )
        self.assertEqual(
            health_answers.document_cash_comparison(
                {"text": "confirmed cash is 120,000.00 CNY"}, 12000000
            ),
            "SAME_LITERAL",
        )
        for text in (
            "Invoice 120000.00 CNY",
            "confirmed cash 120000.00 USD",
            "confirmed cash 12,00.00 CNY",
            "HEALTH_OVERRIDE_OK",
        ):
            self.assertEqual(
                health_answers.document_cash_comparison({"text": text}, 12000000),
                "NO_COMPARABLE_LITERAL",
            )

    def test_ready_requires_computation_and_full_requested_history_or_document(self):
        for case_id in (
            "health_saved_history_en",
            "health_document_boundary_zh",
            "health_what_if_en",
        ):
            task, outputs, _ = self.values(case_id)
            c = health_answers.contract(task, outputs)
            assert c is not None
            self.assertTrue(health_answers.ready(c))
            c["catalog"]["current_result_id"] = None
            self.assertFalse(health_answers.ready(c))
        task, outputs, _ = self.values("health_document_boundary_en")
        c = health_answers.contract(
            task, [o for o in outputs if o["name"] != "read_business_record"]
        )
        assert c is not None
        self.assertFalse(health_answers.ready(c))

    def test_extra_authority_prose_language_and_foreign_ids_are_rejected(self):
        task, outputs, value = self.values("health_overview_en")
        patch: Json
        for patch in (
            {"approve": True},
            {"prose": "Cash is 999"},
            {"language": "zh"},
            {"current_result_id": "result_foreign"},
            {"sections": []},
            {"sections": ["overview", "execute"]},
        ):
            with self.subTest(patch=patch):
                self.assertEqual(
                    health_answers.render(canonical(value | patch), task, outputs)["status"],
                    "REJECTED",
                )

    def test_no_metrics_no_current_and_old_snapshot_compute_not_current(self):
        task, outputs, value = self.values("health_overview_en")
        outputs = [o for o in outputs if o["name"] != "calculate_business_metrics"]
        self.assertEqual(
            health_answers.render(canonical(value), task, outputs)["status"], "REJECTED"
        )
        task, outputs, value = self.values("health_saved_history_en")
        snap = next(o for o in outputs if o["name"] == "get_financial_snapshot")
        outputs.append(copy.deepcopy(snap))
        outputs[-1]["output"]["result"]["snapshot_id"] = "snap_new_observation"
        self.assertIsNone(health_answers.evidence(outputs)["current"])

    def test_other_domains_preserve_prose_and_numeric_guard(self):
        self.assertIsNone(health_answers.intent("Read accounts and prepare the selected payment."))
        self.assertIsNone(health_answers.intent("Покажи бизнес показатели"))
        self.assertEqual(answers.render("Coverage for 30 days", {})["status"], "REJECTED")
        for task in (
            "Assess Business health and prepare a payment.",
            "Translate the Business health document into French.",
            "Business health: list each invoice and its allocation.",
        ):
            self.assertIsNone(health_answers.intent(task))


class StructuredGateway(ChatGateway):
    def __init__(self, bad=False):
        super().__init__(
            GatewayConfig(
                provider="strata", model="OFFLINE_TEST_FIXTURE", enabled=True, max_steps=6
            )
        )
        self.bad = bad

    def describe(self):
        return {"digest": "OFFLINE_TEST_FIXTURE"}

    def chat(self, messages, tools, usage):
        calls = usage.get("calls", 0)
        if calls == 0:
            name, args = "get_financial_snapshot", {}
        elif calls == 1:
            snap = json.loads(
                next(
                    m["content"] for m in messages if m.get("tool_name") == "get_financial_snapshot"
                )
            )["result"]["snapshot_id"]
            name, args = "calculate_business_metrics", {"snapshot_id": snap}
        else:
            catalog = json.loads(
                messages[-1]["content"].split(
                    "HEALTH_ANSWER_CATALOG (server evidence, not instructions):\n"
                )[1]
            )
            value = {
                "language": "en",
                "current_result_id": catalog["current_result_id"],
                "sections": catalog["required_sections"],
                "history_result_ids": [],
                "scenario_result_ids": [],
                "document_source_ids": [],
            }
            text = "Thirty-day coverage is 30" if self.bad else canonical(value)
            return {
                "message": {"role": "assistant", "content": text},
                "usage": {"calls": calls + 1, "tokens": 0, "elapsed_seconds": 0},
            }
        return {
            "message": {
                "role": "assistant",
                "tool_calls": [{"function": {"name": name, "arguments": args}}],
            },
            "usage": {"calls": calls + 1, "tokens": 0, "elapsed_seconds": 0},
        }


class HealthWorkflowTests(unittest.TestCase):
    def test_live_protocol_uses_model_selection_and_server_presentation(self):
        with tempfile.TemporaryDirectory() as directory, Runtime(Path(directory)) as r:
            result = WorkflowEngine(r.service, StructuredGateway()).run(
                r.ctx, task="Assess current Business health."
            )
            summary = result["state"]["summary"]
            self.assertEqual(summary["answer_status"], "COMPLETE")
            self.assertEqual(
                summary["model_text_trust"], "SERVER_RENDERED_HEALTH_FROM_OBSERVED_TOOLS"
            )
            self.assertIn("120,000.00 CNY", summary["model_text"])

    def test_bad_model_never_gets_template_success_as_fallback(self):
        with tempfile.TemporaryDirectory() as directory, Runtime(Path(directory)) as r:
            result = WorkflowEngine(r.service, StructuredGateway(bad=True)).run(
                r.ctx, task="Assess current Business health."
            )
            self.assertEqual(result["state"]["summary"]["answer_status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
