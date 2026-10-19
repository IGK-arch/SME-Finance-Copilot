"""Security audit 18 Oct: host/headers, token guessing, strict JSON, XML, replay, agent audit."""

import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from finance.agents import ToolRegistry
from finance.asgi import make_app
from finance.domain import FinanceError
from finance.hooks import receive
from finance.mapping import read_xlsx, safe_xml
from scripts.runtime import Runtime
from scripts.security_scan import public_ipv4, scan_files, scan_text, tracked_files

LOCAL = "http://127.0.0.1:8080"
SHEET = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    b'<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>a</t></is></c></row>'
    b'<row r="2"><c r="A2" t="inlineStr"><is><t>b</t></is></c></row></sheetData></worksheet>'
)


def workbook(sheet: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


class HttpHardeningTests(unittest.TestCase):
    def test_dns_rebinding_host_is_refused_and_headers_are_set(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            headers = {"Authorization": "Bearer " + r.tokens["OWNER"]}
            with self.assertLogs("sme.security", "WARNING") as logs:
                rebound = TestClient(make_app(r.service), base_url="http://attacker.example:8080")
                response = rebound.get("/v1/dashboard", headers=headers)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"]["code"], "POLICY_DENIED")
            self.assertIn("host_denied", logs.output[0])
            self.assertNotIn(r.tokens["OWNER"], "".join(logs.output))
            self.assertEqual(rebound.get("/").status_code, 400)

            local = TestClient(make_app(r.service), base_url=LOCAL)
            ok = local.get("/v1/dashboard", headers=headers)
            self.assertEqual(ok.status_code, 200)
            for name, value in {
                "X-Frame-Options": "DENY",
                "Cross-Origin-Opener-Policy": "same-origin",
                "Cross-Origin-Resource-Policy": "same-origin",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }.items():
                self.assertEqual(ok.headers[name], value)
            self.assertIn("object-src 'none'", ok.headers["Content-Security-Policy"])
            self.assertIn("frame-ancestors 'none'", ok.headers["Content-Security-Policy"])
            self.assertIn("camera=()", ok.headers["Permissions-Policy"])
            self.assertNotIn("Strict-Transport-Security", ok.headers)
            secure = TestClient(make_app(r.service), base_url="https://127.0.0.1:8443")
            self.assertIn("max-age", secure.get("/").headers["Strict-Transport-Security"])
            self.assertEqual(
                TestClient(make_app(r.service), base_url="http://[::1]:8080").get("/").status_code,
                200,
            )

    def test_operator_can_allow_an_extra_host(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            with mock.patch.dict(os.environ, {"SME_ALLOWED_HOSTS": "cabinet.internal"}):
                client = TestClient(make_app(r.service), base_url="http://cabinet.internal")
                self.assertEqual(client.get("/").status_code, 200)

    def test_bearer_token_guessing_is_rate_limited_and_logged(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            client = TestClient(make_app(r.service), base_url=LOCAL)
            with self.assertLogs("sme.security", "WARNING") as logs:
                codes = [
                    client.get(
                        "/v1/dashboard", headers={"Authorization": f"Bearer guess-{i}"}
                    ).status_code
                    for i in range(21)
                ]
            self.assertEqual(codes[:20], [401] * 20)
            self.assertEqual(codes[20], 429)
            text = "".join(logs.output)
            self.assertIn("bearer_auth_failed", text)
            self.assertIn("bearer_rate_limited", text)
            self.assertNotIn("guess-", text)
            # Locked out even with a valid token: a guesser gets no success oracle.
            valid = client.get(
                "/v1/dashboard", headers={"Authorization": "Bearer " + r.tokens["OWNER"]}
            )
            self.assertEqual(valid.status_code, 429)
            # Browser sign-in keeps its own budget.
            signin = client.post("/session", json={"token": r.tokens["OWNER"]})
            self.assertEqual(signin.status_code, 200, signin.text)

    def test_failed_sign_in_and_foreign_origin_are_logged_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            client = TestClient(make_app(r.service), base_url=LOCAL)
            with self.assertLogs("sme.security", "WARNING") as logs:
                self.assertEqual(
                    client.post("/session", json={"token": "wrong-secret-value"}).status_code, 401
                )
                self.assertEqual(
                    client.post(
                        "/session",
                        json={"token": r.tokens["OWNER"]},
                        headers={"Origin": "http://evil.example"},
                    ).status_code,
                    403,
                )
            text = "\n".join(logs.output)
            self.assertIn("sign_in_failed", text)
            self.assertIn("origin_denied", text)
            self.assertNotIn("wrong-secret-value", text)
            self.assertNotIn(r.tokens["OWNER"], text)
            self.assertEqual(len(logs.output), 2)

    def test_non_finite_and_deeply_nested_json_are_shape_errors(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            client = TestClient(make_app(r.service), base_url=LOCAL)
            headers = {
                "Authorization": "Bearer " + r.tokens["OWNER"],
                "Content-Type": "application/json",
            }
            for body in (
                b'{"reserve_target_minor": NaN}',
                b'{"reserve_target_minor": Infinity}',
                b'{"x":' * 100000 + b"1" + b"}" * 100000,
            ):
                response = client.post("/v1/case/options", content=body, headers=headers)
                self.assertEqual(response.status_code, 400, response.text[:200])
                self.assertEqual(response.json()["error"]["code"], "INVALID_ARGUMENTS")


class WorkbookXmlTests(unittest.TestCase):
    def test_plain_utf8_sheet_is_read(self) -> None:
        self.assertEqual(read_xlsx(workbook(SHEET)), [["a"], ["b"]])

    def test_dtd_entity_and_foreign_encodings_are_refused(self) -> None:
        bombs = [
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><r>&a;</r>',
            b'<?xml version="1.0"?><!doctype r SYSTEM "file:///etc/passwd"><r/>',
            b'<?xml version="1.0" encoding="UTF-16"?><r/>'.decode().encode("utf-16"),
            b'<?xml version="1.0" encoding="cp1026"?><r/>',
            b'\xef\xbb\xbf<?xml version="1.0"?><!ENTITY x "y"><r/>',
        ]
        for bomb in bombs:
            with self.assertRaises(FinanceError) as raised:
                safe_xml(bomb)
            self.assertEqual(raised.exception.code, "INVALID_FILE")
            with self.assertRaises(FinanceError):
                read_xlsx(workbook(bomb))
        self.assertEqual(
            safe_xml(b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?><r/>').tag, "r"
        )


class ReplayAndAuditTests(unittest.TestCase):
    def test_replayed_signed_webhook_does_not_reconcile_again(self) -> None:
        import hashlib
        import hmac
        import time

        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            secret, body = "offline-test-signing-key", json.dumps({"event_id": "e-1"}).encode()
            stamp = str(int(time.time()))
            signature = hmac.new(
                secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            calls = []
            original = r.service.refresh
            r.service.refresh = lambda ctx, observation=None: calls.append(1) or original(ctx)  # type: ignore[method-assign]
            first = receive(r.service, r.ctx, secret, body, stamp, signature)
            again = receive(r.service, r.ctx, secret, body, stamp, signature)
            self.assertFalse(first["duplicate"])
            self.assertEqual(again, {"status": "DUPLICATE_IGNORED", "duplicate": True})
            self.assertEqual(len(calls), 1)

    def test_model_proposals_are_in_the_hash_chained_audit(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            plan = registry.call("optimize_plan", {"objective": "MIN_COST"})
            self.assertEqual(plan["status"], "OK")
            registry.call("get_financial_snapshot", {})
            events = r.store.audit_events(r.ctx, {"agent.tool_call"})
            self.assertEqual(len(events), 1, "reads are not audited as agent actions")
            payload = json.loads(events[0]["payload"])
            self.assertEqual(payload["tool"], "optimize_plan")
            self.assertEqual(payload["tier"], "T2_PROPOSE")
            self.assertFalse(payload["executed"])
            self.assertEqual(payload["actor"], r.ctx.user_id)
            self.assertEqual(payload["result_id"], plan["result_id"])
            self.assertTrue(r.store.verify_audit(r.ctx)["valid"])


class SecretScanTests(unittest.TestCase):
    def test_rules_detect_secrets_without_flagging_versions_or_loopback(self) -> None:
        sample = "\n".join(
            [
                "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
                "token = ghp_" + "a" * 36,
                '"private_key": "0x' + "ab" * 32 + '"',
                "host " + ".".join("8844") + " port 22",
                "engine 0.1.43.1 at 127.0.0.1 and 10.0.0.5, 192.168.1.2",
            ]
        )
        rules = [(f["line"], f["rule"]) for f in scan_text(sample, set())]
        self.assertEqual(
            rules,
            [
                (1, "private_key_block"),
                (2, "github_token"),
                (3, "hex_private_key"),
                (4, "public_ipv4"),
            ],
        )
        self.assertEqual(public_ipv4("1.2.3"), [])
        self.assertEqual(scan_text("host " + ".".join("8844"), {".".join("8844")}), [])

    def test_tracked_files_contain_no_secrets_or_public_hosts(self) -> None:
        allowed = set(json.loads(Path("checklists/security_scan_allow.json").read_text())["ipv4"])
        self.assertEqual(scan_files(tracked_files(), allowed), [])


if __name__ == "__main__":
    unittest.main()
