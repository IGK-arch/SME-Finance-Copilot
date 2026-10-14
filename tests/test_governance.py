from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from finance.compute import catalog, financing
from finance.domain import Config, FinanceError
from scripts.runtime import ORIGIN
from scripts.test import acceptance_status


class GovernanceTests(unittest.TestCase):
    def test_T099_honest_status_report(self) -> None:
        records = [
            {"acceptance_ids": ["T001"], "status": "PASSED", "test_id": "fixture.pass"},
            {"acceptance_ids": ["T002"], "status": "FAILED", "test_id": "fixture.fail"},
            {"acceptance_ids": ["T003"], "status": "SKIPPED", "test_id": "fixture.skip"},
        ]
        targets = [{"id": f"T{i:03}", "requirement": "Reporter unit fixture"} for i in range(1, 5)]
        statuses = [r["status"] for r in acceptance_status(records, targets)]
        self.assertEqual(statuses, ["PASSED", "FAILED", "SKIPPED", "NOT_RUN"])

    def test_T100_source_manifest_and_dependencies(self) -> None:
        sources = json.loads(Path("sources/manifest.json").read_text(encoding="utf-8"))
        for item in sources:
            content = Path(item["packaged_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), item["sha256"])
        lock = Path("requirements.lock").read_text(encoding="utf-8")
        dependencies = [
            line.strip().lstrip("\ufeff")
            for line in lock.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertTrue(dependencies)
        self.assertTrue(all("==" in line and ">=" not in line for line in dependencies))
        from importlib.metadata import version

        for line in dependencies:
            package, pinned = line.split("==")
            self.assertEqual(version(package), pinned)
        card = Path("docs/data_cards/synthetic.md").read_text(encoding="utf-8")
        self.assertIn("No external dataset", card)
        self.assertIn("UNKNOWN", card)
        preserved = json.loads(Path("docs/HANDOFF_INVENTORY.json").read_text(encoding="utf-8"))
        for path, expected_hash in preserved.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected_hash)

    def test_fail_closed_environment(self) -> None:
        for name, value in (
            ("ALLOW_REAL_FINANCIAL_ACTIONS", "true"),
            ("DATA_MODE", "consented_real"),
            ("EXECUTION_BACKEND", "bank"),
            ("MODEL_PROVIDER", "live"),
            ("ALLOW_UNAPPROVED_DATA_EGRESS", "true"),
        ):
            with patch.dict(os.environ, {name: value}):
                with self.assertRaises(FinanceError):
                    Config.from_environment()

    def test_unreviewed_product_not_published(self) -> None:
        product = catalog(ORIGIN)[0] | {"review_status": "UNVERIFIED_WEB_TEXT"}
        with self.assertRaises(FinanceError) as raised:
            financing(product, 9100000)
        self.assertEqual(raised.exception.code, "UNSUPPORTED_PRODUCT_TERMS")
