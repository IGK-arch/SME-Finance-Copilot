"""Evidence-integrity and latency-denominator tests using fabricated fixtures only."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis.multimodel_report import collect, describe, durable_coverage, percentile, summarize


class MultimodelReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.frozen = {
            "cases": [
                {"id": f"c{i}", "language": "en", "task": "synthetic fixture"} for i in range(100)
            ]
        }
        self.write("frozen.json", self.frozen)
        self.manifest = {
            "frozen_case_artifact": "frozen.json",
            "frozen_case_artifact_sha256": hashlib.sha256(
                (self.root / "frozen.json").read_bytes()
            ).hexdigest(),
            "source_hashes": {},
            "download_plan": {"files": [{"sha256": f"pin{i}"} for i in range(5)]},
        }
        self.queue = {"models": [], "restore": "VERIFIED"}
        for i in range(5):
            runs = [
                {
                    "case_id": f"c{j}",
                    "task": "synthetic fixture",
                    "elapsed_seconds": 10.0,
                    "attempts": [],
                    "grade": {"status": "PASSED", "checks": {}, "safety": {"safe": True}},
                }
                for j in range(100)
            ]
            report = {
                "cases": self.frozen["cases"],
                "runs": runs,
                "source_hashes": {},
                "model_identity": {"weight_digest": f"pin{i}", "digest": f"identity{i}"},
                "configuration": {"model": f"m{i}", "output_tokens": 2048},
                "status": "COMPLETED",
            }
            self.write(f"m{i}.json", report)
            self.queue["models"].append(
                {"model": f"m{i}", "index": i + 1, "reports": [f"m{i}.json"]}
            )

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding="utf-8")

    def modify(self, name, fn):
        data = json.loads((self.root / name).read_bytes())
        fn(data)
        self.write(name, data)

    def build(self):
        return collect(self.root, self.queue, self.manifest, self.frozen)

    def test_complete_fixture_has_500_and_no_invented_usage(self):
        result = self.build()
        self.assertEqual(result["total"], 500)
        self.assertEqual(result["summary"]["m0"]["calls_with_usage"], 0)
        self.assertIsNone(result["summary"]["m0"]["passed_p50_seconds"])

    def test_missing_cases_block_before_any_quality_computation(self):
        self.modify("m4.json", lambda d: d.update(runs=d["runs"][:29]))
        with patch(
            "analysis.multimodel_report.describe", side_effect=AssertionError("must not analyze")
        ):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                self.build()

    def test_duplicate_primary_case_rejected(self):
        self.modify("m0.json", lambda d: d["runs"].append(d["runs"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.build()

    def test_changed_definition_rejected(self):
        self.modify("m0.json", lambda d: d["cases"][0].update(task="changed"))
        with self.assertRaisesRegex(ValueError, "definition"):
            self.build()

    def test_changed_source_rejected(self):
        self.modify("m0.json", lambda d: d.update(source_hashes={"finance/x.py": "changed"}))
        with self.assertRaisesRegex(ValueError, "Source freeze"):
            self.build()

    def test_changed_weight_rejected(self):
        self.modify("m0.json", lambda d: d["model_identity"].update(weight_digest="other"))
        with self.assertRaisesRegex(ValueError, "weight identity"):
            self.build()

    def test_different_budget_rejected(self):
        self.modify("m0.json", lambda d: d["configuration"].update(output_tokens=4096))
        with self.assertRaisesRegex(ValueError, "budgets"):
            self.build()

    def test_fast_failure_not_counted_as_fast_success(self):
        base = json.loads((self.root / "m0.json").read_bytes())["runs"][0]
        base["attempts"] = [
            {
                "elapsed_seconds": 1.0,
                "status": "OK",
                "provider_measurement": {
                    "metrics": {
                        "measurement_source": "LLAMACPP_RESPONSE_USAGE",
                        "prompt_eval_count": 8,
                        "eval_count": 2,
                    }
                },
            }
        ]
        fast = copy.deepcopy(base)
        fast.update(case_id="c1", elapsed_seconds=0.01)
        fast["grade"]["status"] = "FAILED"
        rows = [describe(r, self.frozen["cases"][i], "fixture") for i, r in enumerate([base, fast])]
        result = summarize(rows, [base, fast])
        self.assertEqual(result["grades"], {"PASSED": 1, "FAILED": 1})
        self.assertEqual(result["all_p50_seconds"], 0.01)
        self.assertEqual(result["passed_p50_seconds"], 10.0)

    def test_percentiles_do_not_invent_missing_observations(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile([1.0, 2.0, 100.0], 0.95), 100.0)

    def test_durable_evidence_survives_empty_terminal_state(self):
        run = {
            "case_id": "resumed",
            "grade": {},
            "workflow": {
                "state": {},
                "events": [
                    {"node": "clarification_answer", "payload": {}},
                    {
                        "node": "tool",
                        "payload": {
                            "name": "list_business_records",
                            "output": {"status": "OK", "result": {"dataset": "invoices"}},
                        },
                    },
                ],
            },
            "attempts": [
                {"status": "OK", "message": {"tool_calls": [{"function": {"name": "ask_user"}}]}}
            ],
        }
        result = durable_coverage([run])
        self.assertIn("ask_user", result["tools"])
        self.assertIn("invoices", result["datasets"])
        run["workflow"]["events"] = []
        self.assertNotIn("ask_user", durable_coverage([run])["tools"])


if __name__ == "__main__":
    unittest.main()
