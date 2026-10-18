import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finance.asgi import make_app
from scripts.runtime import Runtime


class AsgiTests(unittest.TestCase):
    def test_fastapi_real_domain_routes_and_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            with TestClient(make_app(r.service), base_url="http://127.0.0.1:8080") as client:
                self.assertEqual(client.get("/v1/dashboard").status_code, 401)
                headers = {"Authorization": "Bearer " + r.tokens["OWNER"]}
                for endpoint in (
                    "dashboard",
                    "settings",
                    "imports",
                    "financing",
                    "workflows",
                    "reports",
                    "approvals",
                ):
                    response = client.get("/v1/" + endpoint, headers=headers)
                    self.assertEqual(response.status_code, 200, response.text)
                denied = client.post(
                    "/v1/settings", json={"reserve_minor": True, "protected": []}, headers=headers
                )
                self.assertEqual(denied.status_code, 400)
                self.assertEqual(
                    client.post(
                        "/v1/plans", json={"tenant_id": "another"}, headers=headers
                    ).status_code,
                    403,
                )
                plan = client.post("/v1/plans", json={}, headers=headers).json()["result"]
                self.assertIn("ortools", plan["solver_version"])
                self.assertEqual(plan["plan"]["quote"]["principal_minor"], 9100000)
