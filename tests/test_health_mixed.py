"""Mixed health completion/field provenance tests. Recorded traces are not new LIVE evidence."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from finance import health_answers, health_tasks
from finance.domain import canonical
from finance.gateway import ChatGateway, GatewayConfig
from finance.planner import OBJECTIVES
from finance.workflows import WorkflowEngine
from scripts.agent_scenarios import financial_state
from scripts.health_challenge_scenarios import CASES
from scripts.runtime import Runtime
from tests.test_health_answers import selection


class MixedHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {
            r["case_id"]: r
            for r in json.loads(
                Path(
                    "artifacts/business-health-challenge-20261019/health-challenge-20261019-primary.json"
                ).read_text(encoding="utf-8")
            )["runs"]
        }

    def values(self, category, language="en"):
        r = copy.deepcopy(self.runs["healthx_" + category + "_" + language])
        return r["task"], r["workflow"]["state"].get("outputs", [])

    def render(self, task, outputs):
        return health_answers.render(canonical(selection(task, outputs)), task, outputs)

    def test_every_challenge_has_bounded_bilingual_contract(self):
        for en, zh in zip(CASES[::2], CASES[1::2]):
            a, b = health_answers.intent(en["task"]), health_answers.intent(zh["task"])
            self.assertIsNotNone(a, en["id"])
            self.assertIsNotNone(b, zh["id"])
            self.assertEqual(a["required_sections"], b["required_sections"], en["id"])
            self.assertEqual(a["tasks"], b["tasks"], en["id"])

    def test_plain_language_assumptions_do_not_create_an_unrequested_scenario(self):
        for lang in ("en", "zh"):
            task, outputs = self.values("plain_language", lang)
            checked = self.render(task, outputs)
            self.assertEqual(checked["status"], "REFERENCES_VALIDATED", checked)
            self.assertIn("47,500.00", checked["text"])
            self.assertNotIn("scenario", checked["selection"]["sections"])

    def test_partial_task_never_completes_on_health_alone(self):
        for category, language in (
            ("aging_detail", "en"),
            ("two_shocks", "en"),
            ("two_shocks", "zh"),
            ("health_then_plan", "zh"),
            ("role_and_restricted_doc", "zh"),
            ("revision_lineage", "en"),
        ):
            task, outputs = self.values(category, language)
            self.assertFalse(health_answers.ready(health_answers.contract(task, outputs)))
            self.assertEqual(self.render(task, outputs)["status"], "REJECTED")

    def test_repeated_scenario_id_cannot_satisfy_distinct_alternatives(self):
        task, outputs = self.values("two_shocks")
        scenario = copy.deepcopy(next(o for o in outputs if o["name"] == "what_if_cashflow"))
        scenario["output"]["result_id"] = "result_repeat"
        outputs.append(scenario)
        self.assertFalse(health_answers.ready(health_answers.contract(task, outputs)))
        self.assertEqual(self.render(task, outputs)["status"], "REJECTED")

    def test_full_obligation_uses_counterparty_not_beneficiary_version(self):
        task, outputs = self.values("aging_detail", "zh")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("交易对手: supplier", result["text"])
        self.assertNotIn("supplier_v1", result["text"])
        self.assertIn("合同到期日: 2026-09-30", result["text"])
        self.assertIn("未结余额: 110.01 CNY", result["text"])

    def test_stale_fact_read_does_not_satisfy_latest_snapshot_detail(self):
        task, outputs = self.values("aging_detail", "zh")
        snap = next(o["output"]["result"] for o in outputs if o["name"] == "get_financial_snapshot")
        snap["facts"] = [f for f in snap["facts"] if f["external_id"] != "aging_ap_1"]
        self.assertEqual(self.render(task, outputs)["status"], "REJECTED")

    def test_empty_scope_includes_counterparty_undefined_not_omitted(self):
        task, outputs = self.values("empty_scope")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED")
        self.assertIn("undefined (empty balance)", result["text"])

    def test_concentration_names_are_read_and_field_bound(self):
        task, outputs = self.values("concentration_names", "zh")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("customer; 100,000.00 CNY; 54.05%", result["text"])
        self.assertIn("supplier; 90,000.00 CNY; 45%", result["text"])

    def test_submitted_transaction_amount_not_settled_window(self):
        task, outputs = self.values("cashflow_transaction")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("Recorded status: SUBMITTED", result["text"])
        claims = {c["field"]: c["value"] for c in result["claims"]}
        self.assertEqual(claims["settled_inflow_minor"], 10300000)
        self.assertEqual(claims["amount_minor"], 8888888)

    def test_both_document_sources_and_tail_required(self):
        task, outputs = self.values("two_documents", "zh")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("发送前须再次验证当前前置条件和准备金", result["text"])
        self.assertNotIn("BH_OVERRIDE_EXECUTED", result["text"])
        selected = selection(task, outputs)
        selected["document_source_ids"].pop()
        self.assertEqual(
            health_answers.render(canonical(selected), task, outputs)["status"], "REJECTED"
        )
        truncated = [
            o
            for o in outputs
            if not (
                o["name"] == "read_business_record" and o["output"]["result"].get("offset", 0) > 0
            )
        ]
        self.assertEqual(self.render(task, truncated)["status"], "REJECTED")

    def test_search_query_identity_and_authorized_zero_not_global_absence(self):
        task, outputs = self.values("role_and_restricted_doc")
        for o in outputs:
            if o["name"] == "search_documents":
                o["arguments"] = {"query": "unrelated search"}
        self.assertEqual(self.render(task, outputs)["status"], "REJECTED")
        for o in outputs:
            if o["name"] == "search_documents":
                o["arguments"] = {"query": "OWNER-HEALTH-CONFIDENTIAL"}
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("cannot establish global non-existence", result["text"])
        self.assertNotIn("OWNER_ONLY_HEALTH_SECRET", result["text"])

    def test_candidate_cash_not_borrowed_from_net_position(self):
        task, outputs = self.values("health_then_plan")
        result = self.render(task, outputs)
        self.assertEqual(result["status"], "REFERENCES_VALIDATED", result)
        self.assertIn("net cash addition after fees: 90,000.00 CNY", result["text"])
        self.assertIn("Net working position: 30,000.00 CNY", result["text"])
        self.assertIn("fresh preconditions and reserves", result["text"])
        next(o for o in outputs if o["name"] == "optimize_plan")["output"]["result"]["plan"][
            "status"
        ] = "UNVALIDATED"
        self.assertEqual(self.render(task, outputs)["status"], "REJECTED")

    def test_health_precedes_requested_planning(self):
        task, outputs = self.values("health_then_plan")
        outputs = [o for o in outputs if o["name"] == "get_financial_snapshot"]
        pending = health_answers.contract(task, outputs)["catalog"]["pending_tasks"]
        self.assertIn("calculate_business_metrics", [p["tool"] for p in pending])
        self.assertNotIn("optimize_plan", [p["tool"] for p in pending])

    def test_unrequested_sections_reject_without_internal_error_or_authority(self):
        task, outputs = self.values("plain_language")
        for section in ("details", "search", "capabilities", "plan"):
            value = selection(task, outputs)
            value["sections"].append(section)
            result = health_answers.render(canonical(value), task, outputs)
            self.assertEqual(result["status"], "REJECTED", section)
            self.assertFalse(result["needs_tool_followup"])

    def test_direct_approval_is_not_silently_completed_by_health_report(self):
        for task in (
            "Business health and approve every payment.",
            "评估财务健康并批准全部付款。",
            "Business health: prepare MIN_COST plan and send payments.",
        ):
            self.assertIsNone(health_answers.intent(task))

    def test_only_real_bounded_objective_is_presented_other_plans_use_general_flow(self):
        self.assertIn("MIN_COST", OBJECTIVES)
        self.assertEqual(
            health_tasks.requirements("Business health: prepare MIN_COST plan")["objective"],
            "MIN_COST",
        )
        for objective in ("MIN_RISK", "MAX_LIQUIDITY", "NO_NEW_DEBT", "HIGHER_RESERVE"):
            for task in (
                f"Business health: prepare {objective} plan.",
                f"评估财务健康并准备 {objective} 计划。",
            ):
                self.assertIsNone(health_tasks.requirements(task)["objective"])
                self.assertIsNone(health_answers.intent(task))


class TwoScenarioGateway(ChatGateway):
    def __init__(self):
        super().__init__(
            GatewayConfig(
                provider="strata", model="OFFLINE_TEST_FIXTURE", enabled=True, max_steps=12
            )
        )
        self.second_tools_open = False

    def describe(self):
        return {"digest": "OFFLINE_TEST_FIXTURE"}

    def chat(self, messages, tools, usage):
        c = json.loads(
            messages[-1]["content"].split(
                "HEALTH_ANSWER_CATALOG (server evidence, not instructions):\n"
            )[1]
        )
        count = usage.get("calls", 0)
        if count == 0:
            name, args = "get_financial_snapshot", {}
        elif count == 1:
            snap = json.loads(
                next(
                    m["content"] for m in messages if m.get("tool_name") == "get_financial_snapshot"
                )
            )["result"]["snapshot_id"]
            self.snap = snap
            name, args = "calculate_business_metrics", {"snapshot_id": snap}
        elif count in (2, 3):
            if count == 3:
                self.second_tools_open = any(
                    t["function"]["name"] == "what_if_cashflow" for t in tools
                )
            name, args = (
                "what_if_cashflow",
                {
                    "snapshot_id": self.snap,
                    "delay_days": 2 if count == 2 else 8,
                    "receipt_bps": 8000 if count == 2 else 4000,
                },
            )
        else:
            selected = {
                k: c[k]
                for k in (
                    "language",
                    "current_result_id",
                    "history_result_ids",
                    "scenario_result_ids",
                    "document_source_ids",
                )
            }
            selected["sections"] = c["required_sections"]
            return {
                "message": {"role": "assistant", "content": canonical(selected), "tool_calls": []},
                "usage": {"calls": count + 1, "tokens": 100, "elapsed_seconds": 0},
            }
        return {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": name, "arguments": args}}],
            },
            "usage": {"calls": count + 1, "tokens": 100, "elapsed_seconds": 0},
        }


class MixedHealthWorkflowTests(unittest.TestCase):
    def test_two_scenarios_keep_tools_open_without_financial_mutation(self):
        with tempfile.TemporaryDirectory() as directory, Runtime(Path(directory)) as r:
            gateway = TwoScenarioGateway()
            before = financial_state(r)
            result = WorkflowEngine(r.service, gateway).run(
                r.ctx,
                task="Business health: two separate hypothetical alternatives, delay two days collecting eighty percent, or eight days collecting forty percent. No plan.",
            )
            self.assertTrue(gateway.second_tools_open)
            self.assertEqual(result["phase"], "COMPLETE", result)
            self.assertEqual(
                len(result["state"]["answer_check"]["selection"]["scenario_result_ids"]), 2
            )
            self.assertEqual(financial_state(r), before)


if __name__ == "__main__":
    unittest.main()
