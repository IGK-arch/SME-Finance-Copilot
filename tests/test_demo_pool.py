"""Personal reviewer demos: one isolated, freshly seeded workspace per visitor."""

import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finance.asgi import SESSION_COOKIE, make_app
from scripts.demo_pool import DemoLimits, DemoPool, controls
from scripts.runtime import Runtime

LOCAL = "http://127.0.0.1:8080"
POST = {"X-SME-Request": "1"}


class DemoPoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.main = Runtime(root / "workspace")
        self.pool = DemoPool(
            root / "workspace-demos", DemoLimits(max_active=2, per_client=3, idle_hours=6)
        )
        advance, decision = controls(self.main)
        self.app = make_app(self.main.service, advance, decision, demos=self.pool)

    def tearDown(self) -> None:
        self.pool.close()
        self.main.close()
        self.folder.cleanup()

    def visitor(self) -> TestClient:
        return TestClient(self.app, base_url=LOCAL)

    def start(self, client: TestClient) -> dict:
        response = client.post("/session/demo/new", json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]

    def test_feature_off_is_404(self) -> None:
        client = TestClient(make_app(self.main.service), base_url=LOCAL)
        self.assertEqual(client.get("/session/demo/new").status_code, 404)
        self.assertEqual(client.post("/session/demo/new", json={}).status_code, 404)
        self.assertEqual(self.visitor().get("/session/demo/new").json()["result"]["idle_hours"], 6)

    def test_demos_are_isolated_from_each_other_and_the_main_workspace(self) -> None:
        a, b, owner = self.visitor(), self.visitor(), self.visitor()
        key_a, key_b = self.start(a)["token"], self.start(b)["token"]
        self.assertNotEqual(key_a, key_b)
        self.assertNotIn(key_a, self.main.tokens.values())
        owner.post("/session", json={"token": self.main.tokens["OWNER"]})

        # A raises its reserve; B and the main company do not change.
        changed = a.post(
            "/v1/settings", json={"reserve_minor": 2500000, "protected": ["salary"]}, headers=POST
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        need = {
            name: c.get("/v1/home").json()["result"]["problem"]["need"]["minor"]
            for name, c in (("a", a), ("b", b), ("main", owner))
        }
        self.assertEqual(need, {"a": 9500000, "b": 9000000, "main": 9000000})

        # Each demo has its own bank: an approval in A leaves B's sandbox untouched.
        worlds = [folder / "private" / "world.db" for folder in sorted(self.pool.root.iterdir())]
        self.assertEqual(len(worlds), 2)
        self.assertNotEqual(*(w.resolve() for w in worlds))

        # A demo key is never a main-workspace key, as a bearer token or a cookie.
        self.assertEqual(
            self.visitor()
            .get("/v1/home", headers={"Authorization": "Bearer " + key_a})
            .status_code,
            401,
        )
        cookie_a = a.cookies.get(SESSION_COOKIE)
        cookie_b = b.cookies.get(SESSION_COOKIE)
        id_a, raw_a = cookie_a.split(".", 1)
        id_b = cookie_b.split(".", 1)[0]
        for forged in (raw_a, f"{id_b}.{raw_a}", f"{'0' * 16}.{raw_a}", f"../x.{raw_a}"):
            probe = self.visitor()
            probe.cookies.set(SESSION_COOKIE, forged)
            self.assertEqual(probe.get("/v1/home").status_code, 401, forged)

        # A saved key signs back in to its own demo only.
        again = self.visitor()
        signed = again.post("/session", json={"token": key_a})
        self.assertEqual(signed.status_code, 200)
        self.assertTrue(again.cookies.get(SESSION_COOKIE).startswith(id_a + "."))
        self.assertEqual(
            again.get("/v1/home").json()["result"]["problem"]["need"]["minor"], 9500000
        )

    def test_capacity_and_per_client_limit(self) -> None:
        self.start(self.visitor())
        self.start(self.visitor())
        full = self.visitor().post("/session/demo/new", json={})
        self.assertEqual(full.status_code, 503)
        self.assertEqual(full.json()["error"]["code"], "DEMO_CAPACITY")
        self.assertIn("All demo slots are busy", full.json()["error"]["safe_message"])
        limited = self.visitor().post("/session/demo/new", json={})
        self.assertEqual(limited.status_code, 429)  # three starts per client per hour

    def test_cleanup_stops_idle_and_deletes_only_expired_demo_folders(self) -> None:
        client = self.visitor()
        self.start(client)
        demo = next(self.pool.root.iterdir())
        stray = self.pool.root / "not-a-demo"
        stray.mkdir()
        later = time.time() + 3600
        self.assertEqual(self.pool.sweep(later), {"stopped": [demo.name], "deleted": []})
        self.assertEqual(client.get("/v1/home").status_code, 200)  # resumed on demand
        result = self.pool.sweep(time.time() + 7 * 3600)
        self.assertEqual(result["deleted"], [demo.name])
        self.assertFalse(demo.exists())
        self.assertTrue(stray.is_dir())
        self.assertTrue((self.main.directory / "observed" / "finance.db").exists())
        self.assertEqual(client.get("/v1/home").status_code, 401)  # demo has ended

    def test_golden_path_inside_a_demo(self) -> None:
        client = self.visitor()
        key = self.start(client)["token"]
        call = lambda path, value=None: client.post(path, json=value, headers=POST).json()  # noqa: E731
        options = call("/v1/case/options", {})["result"]
        self.assertTrue(any(o["key"] == "FINANCE_MIN_COST" for o in options["options"]))
        plan_id = call("/v1/case/select", {"key": "FINANCE_MIN_COST"})["result"]["plan_id"]
        steps = client.get(f"/v1/plans/{plan_id}/progress").json()["result"]["steps"]
        for s in steps:
            action = s["action_id"]
            for _ in range(8):
                review = client.get(f"/v1/review/{plan_id}/{action}").json()["result"]
                if review.get("approvable"):
                    break
                call("/v1/demo/advance", {})
            approved = call(
                f"/v1/review/{plan_id}/{action}/approve",
                {"payload_hash": review["payload_hash"], "confirm": True, "reauth": key},
            )
            self.assertIn("result", approved, approved)
            status = ""
            for _ in range(60):
                status = client.get(f"/v1/timeline/{action}").json()["result"]["status"]
                if status in {"SUBMITTED", "SETTLED"}:
                    break
                time.sleep(0.25)
            for _ in range(8):
                call("/v1/demo/advance", {})
                status = client.get(f"/v1/timeline/{action}").json()["result"]["status"]
                if status == "SETTLED":
                    break
            self.assertEqual(status, "SETTLED", s["title"])
        progress = client.get(f"/v1/plans/{plan_id}/progress").json()["result"]
        recon = call("/v1/reconcile", {})["result"]
        closed = client.get("/v1/case").json()["result"]
        self.assertEqual(progress["status"], "COMPLETED")
        self.assertTrue(recon["matched"])
        self.assertEqual(recon["discrepancy_minor"], 0)
        self.assertEqual(
            (closed.get("last_closed") or {}).get("closed_reason"),
            "RESOLVED_SETTLED_AND_RECONCILED",
        )
        # The main company is still at the start of its story.
        owner = self.visitor()
        owner.post("/session", json={"token": self.main.tokens["OWNER"]})
        self.assertEqual(owner.get("/v1/home").json()["result"]["state"], "GAP")


if __name__ == "__main__":
    unittest.main()
