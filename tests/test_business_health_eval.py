"""Check new fixtures and grader without making a model call."""

import copy
import tempfile
import unittest
from pathlib import Path

from finance.agents import ToolRegistry
from finance.ingestion import snapshot
from scripts.business_health_eval import fields_match, health_grade, language_matches
from scripts.business_health_scenarios import CASES, setup
from scripts.runtime import Runtime


class BusinessHealthEvalTests(unittest.TestCase):
    def test_pairs_have_identical_financial_requirements(self) -> None:
        self.assertEqual(len(CASES), 20)
        self.assertEqual(len({c["id"] for c in CASES}), 20)
        for en, zh in zip(CASES[::2], CASES[1::2]):
            self.assertEqual((en["language"], zh["language"]), ("en", "zh"))
            self.assertEqual(
                {k: v for k, v in en.items() if k not in {"id", "task", "language"}},
                {k: v for k, v in zh.items() if k not in {"id", "task", "language"}},
            )

    def test_all_fixtures_agree_with_preregistered_amounts(self) -> None:
        for case in CASES[::2]:
            with (
                self.subTest(case=case["id"]),
                tempfile.TemporaryDirectory() as folder,
                Runtime(Path(folder), cash_minor=case.get("cash_minor", 12000000)) as r,
            ):
                setup(r, case)
                snap = snapshot(r.store, r.ctx)
                registry = ToolRegistry(r.service, r.ctx)
                result = registry.call(
                    "calculate_business_metrics", {"snapshot_id": snap["snapshot_id"]}
                )
                self.assertEqual(result["status"], "OK")
                self.assertTrue(
                    fields_match(result["result"]["business_health"], case["health_expected"]),
                    case["id"],
                )
                if case.get("scenario_expected"):
                    what = registry.call(
                        "what_if_cashflow",
                        {"snapshot_id": snap["snapshot_id"], "delay_days": 7, "receipt_bps": 5000},
                    )
                    self.assertTrue(
                        fields_match(
                            what["result"]["forecast"]["business_health"], case["scenario_expected"]
                        )
                    )

    def test_grader_never_accepts_missing_health_or_noncompletion(self) -> None:
        case = copy.deepcopy(CASES[0])
        grade = health_grade(case, None, [], {}, {"sources": {}})
        self.assertEqual(grade["status"], "FAILED")
        self.assertFalse(grade["checks"]["health_contract"])
        self.assertFalse(fields_match({"days_to_gap": None}, {"days_to_gap": 0}))
        self.assertFalse(fields_match({"coverage": True}, {"coverage": 1}))

    def test_language_ignores_only_the_exact_observed_company_name(self) -> None:
        name = "苏州合成精密配件 · Synthetic B2B"
        outputs = [
            {
                "name": "get_financial_snapshot",
                "output": {"status": "OK", "result": {"profile": {"name": name}}},
            }
        ]
        english = name + " has observed cash and obligations with a projected reserve breach."
        self.assertTrue(language_matches(english, "en", outputs))
        self.assertFalse(language_matches(english, "en", []))
        self.assertFalse(language_matches(name, "zh", outputs))
        self.assertFalse(language_matches(english + "请注意这句话不是英语说明。", "en", outputs))
        self.assertTrue(language_matches("当前现金与未结债务的指标来自已观察数据。", "zh", outputs))


if __name__ == "__main__":
    unittest.main()
