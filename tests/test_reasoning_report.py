"""Comparison integrity: missing measurements and duplicate attempts stay explicit."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.reasoning_eval import configurations
from scripts.reasoning_report import combine, measurements, percentile


class ReasoningReportTests(unittest.TestCase):
    def test_mode_does_not_change_limits_or_tools(self):
        configs = configurations("fixture", 18443, ["none", "medium"])
        values = [
            {k: v for k, v in c.public().items() if k not in {"think", "strata_reasoning_effort"}}
            for c in configs.values()
        ]
        self.assertEqual(values[0], values[1])
        self.assertEqual(configs["medium"].output_tokens, 2048)
        self.assertEqual(configs["medium"].max_elapsed_seconds, 240)
        self.assertFalse(configs["none"].think)
        self.assertTrue(configs["medium"].think)

    def test_missing_usage_is_not_estimated_and_empty_percentile_is_null(self):
        result = measurements(
            {
                "elapsed_seconds": 2,
                "attempts": [
                    {
                        "status": "FAILED",
                        "elapsed_seconds": 1,
                        "provider_measurement": {"status": "NOT_SENT"},
                    }
                ],
            }
        )
        self.assertEqual(result["unmeasured_calls"], 1)
        self.assertIsNone(result["reasoning_tokens"])
        self.assertEqual(result["completion_tokens_known"], 0)
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile([5, 1, 3, 2, 4], 0.5), 3)
        measured = {
            "elapsed_seconds": 1,
            "provider_measurement": {
                "metrics": {
                    "measurement_source": "STRATA_RESPONSE_USAGE",
                    "prompt_eval_count": 10,
                    "eval_count": 4,
                    "reasoning_tokens": 3,
                }
            },
        }
        mixed = measurements({"elapsed_seconds": 2, "attempts": [measured, {"elapsed_seconds": 1}]})
        self.assertIsNone(mixed["reasoning_tokens"])
        self.assertEqual(mixed["unmeasured_calls"], 1)

    def test_duplicate_primary_outcome_is_rejected_and_partial_stays_partial(self):
        configs = configurations("fixture", 18443, ["none", "medium"])
        report = {
            "status": "COMPLETED",
            "configuration": configs["none"].public(),
            "cases": [{"id": "fixture"}],
            "source_hashes": {},
            "model_identity": {"model": "fixture"},
            "runs": [
                {
                    "case_id": "fixture",
                    "elapsed_seconds": 1,
                    "attempts": [],
                    "grade": {"status": "FAILED", "checks": {}, "safety": {}},
                    "workflow": None,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.json", Path(folder) / "b.json"
            a.write_text(json.dumps(report), encoding="utf-8")
            partial = combine([a])
            self.assertEqual(partial["status"], "PARTIAL")
            self.assertEqual(partial["missing"], [{"case_id": "fixture", "effort": "medium"}])
            b.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(ValueError):
                combine([a, b])
            report["configuration"] = configs["medium"].public()
            b.write_text(json.dumps(report), encoding="utf-8")
            paired = combine([a, b])
            self.assertTrue(paired["pairs"][0]["same_budget"])
            self.assertEqual(paired["pairs"][0]["category"], "fixture")
            self.assertEqual(paired["paired_summary"]["regressed"], [])
            self.assertEqual(paired["paired_summary"]["both_pass_count"], 0)

    def test_full_count_from_running_source_is_not_completed(self):
        configs = configurations("fixture", 18443, ["none", "medium"])
        report = {
            "status": "RUNNING",
            "configurations": {e: c.public() for e, c in configs.items()},
            "cases": [{"id": str(i), "category": "offline"} for i in range(100)],
            "source_hashes": {},
            "model_identity": {},
            "runs": [
                {
                    "case_id": str(i),
                    "reasoning_effort": effort,
                    "elapsed_seconds": 1,
                    "attempts": [],
                    "grade": {"status": "FAILED", "checks": {}, "safety": {}},
                    "workflow": None,
                }
                for i in range(100)
                for effort in ("none", "medium")
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "running.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(combine([path])["status"], "PARTIAL")
            report["status"] = "COMPLETED"
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(combine([path])["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
