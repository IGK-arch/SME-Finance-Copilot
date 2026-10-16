"""Language-profile integrity, not measured model quality."""

import copy
import unittest
from collections import Counter

from finance.answer_quality import requirements
from finance.domain import FinanceError
from scripts.agent_language_profile import localize
from scripts.agent_scenarios import CASES
from scripts.live_compare import PLATFORM_CASES, EXPLORATORY_CASES


class LanguageTests(unittest.TestCase):
    def test_all_74_prompts_and_clarifications_localized_without_changing_oracles(self):
        cases = CASES + PLATFORM_CASES + EXPLORATORY_CASES
        before = copy.deepcopy(cases)
        translated = localize(cases)
        self.assertEqual(len(translated), 74)
        self.assertEqual(Counter(c["language"] for c in translated), {"en": 54, "zh": 20})
        self.assertEqual(cases, before)
        for old, new in zip(cases, translated):
            with self.subTest(case=old["id"]):
                self.assertEqual(
                    {k: v for k, v in old.items() if k not in {"task", "answer"}},
                    {
                        k: v
                        for k, v in new.items()
                        if k
                        not in {
                            "task",
                            "answer",
                            "language",
                            "source_task_hash",
                            "source_answer_hash",
                        }
                    },
                )
                self.assertTrue(
                    new["task"].endswith("Answer in English.")
                    or new["task"].endswith("请用中文回答。")
                )
                if old.get("answer"):
                    self.assertNotEqual(old["answer"], new["answer"])
        company = next(c for c in translated if c["id"] == "company_access_records")
        self.assertEqual(
            set(requirements(company["task"])["datasets"]),
            {"company", "accounts", "beneficiaries", "memberships", "policies"},
        )
        history = next(c for c in translated if c["id"] == "history_current")
        self.assertEqual(set(requirements(history["task"])["datasets"]), {"facts", "obligations"})

    def test_unknown_case_fails_instead_of_silently_sending_source_language(self):
        with self.assertRaises(FinanceError):
            localize([{"id": "unknown", "task": "исходный текст"}])


if __name__ == "__main__":
    unittest.main()
