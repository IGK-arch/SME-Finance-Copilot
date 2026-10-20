"""Preflight validation of new fixtures and completeness criteria; no model calls."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finance.agents import ToolRegistry
from finance.domain import canonical
from scripts.agent_edge_scenarios import setup as edge_setup
from scripts.agent_eval import grade
from scripts.business_health_eval import fields_match
from scripts.health_challenge_scenarios import CASES as OLD_HEALTH, setup as health_setup
from scripts.release_challenge_scenarios import CASES
from scripts.release_eval import main, save, suite
from scripts.runtime import Runtime


class ReleaseEvalTests(unittest.TestCase):
    def test_reasoning_must_be_explicit(self) -> None:
        errors = io.StringIO()
        with (
            patch("sys.argv", ["release_eval", "--prepare", "--preregistration", "unused"]),
            contextlib.redirect_stderr(errors),
            self.assertRaises(SystemExit) as caught,
        ):
            main()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--reasoning", errors.getvalue())

    def test_prepare_medium_changes_only_reasoning_not_budget_or_cases(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            root = Path(folder)
            connection = root / "synthetic.json"
            connection.write_text('{"bridge_token":"synthetic-token","local_port":18443}')
            prepared = {}
            for effort in ("none", "medium"):
                target = root / (effort + ".json")
                with (
                    patch(
                        "sys.argv",
                        [
                            "release_eval",
                            "--prepare",
                            "--reasoning",
                            effort,
                            "--connection",
                            str(connection),
                            "--preregistration",
                            str(target),
                        ],
                    ),
                    patch("scripts.release_eval.ChatGateway", side_effect=AssertionError),
                ):
                    main()
                serialized = target.read_text(encoding="utf-8")
                self.assertNotIn("synthetic-token", serialized)
                prepared[effort] = json.loads(serialized)
            first, second = prepared["none"], prepared["medium"]
            for key in ("entries", "source_hashes", "system_hash", "tools_hash"):
                self.assertEqual(first[key], second[key])
            a, b = first["configuration"], second["configuration"]
            self.assertEqual(b["strata_reasoning_effort"], "medium")
            self.assertTrue(b["think"])
            self.assertEqual(
                {key for key in a if a[key] != b[key]}, {"think", "strata_reasoning_effort"}
            )

    def test_checkpoint_retries_temporary_windows_file_lock(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "checkpoint.json"
            real_replace = Path.replace
            calls = []

            def replace(source, destination):
                calls.append(source)
                if len(calls) == 1:
                    raise PermissionError("simulated transient reader lock")
                return real_replace(source, destination)

            with patch.object(Path, "replace", replace), patch("scripts.release_eval.time.sleep"):
                save(target, {"runs": ["retained"]})
            self.assertIn("retained", target.read_text())
            self.assertEqual(len(calls), 2)

    def test_checkpoint_does_not_hide_persistent_storage_failure(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "checkpoint.json"
            target.write_text("original")
            with (
                patch.object(Path, "replace", side_effect=PermissionError("persistent")) as replace,
                patch("scripts.release_eval.time.sleep"),
            ):
                with self.assertRaises(PermissionError):
                    save(target, {"runs": ["new"]})
            self.assertEqual(replace.call_count, 10)
            self.assertEqual(target.read_text(), "original")

    def test_new_prompts_balanced_unique_and_separate(self) -> None:
        entries = suite()
        self.assertEqual(len(entries), 120)
        self.assertEqual(len({e["case"]["id"] for e in entries}), 120)
        old = [e["case"] for e in entries if e["group"] == "regression100"]
        self.assertEqual(len(old), 100)
        self.assertFalse({c["task"] for c in CASES} & {c["task"] for c in old + OLD_HEALTH})
        self.assertEqual(sum(c["language"] == "en" for c in CASES), 10)
        self.assertEqual(sum(c["language"] == "zh" for c in CASES), 10)
        for en, zh in zip(CASES[::2], CASES[1::2]):
            ignored = {"id", "task", "language"}
            self.assertEqual(
                {k: v for k, v in en.items() if k not in ignored},
                {k: v for k, v in zh.items() if k not in ignored},
            )

    def test_fixtures_have_observable_expected_evidence(self) -> None:
        for case in CASES[::2]:
            with (
                self.subTest(case=case["id"]),
                tempfile.TemporaryDirectory() as folder,
                Runtime(Path(folder)) as runtime,
            ):
                oracle = (health_setup if case["evaluator"] == "health" else edge_setup)(
                    runtime, case
                )
                self.assertEqual(oracle["task"], case["task"])
                self.assertTrue(set(case.get("citations", [])) <= set(oracle["sources"]))
                registry = ToolRegistry(runtime.service, runtime.ctx)
                if case["evaluator"] == "health":
                    snap = registry.call("get_financial_snapshot", {})["result"]
                    metrics = registry.call(
                        "calculate_business_metrics", {"snapshot_id": snap["snapshot_id"]}
                    )
                    self.assertTrue(
                        fields_match(metrics["result"]["business_health"], case["health_expected"])
                    )
                for dataset in case.get("datasets", []):
                    result = registry.call(
                        "list_business_records", {"dataset": dataset, "query": "", "offset": 0}
                    )
                    self.assertEqual(result["status"], "OK")
                for _, title, _ in case.get("documents", []):
                    result = registry.call("search_documents", {"query": title})
                    self.assertEqual(result["status"], "OK")
                    self.assertTrue(result["result"]["hits"])
                if case.get("operation") == "UNKNOWN":
                    result = registry.call(
                        "list_business_records", {"dataset": "actions", "query": "", "offset": 0}
                    )
                    self.assertIn("UNKNOWN", canonical(result))

    def test_empty_answers_fail_even_with_all_safety_true(self) -> None:
        for case in CASES:
            oracle = {
                "sources": {key: "source_missing" for key in case.get("citations", [])},
                "hidden": [],
            }
            result = grade(case, None, [], {"financial_records_unchanged": True}, oracle, False)
            self.assertEqual(result["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
