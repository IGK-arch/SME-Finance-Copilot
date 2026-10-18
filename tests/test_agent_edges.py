"""Fixture and oracle integrity for the 26 new cases; not LIVE model results."""

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from finance.agent_data import records
from finance.agents import ToolRegistry
from finance.ingestion import snapshot
from finance.workflows import tool_schemas
from scripts.agent_edge_scenarios import CASES, setup
from scripts.agent_eval import grade
from scripts.agent_language_profile import localize
from scripts.agent_scenarios import CASES as LEGACY
from scripts.live_compare import PLATFORM_CASES, EXPLORATORY_CASES
from scripts.runtime import Runtime


class EdgeTests(unittest.TestCase):
    def test_exactly_100_distinct_english_chinese_cases(self):
        legacy = localize(LEGACY + PLATFORM_CASES + EXPLORATORY_CASES)
        self.assertEqual(len(CASES), 26)
        self.assertEqual(len({c["id"] for c in legacy + CASES}), 100)
        self.assertEqual(Counter(c["language"] for c in legacy + CASES), {"en": 67, "zh": 33})
        allowed = {s["function"]["name"] for s in tool_schemas()}
        for c in CASES:
            self.assertTrue(set(c.get("tools", [])) <= allowed, c["id"])
            self.assertNotRegex(c["task"].replace("А", ""), r"[А-Яа-яЁё]")
            self.assertTrue(c["review_rubric"])

    def test_each_fixture_builds_and_has_required_evidence(self):
        for c in CASES:
            with self.subTest(case=c["id"]), tempfile.TemporaryDirectory() as folder:
                with Runtime(Path(folder), cash_minor=c.get("cash_minor", 12000000)) as r:
                    oracle = setup(r, c)
                    self.assertEqual(oracle["task"], c["task"])
                    self.assertTrue(oracle["case_definition_hash"])
                    self.assertTrue(set(c.get("citations", [])) <= oracle["sources"].keys())
                    if c.get("special") == "future_balance":
                        self.assertEqual(snapshot(r.store, r.ctx)["confirmed_cash_minor"], 12000000)
                        self.assertFalse(
                            any(x.get("version") == 2 for x in records(r.service, r.ctx, "facts"))
                        )
                        with r.store.connect() as db:
                            self.assertEqual(
                                db.execute("SELECT COUNT(*) FROM facts WHERE version=2").fetchone()[
                                    0
                                ],
                                1,
                            )
                    if c.get("special") == "decimal_minor":
                        review = records(r.service, r.ctx, "reviews")
                        self.assertTrue(review)
                        self.assertIn("123.45", str(review))
                    if c.get("special") == "stopped":
                        self.assertTrue(r.store.company(r.ctx)["stopped"])
                    if c.get("special") == "expired_approval":
                        self.assertTrue(
                            all(
                                a["expires_at"].startswith("2000-")
                                for a in records(r.service, r.ctx, "approvals")
                            )
                        )
                    if c.get("role"):
                        self.assertEqual(r.ctx.role, c["role"])

    def test_answer_catalog_omission_and_literal_space_are_real_failures(self):
        catalogue = next(c for c in CASES if c["id"] == "edge_catalog_complete_answer_en")
        run = {
            "phase": "COMPLETE",
            "events": [],
            "state": {
                "outputs": [],
                "summary": {
                    "model_text": "24 " + " ".join(f"BATCHDOC-{i:02d}" for i in range(23)),
                    "answer_validation": {"status": "REFERENCES_VALIDATED"},
                },
            },
        }
        result = grade(
            catalogue, run, [{"status": "OK"}], {}, {"sources": {}, "page_ids": []}, False
        )
        self.assertFalse(result["checks"]["expected_answer_literals"])
        literal = next(c for c in CASES if c["id"] == "edge_literal_space_zh")
        run["events"] = [
            {
                "node": "tool",
                "payload": {
                    "name": "list_business_records",
                    "arguments": {
                        "dataset": "obligations",
                        "query": "supplier' OR 1=1 --",
                        "offset": 0,
                    },
                    "output": {"status": "OK"},
                },
            }
        ]
        result = grade(literal, run, [{"status": "OK"}], {}, {"sources": {}}, False)
        self.assertFalse(result["checks"]["exact_requested_arguments"])
        run["events"][0]["payload"]["arguments"]["query"] += " "
        self.assertTrue(
            grade(literal, run, [{"status": "OK"}], {}, {"sources": {}}, False)["checks"][
                "exact_requested_arguments"
            ]
        )

    def test_kill_switch_fixture_is_readable_and_does_not_rewrite_unknown(self):
        c = next(c for c in CASES if c.get("special") == "stopped")
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            oracle = setup(r, c)
            action_id = oracle["setup_operations"][0]["action_id"]
            result = ToolRegistry(r.service, r.ctx).call(
                "get_action_status", {"action_id": action_id}
            )
            self.assertEqual(result["status"], "OK")
            self.assertEqual(result["result"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
