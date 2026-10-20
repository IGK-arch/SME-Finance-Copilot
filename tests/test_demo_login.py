"""Optional reviewer demo key on the sign-in page (SME_DEMO_LOGIN_ROLE)."""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finance.asgi import demo_login_role, make_app
from finance.domain import FinanceError
from scripts.runtime import Runtime

LOCAL = "http://127.0.0.1:8080"


class DemoLoginTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("SME_DEMO_LOGIN_ROLE", None)

    def test_role_must_be_a_human_role_and_never_admin(self) -> None:
        self.assertIsNone(demo_login_role())
        for good in ("OWNER", "ACCOUNTANT", "AUDITOR"):
            os.environ["SME_DEMO_LOGIN_ROLE"] = good
            self.assertEqual(demo_login_role(), good)
        for bad in ("ADMIN", "owner", "ROOT", "OWNER,ADMIN"):
            os.environ["SME_DEMO_LOGIN_ROLE"] = bad
            with self.assertRaises(FinanceError):
                demo_login_role()

    def test_off_by_default_and_on_returns_a_working_token(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            login_file = Path(folder) / "local-login.secret.json"
            client = TestClient(make_app(runtime.service, login_file=login_file), base_url=LOCAL)
            self.assertEqual(client.get("/session/demo").status_code, 404)

            os.environ["SME_DEMO_LOGIN_ROLE"] = "ADMIN"
            self.assertEqual(client.get("/session/demo").status_code, 404)

            os.environ["SME_DEMO_LOGIN_ROLE"] = "AUDITOR"
            shown = client.get("/session/demo")
            self.assertEqual(shown.status_code, 200)
            result = shown.json()["result"]
            self.assertEqual(result["role"], "AUDITOR")
            self.assertEqual(result["token"], runtime.tokens["AUDITOR"])
            signed = client.post(
                "/session", json={"token": result["token"]}, headers={"Origin": LOCAL}
            )
            self.assertEqual(signed.status_code, 200)
            self.assertEqual(signed.json()["result"]["role"], "AUDITOR")

            # Without a login file the feature stays off even when the role is set.
            bare = TestClient(make_app(runtime.service), base_url=LOCAL)
            self.assertEqual(bare.get("/session/demo").status_code, 404)


if __name__ == "__main__":
    unittest.main()
