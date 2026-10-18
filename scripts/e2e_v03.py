"""v0.3 product-path E2E over the real HTTP server, worker and independent sandbox.

Drives the same endpoints as the browser cabinet with a cookie session:
changed source data -> problem diff -> options -> select -> per-action review/approve ->
queue worker -> lost response -> forced server restart mid-flight -> settlement ->
reconciliation -> independent world evaluation and duplicate checks on world.db.

This is NOT a LIVE agent evaluation: no model chooses anything here (MOCK runtime).
Usage: python -m scripts.e2e_v03 [--output artifacts/v03/e2e-latest.json]
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, port: int) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def call(self, path: str, value: dict | None = None, expect: int = 200) -> dict:
        data = None if value is None else json.dumps(value).encode()
        headers = (
            {"Content-Type": "application/json", "X-SME-Request": "1"} if data is not None else {}
        )
        request = Request(
            self.base + path,
            data=data,
            headers=headers,
            method="POST" if data is not None else "GET",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                code, body = response.status, json.loads(response.read())
        except HTTPError as error:
            code, body = error.code, json.loads(error.read() or b"{}")
        if code != expect:
            raise AssertionError(f"{path}: HTTP {code} {body}")
        return body.get("result", body)


class Server:
    def __init__(self, directory: Path, port: int, log: Path) -> None:
        self.directory, self.port, self.log = directory, port, log
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        handle = open(self.log, "ab")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.serve",
                "--port",
                str(self.port),
                "--directory",
                str(self.directory),
            ],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("Server did not start")

    def kill(self) -> None:
        """Forced stop (no graceful shutdown), like a crash: process tree is killed."""
        assert self.process is not None
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(self.process.pid)], capture_output=True
            )
        else:
            self.process.kill()
        self.process.wait(30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/v03/e2e-latest.json")
    args = parser.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    directory = ROOT / ".runtime" / "v03-e2e" / stamp
    directory.parent.mkdir(parents=True, exist_ok=True)
    seed = subprocess.run(
        [sys.executable, "-m", "scripts.task", "seed-demo", "--directory", str(directory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr
    log: list[dict] = []
    checks: dict[str, bool] = {}

    def step(name: str, **data: object) -> None:
        log.append({"at": time.time(), "step": name} | data)
        print(f"[e2e] {name} {json.dumps(data, ensure_ascii=False)[:220]}", flush=True)

    port = free_port()
    server = Server(directory, port, directory / "server.log")
    server.start()
    owner = json.loads((directory / "local-login.secret.json").read_text())["OWNER"]
    c = Client(port)
    c.call("/session", {"token": owner})
    home = c.call("/v1/home")
    step(
        "home_initial",
        state=home["state"],
        need=home["problem"]["need"]["display"],
        gap=home["problem"]["first_gap_at"],
    )
    checks["initial_gap_90000"] = (
        home["state"] == "GAP" and home["problem"]["need"]["minor"] == 9000000
    )

    # 1. Changed source data: the customer tells us the receipt moves to 15 Oct (new version).
    moved = {
        "template": "obligations",
        "format": "csv",
        "options": {"namespace": "synthetic_csv", "kind": "RECEIVABLE"},
        "content": 'reference,counterparty,amount,due_date\ncustomer_invoice,customer,"100,000.00",2026-10-15\n',
    }
    preview = c.call("/v1/imports/preview", moved)
    step(
        "import_preview", ready=preview["summary"]["ready"], update=preview["rows"][0].get("update")
    )
    committed = c.call(
        "/v1/imports/commit", moved | {"confirm": True, "raw_digest": preview["raw_digest"]}
    )
    step(
        "import_commit",
        status=committed["import"]["status"],
        accepted=committed["import"]["accepted"],
    )
    home = c.call("/v1/home")
    history = [h["type"] for h in home["case"]["history"]]
    receivable = next(o for o in home["upcoming"] if o["reference"] == "customer_invoice")
    step(
        "home_after_change",
        state=home["state"],
        history=history,
        receivable_due=receivable["due_at"],
    )
    checks["receivable_due_moved"] = receivable["due_at"].startswith("2026-10-14T16:00")
    checks["same_gap_not_reported_as_change"] = "PROBLEM_CHANGED" not in history
    # A change that does move the problem: the owner raises the hard reserve to CNY 25,000.
    c.call("/v1/settings", {"reserve_minor": 2500000, "protected": ["salary", "rent"]})
    home = c.call("/v1/home")
    changes = [h for h in home["case"]["history"] if h["type"] == "PROBLEM_CHANGED"]
    step(
        "home_after_policy",
        need=home["problem"]["need"]["display"],
        change=changes[-1]["summary"] if changes else None,
    )
    checks["change_recorded_in_case"] = (
        bool(changes) and home["problem"]["need"]["minor"] == 9500000
    )

    # 2. Options and selection.
    options = c.call("/v1/case/options", {})
    by = {o["key"]: o for o in options["options"]}
    step("options", summary=options["summary"], statuses={k: v["status"] for k, v in by.items()})
    checks["options_differ"] = (
        by["FINANCE_MIN_COST"]["status"] == "EXECUTABLE"
        and by["NO_NEW_DEBT"]["status"] == "INFEASIBLE"
    )
    selected = c.call("/v1/case/select", {"key": "FINANCE_MIN_COST"})
    plan_id = selected["plan_id"]
    plan = c.call(f"/v1/plans/{plan_id}/progress")
    step("selected", plan_id=plan_id, actions=[s["title"] for s in plan["steps"]])
    refused = c.call(
        f"/v1/review/{plan_id}/{plan['steps'][0]['action_id']}/approve",
        {"payload_hash": "0" * 64, "confirm": True, "reauth": owner},
        expect=409,
    )
    no_step_up = c.call(
        f"/v1/review/{plan_id}/{plan['steps'][0]['action_id']}/approve",
        {"payload_hash": "0" * 64, "confirm": True},
        expect=403,
    )
    checks["approval_requires_step_up"] = (
        no_step_up.get("error", {}).get("code") == "STEP_UP_REQUIRED"
    )
    legacy = c.call("/v1/approvals", {"command": {}}, expect=403)
    checks["browser_session_cannot_use_legacy_money_route"] = (
        legacy.get("error", {}).get("code") == "POLICY_DENIED"
    )
    checks["tampered_hash_refused"] = refused.get("error", {}).get("code") in {
        "APPROVAL_HASH_MISMATCH",
        "PRECONDITION_FAILED",
    }

    restarted = False
    for index, s in enumerate(plan["steps"]):
        action = s["action_id"]
        for _ in range(8):
            review = c.call(f"/v1/review/{plan_id}/{action}")
            if review.get("approvable"):
                break
            c.call("/v1/demo/advance", {})
        else:
            raise AssertionError(f"Action never became approvable: {review.get('block')}")
        lost = s["kind"] == "PAY_OBLIGATION" and "supplier" in review["command"]["obligation_id"]
        result = c.call(
            f"/v1/review/{plan_id}/{action}/approve",
            {
                "payload_hash": review["payload_hash"],
                "confirm": True,
                "reauth": owner,
                "inject_lost_response": lost,
            },
        )
        step(
            "approved",
            n=index + 1,
            title=review["title"],
            status=result["status"],
            lost_response=lost,
        )
        # Wait for the worker (separate process) to send.
        for _ in range(40):
            state = c.call(f"/v1/timeline/{action}")["status"]
            if state in {"SUBMITTED", "UNKNOWN", "SETTLED", "FAILED"}:
                break
            time.sleep(0.5)
        step("worker_sent", title=review["title"], status=state)
        if lost and not restarted:
            server.kill()
            step("server_killed", while_status=state)
            server.start()
            restarted = True
            again = c.call("/v1/home")  # same cookie session survives the restart
            step("server_restarted", home_state=again["state"])
            checks["session_survives_restart"] = True
        for _ in range(8):
            c.call("/v1/demo/advance", {})
            line = c.call(f"/v1/timeline/{action}")
            if line["status"] == "SETTLED":
                break
            time.sleep(0.5)
        step(
            "settled", title=review["title"], status=line["status"], attempts=len(line["attempts"])
        )
        checks[f"action_{index + 1}_settled"] = line["status"] == "SETTLED"
        if lost:
            checks["lost_response_single_attempt"] = len(line["attempts"]) == 1

    progress = c.call(f"/v1/plans/{plan_id}/progress")
    recon = c.call("/v1/reconcile", {})
    final = c.call("/v1/home")
    step(
        "final",
        plan=progress["status"],
        reconciliation=recon["status"],
        cash=final["metrics"]["confirmed_cash"]["display"],
        state=final["state"],
    )
    checks["plan_completed"] = progress["status"] == "COMPLETED"
    checks["reconciled_zero_difference"] = recon["matched"] and recon["discrepancy_minor"] == 0
    checks["final_cash_29000"] = final["metrics"]["confirmed_cash"]["minor"] == 2900000
    closed = c.call("/v1/case")
    step(
        "case_after",
        state=closed["state"],
        closed_reason=(closed.get("last_closed") or {}).get("closed_reason"),
    )
    checks["case_resolved_only_after_reconciliation"] = (
        final["case"] is None
        and (closed.get("last_closed") or {}).get("closed_reason")
        == "RESOLVED_SETTLED_AND_RECONCILED"
    )
    server.kill()

    # 3. Independent checks straight from the sandbox world database (not via the app).
    world = sqlite3.connect(f"file:{directory / 'private' / 'world.db'}?mode=ro", uri=True)
    duplicates = world.execute(
        "SELECT stable_key, COUNT(*) FROM operations GROUP BY stable_key HAVING COUNT(*)>1"
    ).fetchall()
    operations = world.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    movements = world.execute("SELECT COUNT(*) FROM movements").fetchone()[0]
    cash = world.execute("SELECT cash FROM worlds").fetchone()[0]
    world.close()
    observed = sqlite3.connect(f"file:{directory / 'observed' / 'finance.db'}?mode=ro", uri=True)
    ledger_pairs = observed.execute("SELECT COUNT(DISTINCT entry_id) FROM ledger").fetchone()[0]
    unbalanced = observed.execute(
        "SELECT entry_id FROM ledger GROUP BY entry_id HAVING COUNT(*)!=2 OR SUM(amount_minor)!=0"
    ).fetchall()
    observed.close()
    step(
        "world",
        operations=operations,
        movements=movements,
        cash=cash,
        duplicate_keys=len(duplicates),
        ledger_pairs=ledger_pairs,
    )
    checks["world_one_operation_per_key"] = not duplicates and operations == 5
    checks["world_movements_6"] = movements == 6
    checks["world_cash_matches"] = cash == 2900000
    checks["ledger_one_balanced_pair_per_movement"] = ledger_pairs == movements and not unbalanced

    report = {
        "schema_version": 1,
        "kind": "V03_PRODUCT_PATH_E2E",
        "scope": "Real HTTP server + queue worker + independent sandbox via cookie session; MOCK runtime; no LIVE model decisions",
        "workspace": str(directory.relative_to(ROOT)),
        "checks": checks,
        "passed": all(checks.values()),
        "steps": log,
        "not_covered": [
            "Pixel rendering (see browser evidence)",
            "LIVE agent from a free-form request (deferred until the target model)",
        ],
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks}, indent=1))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
