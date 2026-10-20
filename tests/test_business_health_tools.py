"""Business health through the actual read/compute/projection boundaries."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from finance import answers, cases
from finance.agent_data import read_record
from finance.agents import ToolRegistry
from finance.compute import analysis, business_health, forecast
from finance.contracts import schema_check
from finance.copilot import _card
from finance.domain import FinanceError, canonical
from finance.ingestion import import_csv, snapshot
from finance.workflows import call_model_tool, model_result
from scripts.agent_scenarios import financial_state
from scripts.runtime import ORIGIN, PROFILE, Runtime, csv_bytes, golden_rows


class BusinessHealthToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temp.name))
        self.registry = ToolRegistry(self.runtime.service, self.runtime.ctx)
        self.snap = snapshot(self.runtime.store, self.runtime.ctx)

    def tearDown(self) -> None:
        self.runtime.close()
        self.temp.cleanup()

    def metrics(self) -> dict:
        result = self.registry.call(
            "calculate_business_metrics", {"snapshot_id": self.snap["snapshot_id"]}
        )
        self.assertEqual(result["status"], "OK")
        return result

    def test_tool_matches_cabinet_and_independent_known_values(self) -> None:
        before = financial_state(self.runtime)
        h = self.metrics()["result"]["business_health"]
        owner = cases.analysis_view(self.snap, forecast(self.snap), {})
        self.assertEqual(h["net_working_position_minor"], 3000000)
        self.assertEqual(h["liquidity_buffer_minor"], -9000000)
        self.assertEqual(h["days_to_gap"], 7)
        self.assertEqual(h["coverage_30d_bps"], 6315)
        self.assertEqual(h["net_working_position_minor"], owner["net_working_position"]["minor"])
        self.assertEqual(h["liquidity_buffer_minor"], owner["liquidity_buffer"]["minor"])
        self.assertEqual(h["evidence_refs"], self.snap["evidence_refs"])
        self.assertEqual(financial_state(self.runtime), before)
        schema_check(
            h, json.loads(Path("contracts/business-health.schema.json").read_text(encoding="utf-8"))
        )

    def test_money_and_percent_refs_are_exact_in_projection(self) -> None:
        view = model_result(self.metrics())
        h = view["result"]["business_health"]
        self.assertEqual(
            h["receivables_aging"][1]["display_cny"]["outstanding_minor"], "100,000.00 CNY"
        )
        refs = answers.references([view])
        values = {(v["kind"], v["value"]) for v in refs.values()}
        self.assertIn(("money", "100,000.00 CNY"), values)
        self.assertIn(("money", "-90,000.00 CNY"), values)
        self.assertIn(("percentage", "63.15%"), values)
        self.assertNotIn(("number", "10000000"), values)

    def test_model_projection_drops_only_redundant_metric_metadata(self) -> None:
        out = self.metrics()
        projected = model_result(out)
        raw = out["result"]["metrics"]["confirmed_cash_minor"]
        visible = projected["result"]["metrics"]["confirmed_cash_minor"]
        self.assertIn("metric_id", raw)
        self.assertNotIn("metric_id", visible)
        self.assertEqual(visible["value"], raw["value"])
        self.assertEqual(projected["evidence_refs"], out["evidence_refs"])
        self.assertEqual(projected["result"]["business_health"]["snapshot_id"], out["snapshot_id"])

    def test_forecast_and_hypothetical_health_have_explicit_scope(self) -> None:
        before = financial_state(self.runtime)
        current = self.metrics()["result"]["business_health"]
        fc = self.registry.call("forecast_cashflow", {"snapshot_id": self.snap["snapshot_id"]})
        self.assertEqual(
            model_result(fc)["result"]["business_health"],
            model_result(self.metrics())["result"]["business_health"],
        )
        what = self.registry.call(
            "what_if_cashflow",
            {"snapshot_id": self.snap["snapshot_id"], "delay_days": 7, "receipt_bps": 5000},
        )
        h = model_result(what)["result"]["forecast"]["business_health"]
        self.assertEqual(h["forecast_scope"]["scenario_id"], "user_what_if")
        self.assertEqual(h["forecast_scope"]["receipt_bps"], 5000)
        self.assertEqual(h["forecast_scope"]["delay_days"], 7)
        self.assertEqual(h["net_working_position_minor"], current["net_working_position_minor"])
        self.assertEqual(h["customer_concentration"]["total_minor"], 10000000)
        self.assertEqual(snapshot(self.runtime.store, self.runtime.ctx), self.snap)
        self.assertEqual(financial_state(self.runtime), before)

    def test_zero_denominator_empty_parties_and_no_gap_are_not_infinity(self) -> None:
        empty = copy.deepcopy(self.snap)
        empty["obligations"] = []
        h = business_health(empty)
        self.assertIsNone(h["coverage_30d_bps"])
        self.assertEqual(h["coverage_30d_status"], "NOT_APPLICABLE")
        self.assertIsNone(h["days_to_gap"])
        self.assertEqual(h["days_to_gap_status"], "NO_GAP_IN_FORECAST")
        self.assertIsNone(h["customer_concentration"]["top3_share_bps"])
        self.assertEqual(h["supplier_concentration"]["top"], [])

    def test_initial_breach_is_zero_days_not_missing(self) -> None:
        low = copy.deepcopy(self.snap)
        low["confirmed_cash_minor"] = -100
        h = business_health(low)
        self.assertEqual(h["days_to_gap"], 0)
        self.assertEqual(h["days_to_gap_status"], "PROJECTED_GAP")
        self.assertLess(h["coverage_30d_bps"], 0)
        self.assertLess(h["liquidity_buffer_minor"], 0)

    def test_saved_result_read_pagination_preserves_the_health_contract(self) -> None:
        out = self.metrics()
        pages, offset = [], 0
        while offset is not None:
            page = read_record(
                self.runtime.service, self.runtime.ctx, "calculations", out["result_id"], offset
            )
            if "record" in page:
                record = page["record"]
                break
            pages.append(page["json_fragment"])
            offset = page["next_offset"]
        else:
            record = json.loads("".join(pages))
        self.assertEqual(record["result"]["business_health"], out["result"]["business_health"])
        self.assertEqual(record["contract_version"], "agent-tools-v5")

    def test_historical_snapshot_is_not_replaced_by_updated_facts(self) -> None:
        original = self.metrics()
        import_csv(
            self.runtime.store,
            self.runtime.ctx,
            csv_bytes([golden_rows()[2] | {"version": 2, "amount_minor": 8500000}]),
            "synthetic_csv",
            ORIGIN,
        )
        fresh = snapshot(self.runtime.store, self.runtime.ctx)
        result = self.registry.call(
            "calculate_business_metrics", {"snapshot_id": fresh["snapshot_id"]}
        )
        self.assertEqual(result["result"]["business_health"]["net_working_position_minor"], 1500000)
        self.assertEqual(
            self.metrics()["result"]["business_health"]["net_working_position_minor"], 3000000
        )
        self.assertNotEqual(original["snapshot_id"], result["snapshot_id"])

    def test_foreign_snapshot_and_calculation_are_denied(self) -> None:
        out = self.metrics()
        tokens = self.runtime.store.create_company("other", PROFILE, ORIGIN)
        other = self.runtime.store.authenticate(tokens["OWNER"])
        registry = ToolRegistry(self.runtime.service, other)
        self.assertEqual(
            registry.call("calculate_business_metrics", {"snapshot_id": self.snap["snapshot_id"]})[
                "status"
            ],
            "ERROR",
        )
        with self.assertRaises(FinanceError):
            read_record(self.runtime.service, other, "calculations", out["result_id"], 0)

    def test_cached_health_reauthorizes_membership(self) -> None:
        self.metrics()
        with self.runtime.store.transaction() as db:
            db.execute(
                "UPDATE memberships SET active=0 WHERE tenant_id=? AND user_id=?",
                (self.runtime.ctx.tenant_id, self.runtime.ctx.user_id),
            )
        self.assertEqual(
            self.registry.call(
                "calculate_business_metrics", {"snapshot_id": self.snap["snapshot_id"]}
            )["status"],
            "ERROR",
        )

    def test_unobserved_snapshot_and_extra_authority_arguments_are_denied(self) -> None:
        out = call_model_tool(
            self.registry,
            "calculate_business_metrics",
            {"snapshot_id": self.snap["snapshot_id"]},
            [],
        )
        self.assertEqual(out["error"]["code"], "MODEL_TOOL_PREREQUISITE")
        for extra in ({"approve": True}, {"tenant_id": "other"}, {"window_days": 365}):
            self.assertEqual(
                self.registry.call(
                    "calculate_business_metrics", {"snapshot_id": self.snap["snapshot_id"], **extra}
                )["status"],
                "ERROR",
            )

    def test_capabilities_and_owner_card_expose_health_without_payment_authority(self) -> None:
        cap = self.registry.call("get_platform_capabilities", {})["result"]
        self.assertEqual(cap["business_health"]["tool"], "calculate_business_metrics")
        self.assertIn("Only OWNER", canonical(cap["human_controls"]))
        card = _card("calculate_business_metrics", {}, self.metrics())
        assert card is not None
        self.assertEqual(card["title"], "Business health")
        values = [r["value"]["display"] for r in card["rows"]]
        self.assertIn("−CNY 90,000.00", values)
        self.assertIn("63.15%", values)
        self.assertEqual(card["business_health"]["pnl"]["status"], "INSUFFICIENT_DATA")

    def test_concentration_aggregate_rounds_from_amounts_not_rounded_shares(self) -> None:
        snap = copy.deepcopy(self.snap)
        sample = snap["obligations"][0]
        snap["obligations"] = [
            sample | {"kind": "RECEIVABLE", "counterparty": str(n), "outstanding_minor": 1}
            for n in range(6)
        ]
        h = analysis(snap)
        c = h["customer_concentration"]
        self.assertEqual(c["top3_share_bps"], 5000)
        self.assertEqual(sum(t["share_bps"] for t in c["top"]), 4998)


if __name__ == "__main__":
    unittest.main()
