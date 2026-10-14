from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from finance.api import make_api
from finance.contracts import schema_check
from finance.domain import FinanceError
from scripts.runtime import Runtime


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temporary.name))
        self.server = make_api(self.runtime.service, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.runtime.close()
        self.temporary.cleanup()

    def request(
        self, path: str, value: dict | None = None, role: str = "OWNER"
    ) -> tuple[int, dict]:
        req = Request(
            self.url + path,
            data=json.dumps(value).encode() if value is not None else None,
            headers={
                "Authorization": "Bearer " + self.runtime.tokens[role],
                "Content-Type": "application/json",
            },
        )
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_T055_what_if_isolated(self) -> None:
        before = self.request("/v1/dashboard")[1]["result"]["snapshot"]
        plan = self.request("/v1/plans", {})[1]["result"]["plan"]
        code, result = self.request(
            "/v1/plans/" + plan["plan_id"] + "/what-if", {"receipt_delay_days": 25}
        )
        self.assertEqual(code, 200)
        self.assertEqual(result["result"]["result"]["solver_status"], "INFEASIBLE")
        after = self.request("/v1/dashboard")[1]["result"]["snapshot"]
        self.assertEqual(before, after)

    def test_T060_api_tenant_and_roles(self) -> None:
        code, result = self.request("/v1/plans", {"tenant_id": "other"})
        self.assertEqual(code, 403)
        code, result = self.request("/v1/plans", {}, "AUDITOR")
        self.assertEqual(code, 403)
        code, result = self.request("/v1/snapshots/missing_other_tenant")
        self.assertEqual(code, 404)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.url + "/v1/dashboard")
        self.assertEqual(raised.exception.code, 401)

    def test_T093_actual_expected_api_and_ui(self) -> None:
        value = self.request("/v1/dashboard")[1]["result"]
        self.assertEqual(value["snapshot"]["confirmed_cash_minor"], 12000000)
        self.assertEqual(value["forecast"]["scenarios"][0]["minimum_balance_minor"], -7000000)
        # v0.3: the cabinet is rendered by web/*.js; the honest labels must stay in the UI.
        ui = "".join(p.read_text(encoding="utf-8") for p in sorted(Path("web").glob("*.js")))
        self.assertIn("expected, not settled", ui)
        self.assertIn("keeps actual facts unchanged", ui)
        legacy = Path("web/legacy/index.html").read_text(encoding="utf-8")
        self.assertIn("What-if · keeps actual facts unchanged", legacy)

    def test_web_utf8_and_security_headers(self) -> None:
        with urlopen(self.url + "/") as response:
            html = response.read().decode("utf-8")
            self.assertIn('lang="en"', html)
            self.assertIn("SME Finance Copilot", html)
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        value = self.request("/v1/dashboard")[1]["result"]
        self.assertIn("苏州", value["snapshot"]["profile"]["name"])

    def test_api_full_golden(self) -> None:
        plan = self.request("/v1/plans", {})[1]["result"]["plan"]
        for action in plan["actions"]:
            from datetime import datetime
            from scripts.runtime import ORIGIN

            day = (datetime.fromisoformat(action["at"]) - datetime.fromisoformat(ORIGIN)).days
            self.runtime.advance(day)
            command = self.request(
                "/v1/plans/" + plan["plan_id"] + "/command", {"action_id": action["action_id"]}
            )[1]["result"]
            self.assertEqual(self.request("/v1/approvals", {"command": command})[0], 200)
            self.assertEqual(
                self.request(
                    "/v1/actions/" + action["action_id"] + "/dispatch", {"command": command}
                )[0],
                200,
            )
            self.runtime.settle()
            self.assertEqual(
                self.request("/v1/actions/" + action["action_id"])[1]["result"]["status"], "SETTLED"
            )
        self.assertEqual(
            self.request("/v1/dashboard")[1]["result"]["snapshot"]["confirmed_cash_minor"], 2800000
        )
        self.assertTrue(
            self.runtime.admin("/admin/evaluate", {"reserve_minor": 2000000})["success"]
        )

    def test_handoff_contracts(self) -> None:
        schema = json.loads(Path("contracts/payment-command.schema.json").read_text())
        example = json.loads(Path("contracts/payment-command.example.json").read_text())
        schema_check(example, schema)
        with self.assertRaises(FinanceError):
            schema_check(example | {"amount_minor": True}, schema)
        from finance.agents import ToolRegistry

        result = ToolRegistry(self.runtime.service, self.runtime.ctx).call(
            "get_financial_snapshot", {}
        )
        schema_check(result, json.loads(Path("contracts/tool-result.schema.json").read_text()))

    def test_payload_shape_fail_closed(self) -> None:
        self.assertEqual(self.request("/v1/approvals", {"command": {}})[0], 409)
        self.assertEqual(self.request("/v1/imports", {"csv": "", "provider": "csv"})[0], 409)
