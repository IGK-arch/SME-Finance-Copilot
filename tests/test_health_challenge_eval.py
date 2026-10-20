"""Fixture and strict-grader checks; no model calls."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from finance.agents import ToolRegistry
from finance.domain import canonical
from finance.ingestion import snapshot
from scripts.business_health_eval import fields_match
from scripts.business_health_scenarios import CASES as OLD_CASES
from scripts.health_challenge_eval import challenge_grade
from scripts.health_challenge_scenarios import CASES, setup
from scripts.runtime import Runtime


class HealthChallengeTests(unittest.TestCase):
    def test_twenty_new_prompts_ten_matched_pairs(self) -> None:
        self.assertEqual(len(CASES), 20)
        self.assertEqual(len({c["id"] for c in CASES}), 20)
        self.assertFalse({c["task"] for c in CASES} & {c["task"] for c in OLD_CASES})
        for en, zh in zip(CASES[::2], CASES[1::2]):
            self.assertEqual((en["language"], zh["language"]), ("en", "zh"))
            self.assertEqual(
                {k: v for k, v in en.items() if k not in {"id", "task", "language"}},
                {k: v for k, v in zh.items() if k not in {"id", "task", "language"}},
            )
            self.assertTrue(en["manual_rubric"])

    def test_ten_fixtures_match_frozen_expectations_and_restricted_doc_is_hidden(self) -> None:
        for case in CASES[::2]:
            with (
                self.subTest(case=case["id"]),
                tempfile.TemporaryDirectory() as folder,
                Runtime(Path(folder), cash_minor=case.get("cash_minor", 12000000)) as r,
            ):
                oracle = setup(r, case)
                registry = ToolRegistry(r.service, r.ctx)
                snap = snapshot(r.store, r.ctx)
                result = registry.call(
                    "calculate_business_metrics", {"snapshot_id": snap["snapshot_id"]}
                )
                self.assertEqual(result["status"], "OK")
                self.assertTrue(
                    fields_match(result["result"]["business_health"], case["health_expected"])
                )
                if case.get("extra_fixture") == "restricted_document":
                    found = registry.call(
                        "search_documents", {"query": "OWNER-HEALTH-CONFIDENTIAL"}
                    )
                    self.assertEqual(found["status"], "OK")
                    self.assertEqual(found["result"]["hits"], [])
                    self.assertNotIn(oracle["hidden"][0], canonical(found))
                for call in case.get("required_calls", []):
                    scenario = registry.call(
                        call["name"], {"snapshot_id": snap["snapshot_id"], **call["arguments"]}
                    )
                    self.assertEqual(scenario["status"], "OK")
                    health = scenario["result"]["forecast"]["business_health"]
                    self.assertEqual(health["net_working_position_minor"], 3000000)

    def test_old_success_does_not_satisfy_new_detail_request(self) -> None:
        old = json.loads(
            Path("artifacts/business-health-fix-20261019/live-health-final.json").read_text(
                encoding="utf-8"
            )
        )
        old_case = next(r for r in old["runs"] if r["case_id"] == "health_aging_en")
        case = next(c for c in CASES if c["id"] == "healthx_aging_detail_en")
        grade = challenge_grade(
            case,
            old_case["workflow"],
            old_case["attempts"],
            old_case["grade"]["safety"],
            old_case["oracle"],
        )
        self.assertEqual(grade["status"], "FAILED")
        self.assertFalse(grade["checks"]["each_requested_record_fully_read"])
        self.assertFalse(grade["checks"]["required_record_details"])

    def test_single_scenario_does_not_count_as_two(self) -> None:
        old = json.loads(
            Path("artifacts/business-health-fix-20261019/live-health-final.json").read_text(
                encoding="utf-8"
            )
        )
        old_case = next(r for r in old["runs"] if r["case_id"] == "health_what_if_en")
        case = copy.deepcopy(next(c for c in CASES if c["id"] == "healthx_two_shocks_en"))
        grade = challenge_grade(
            case,
            old_case["workflow"],
            old_case["attempts"],
            old_case["grade"]["safety"],
            old_case["oracle"],
        )
        self.assertFalse(grade["checks"]["each_requested_call"])
        self.assertFalse(grade["checks"]["each_scenario_cited"])
        self.assertEqual(grade["status"], "FAILED")

    def test_empty_or_failed_run_never_passes(self) -> None:
        for case in CASES:
            oracle = {"sources": {k: "source_missing" for k in case.get("citations", [])}}
            self.assertEqual(challenge_grade(case, None, [], {}, oracle)["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
