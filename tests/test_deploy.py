"""Public deployment behind a TLS reverse proxy (SME_PUBLIC_ORIGIN)."""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finance.asgi import FailureLimiter, make_app, public_origin
from finance.domain import FinanceError
from scripts.runtime import Runtime

ORIGIN = "https://copilot.example.com"


class DeployTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SME_PUBLIC_ORIGIN"] = ORIGIN

    def tearDown(self) -> None:
        os.environ.pop("SME_PUBLIC_ORIGIN", None)

    def test_public_origin_must_be_exact_https(self) -> None:
        self.assertEqual(public_origin(), ORIGIN)
        for bad in ("http://copilot.example.com", "https://copilot.example.com/app", "copilot"):
            os.environ["SME_PUBLIC_ORIGIN"] = bad
            with self.assertRaises(FinanceError):
                public_origin()
        os.environ.pop("SME_PUBLIC_ORIGIN")
        self.assertIsNone(public_origin())

    def test_domain_sign_in_secure_cookie_and_hsts(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url=ORIGIN)
            signed = client.post(
                "/session", json={"token": runtime.tokens["OWNER"]}, headers={"Origin": ORIGIN}
            )
            self.assertEqual(signed.status_code, 200)
            cookie = signed.headers["set-cookie"].lower()
            self.assertIn("secure", cookie)
            self.assertIn("httponly", cookie)
            self.assertIn("samesite=strict", cookie)
            self.assertIn("max-age=31536000", signed.headers["strict-transport-security"])
            for bad in (
                "http://copilot.example.com",
                "https://evil.example",
                "https://copilot.example.com.evil.example",
            ):
                denied = client.post(
                    "/session", json={"token": runtime.tokens["OWNER"]}, headers={"Origin": bad}
                )
                self.assertEqual(denied.status_code, 403, bad)

    def test_loopback_still_works_when_public_origin_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            client = TestClient(make_app(runtime.service), base_url="http://127.0.0.1:8080")
            signed = client.post(
                "/session",
                json={"token": runtime.tokens["OWNER"]},
                headers={"Origin": "http://127.0.0.1:8080"},
            )
            self.assertEqual(signed.status_code, 200)

    def test_sign_in_limit_is_per_client(self) -> None:
        limiter = FailureLimiter(limit=3, window_seconds=300)
        for _ in range(3):
            limiter.fail("203.0.113.9")
        self.assertTrue(limiter.blocked("203.0.113.9"))
        self.assertFalse(limiter.blocked("198.51.100.7"))  # a judge elsewhere is not locked out


if __name__ == "__main__":
    unittest.main()
