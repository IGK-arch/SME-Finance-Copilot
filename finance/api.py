"""Local authenticated API and English dashboard; no private simulator imports."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, cast
from urllib.parse import urlparse

from finance.compute import forecast, metrics
from finance.planner import solve as optimize
from finance.domain import AuthContext, FinanceError, Json, require, uid
from finance.execution import ExecutionService
from finance.ingestion import import_csv, snapshot
from finance import workspace
from finance.gateway import GatewayConfig
from finance.workflows import WorkflowEngine


def make_api(
    service: ExecutionService,
    port: int,
    demo_advance: Callable[[], Json] | None = None,
    queued_execution: bool = False,
) -> ThreadingHTTPServer:
    web_root = Path(__file__).resolve().parent.parent / "web"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.route()

        def do_POST(self) -> None:
            self.route()

        def route(self) -> None:
            request_id = uid("request")
            path = urlparse(self.path).path
            if self.command == "GET" and path in ("/", "/app.js", "/style.css"):
                filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                body = (web_root / filename).read_bytes()
                self.reply(
                    200,
                    body,
                    {
                        "index.html": "text/html; charset=utf-8",
                        "app.js": "text/javascript; charset=utf-8",
                        "style.css": "text/css; charset=utf-8",
                    }[filename],
                )
                return
            try:
                origin = self.headers.get("Origin")
                if origin:
                    parsed = urlparse(origin)
                    require(
                        parsed.scheme == "http"
                        and parsed.hostname == "127.0.0.1"
                        and parsed.port == cast(ThreadingHTTPServer, self.server).server_port,
                        "POLICY_DENIED",
                        "Cross-origin request denied",
                    )
                token = self.headers.get("Authorization", "").removeprefix("Bearer ")
                ctx = service.store.authenticate(token)
                length = int(self.headers.get("Content-Length", "0"))
                require(0 <= length <= 1_000_000, "INVALID_ARGUMENTS", "Request body too large")
                value = json.loads(self.rfile.read(length)) if length else {}
                require(isinstance(value, dict), "INVALID_ARGUMENTS", "JSON object required")
                require(
                    "tenant_id" not in value and "tenant" not in value,
                    "POLICY_DENIED",
                    "Tenant comes from authenticated membership",
                )
                result = dispatch(
                    service, ctx, self.command, path, value, demo_advance, queued_execution
                )
                self.json_reply(
                    200, {"schema_version": 1, "request_id": request_id, "result": result}
                )
            except FinanceError as exc:
                code = (
                    401
                    if exc.code == "UNAUTHORIZED"
                    else 403
                    if exc.code == "POLICY_DENIED"
                    else 404
                    if exc.code == "NOT_FOUND"
                    else 409
                )
                self.json_reply(code, {"request_id": request_id, "error": exc.envelope()})
            except (ValueError, KeyError, TypeError, AttributeError):
                self.json_reply(
                    400,
                    {
                        "request_id": request_id,
                        "error": {
                            "code": "INVALID_ARGUMENTS",
                            "safe_message": "Invalid request shape or value",
                            "retryable": False,
                        },
                    },
                )
            except Exception:
                self.json_reply(
                    500,
                    {
                        "request_id": request_id,
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "safe_message": "Request failed; no success asserted",
                            "retryable": False,
                        },
                    },
                )
                # Internal failures are visible to the developer, without body/header contents.
                import traceback

                traceback.print_exc()

        def json_reply(self, code: int, value: object) -> None:
            self.reply(
                code,
                json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
                "application/json; charset=utf-8",
            )

        def reply(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def dispatch(
    service: ExecutionService,
    ctx: AuthContext,
    method: str,
    path: str,
    value: Json,
    demo_advance: Callable[[], Json] | None = None,
    queued_execution: bool = False,
    demo_decision: Callable[[Json], Json] | None = None,
) -> Json:
    parts = path.strip("/").split("/")
    result: Json
    routed = v03_route(service, ctx, method, parts, value)
    if routed is not None:
        return routed
    if method == "GET" and path == "/v1/dashboard":
        snap = snapshot(service.store, ctx)
        with service.store.connect() as db:
            service.store.authorize(db, ctx)
            plans = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM objects WHERE tenant_id=? AND kind='plan' ORDER BY created_at DESC LIMIT 10",
                    (ctx.tenant_id,),
                )
            ]
            operations = [
                dict(r)
                for r in db.execute(
                    "SELECT action_id,status,provider_ref,state_version FROM actions WHERE tenant_id=? ORDER BY rowid",
                    (ctx.tenant_id,),
                )
            ]
            reserves = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM reservations WHERE tenant_id=?", (ctx.tenant_id,)
                )
            ]
            imports = [
                dict(r)
                for r in db.execute("SELECT * FROM imports WHERE tenant_id=?", (ctx.tenant_id,))
            ]
        result = {
            "snapshot": snap,
            "metrics": metrics(snap),
            "forecast": forecast(snap),
            "plans": plans,
            "operations": operations,
            "reservations": reserves,
            "active_reservations_minor": sum(
                r["amount_minor"] for r in reserves if r["status"] == "ACTIVE"
            ),
            "available_after_internal_reserves_minor": snap["confirmed_cash_minor"]
            - sum(r["amount_minor"] for r in reserves if r["status"] == "ACTIVE"),
            "imports": imports,
            "role": ctx.role,
            "stopped": bool(service.store.company(ctx)["stopped"]),
            "mode": {
                "data": "synthetic",
                "execution": "sandbox",
                "model": GatewayConfig.environment().public()["mode"].lower(),
                "model_name": GatewayConfig.environment().model or "deterministic-fixture",
            },
        }
    elif method == "GET" and path == "/v1/obligations":
        result = {"obligations": snapshot(service.store, ctx)["obligations"]}
    elif method == "POST" and path == "/v1/extensions":
        from finance.contingency import request_extension

        result = request_extension(service.store, ctx, value["fact_id"], value["due_at"])
    elif method == "GET" and path == "/v1/extensions":
        with service.store.connect() as db:
            service.store.authorize(db, ctx)
            result = {
                "extensions": [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM extension_requests WHERE tenant_id=?", (ctx.tenant_id,)
                    )
                ]
            }
    elif method == "POST" and path == "/v1/demo/extension-decision":
        with service.store.connect() as db:
            service.store.authorize(db, ctx, {"OWNER"})
            row = db.execute(
                "SELECT r.*,f.external_id FROM extension_requests r JOIN facts f ON r.tenant_id=f.tenant_id AND r.obligation_fact_id=f.fact_id WHERE r.tenant_id=? AND r.request_id=?",
                (ctx.tenant_id, value["request_id"]),
            ).fetchone()
            require(
                row is not None and type(value["accepted"]) is bool,
                "INVALID_ARGUMENTS",
                "Scoped request and boolean decision required",
            )
        require(
            demo_decision is not None,
            "UNSUPPORTED",
            "Synthetic counterparty control is unavailable",
        )
        assert demo_decision is not None
        decision = demo_decision(
            {
                "request_id": row["request_id"],
                "obligation_id": row["external_id"],
                "due_at": row["proposed_due_at"],
                "accepted": value["accepted"],
            }
        )
        service.refresh(ctx)
        result = {"observation": decision, "replan": service.make_plan(ctx)}
    elif method == "GET" and path == "/v1/health":
        import time

        with service.store.connect() as db:
            service.store.authorize(db, ctx)
            worker = db.execute(
                "SELECT heartbeat FROM worker_health WHERE tenant_id=?", (ctx.tenant_id,)
            ).fetchone()
        try:
            observation = service.adapter.observation()
            simulator = {"status": "CONNECTED", "clock": observation["clock"]}
        except FinanceError as exc:
            simulator = {"status": "UNAVAILABLE", "error": exc.code}
        result = {
            "database": {"backend": service.store.backend, "status": "CONNECTED"},
            "worker": {
                "status": "RUNNING"
                if worker and time.time() - worker[0] < 10
                else "NOT_RUNNING_OR_STALE"
            },
            "simulator": simulator,
            "model": GatewayConfig.environment().public(),
            "legacy_cabinet": os.getenv("SME_ENABLE_LEGACY") == "1",
        }
    elif method == "GET" and path == "/v1/audit/verify":
        result = service.store.verify_audit(ctx)
    elif method == "GET" and path == "/v1/audit":
        result = {"events": service.store.audit_log(ctx)}
    elif method == "GET" and len(parts) == 3 and parts[1] == "evidence":
        result = service.store.evidence(ctx, parts[2])
    elif method == "GET" and len(parts) == 3 and parts[1] in {"snapshots", "plans", "workflows"}:
        kind = {"snapshots": "snapshot", "plans": "plan", "workflows": "workflow"}[parts[1]]
        result = (
            WorkflowEngine(service).read(ctx, parts[2])
            if kind == "workflow"
            else service.store.get_object(ctx, kind, parts[2])
        )
        if kind == "plan":
            result = result | {"execution": service.plan_status(ctx, parts[2])}
    elif method == "GET" and len(parts) == 3 and parts[1] == "actions":
        result = service.action(ctx, parts[2])
    elif method == "POST" and path == "/v1/imports":
        result = import_csv(
            service.store,
            ctx,
            value["csv"].encode(),
            value["provider"],
            service.store.company(ctx)["clock"],
            value.get("closing_balance_minor"),
        )
    elif method == "POST" and path == "/v1/forecasts":
        result = forecast(snapshot(service.store, ctx), scenario_set=value.get("scenarios"))
    elif method == "POST" and path == "/v1/plans":
        result = service.make_plan(
            ctx, value.get("objective", "MIN_COST"), None, value.get("reserve_target_minor")
        )
    elif method == "POST" and len(parts) == 4 and parts[1] == "plans" and parts[3] == "command":
        result = service.command(ctx, parts[2], value["action_id"])
    elif method == "POST" and len(parts) == 4 and parts[1] == "plans" and parts[3] == "what-if":
        service.store.get_object(ctx, "plan", parts[2])
        snap = snapshot(service.store, ctx)
        require(
            type(value["receipt_delay_days"]) is int and 0 <= value["receipt_delay_days"] <= 365,
            "INVALID_ARGUMENTS",
            "Scenario delay must be 0–365 days",
        )
        result = {
            "label": "SCENARIO ONLY — actual obligations unchanged",
            "result": optimize(
                snap,
                scenario_set=[
                    {
                        "scenario_id": "what_if",
                        "delay_days": value["receipt_delay_days"],
                        "provenance": "OWNER_WHAT_IF",
                    }
                ],
            ),
        }
    elif method == "POST" and len(parts) == 4 and parts[1] == "plans" and parts[3] == "cancel":
        result = service.cancel_plan(ctx, parts[2])
    elif method == "POST" and path == "/v1/approvals":
        result = service.approve(ctx, value["command"])
    elif method == "POST" and len(parts) == 4 and parts[1] == "approvals" and parts[3] == "revoke":
        service.revoke(ctx, parts[2])
        result = {"status": "REVOKED"}
    elif method == "POST" and len(parts) == 4 and parts[1] == "actions" and parts[3] == "dispatch":
        command = value["command"]
        require(
            command["action_id"] == parts[2],
            "INVALID_ARGUMENTS",
            "Action path mismatch",
        )
        from finance.worker import enqueue

        if queued_execution:
            result = enqueue(
                service,
                ctx,
                command,
                "lost_response" if value.get("inject_lost_response") is True else "none",
            )
        else:
            service.prepare(ctx, command)
            result = service.deliver(
                ctx,
                parts[2],
                "lost_response" if value.get("inject_lost_response") is True else "none",
            )
    elif method == "POST" and len(parts) == 4 and parts[1] == "actions" and parts[3] == "recover":
        result = service.deliver(ctx, parts[2])
    elif method == "POST" and path == "/v1/reconcile":
        result = service.refresh(ctx)
    elif method == "POST" and path == "/v1/workflows":
        result = WorkflowEngine(service).run(ctx, task=value["task"])
    elif method == "POST" and len(parts) == 4 and parts[1] == "workflows" and parts[3] == "resume":
        result = WorkflowEngine(service).run(ctx, run_id=parts[2], answer=value)
    elif method == "GET" and path == "/v1/workflows":
        with service.store.connect() as db:
            service.store.authorize(db, ctx)
            result = {
                "workflows": [
                    dict(r)
                    for r in db.execute(
                        "SELECT run_id,task,provider,status,updated_at FROM workflow_runs WHERE tenant_id=? AND actor=? ORDER BY updated_at DESC LIMIT 30",
                        (ctx.tenant_id, ctx.user_id),
                    )
                ]
            }
    elif method == "GET" and path == "/v1/imports":
        result = workspace.imports(service.store, ctx)
    elif method == "POST" and len(parts) == 4 and parts[1] == "imports" and parts[3] == "review":
        result = workspace.review(
            service.store,
            ctx,
            parts[2],
            value["row_number"],
            value["decision"],
            value["reason"],
            value.get("corrected"),
        )
    elif method == "POST" and path == "/v1/allocations":
        from finance.ingestion import allocate

        result = {
            "allocation_id": allocate(
                service.store,
                ctx,
                value["transaction_id"],
                value["obligation_id"],
                value["amount_minor"],
                service.store.company(ctx)["clock"],
            )
        }
    elif path == "/v1/settings":
        result = workspace.settings(service.store, ctx, value if method == "POST" else None)
        result["model"] = GatewayConfig.environment().public()
    elif method == "GET" and path == "/v1/financing":
        result = workspace.products(service.store, ctx)
    elif method == "POST" and path == "/v1/financing/quote":
        from finance.compute import financing

        item = next(
            (
                p
                for p in [
                    entry["terms"] for entry in workspace.products(service.store, ctx)["products"]
                ]
                if p["product_id"] == value["product_id"]
            ),
            None,
        )
        require(item is not None, "NOT_FOUND", "DEMO product not found")
        assert item is not None
        result = financing(item, value["amount_minor"])
    elif method == "POST" and path == "/v1/documents":
        # Authorize BEFORE spawning the PDF parser: a read-only role must not be able to
        # occupy a 20-second parser subprocess per request (add_document re-checks).
        with service.store.connect() as db:
            service.store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        text = (
            workspace.extract_pdf(value["content_base64"])
            if value.get("format") == "pdf"
            else value["text"]
        )
        result = workspace.add_document(
            service.store,
            ctx,
            value["title"],
            text,
            value.get("read_roles"),
            value.get("document_id"),
        )
    elif method == "POST" and path == "/v1/retrieval":
        result = workspace.retrieve(service.store, ctx, value["query"], value.get("cutoff"))
    elif method == "GET" and path == "/v1/reports":
        result = workspace.report(service.store, ctx)
    elif method == "GET" and path == "/v1/approvals":
        with service.store.connect() as db:
            service.store.authorize(db, ctx)
            result = {
                "approvals": [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM approvals WHERE tenant_id=? ORDER BY rowid DESC",
                        (ctx.tenant_id,),
                    )
                ]
            }
    elif method == "POST" and path == "/v1/controls/stop":
        service.stop(ctx, value["enabled"], value["reason"])
        result = {"stopped": value["enabled"]}
    elif method == "POST" and path == "/v1/demo/advance":
        with service.store.connect() as db:
            service.store.authorize(db, ctx, {"OWNER", "ADMIN"})
        if demo_advance is None:
            raise FinanceError("UNSUPPORTED", "Synthetic clock control unavailable")
        result = demo_advance()
    else:
        raise FinanceError("NOT_FOUND", "Unsupported API path")
    return result


def v03_route(
    service: ExecutionService, ctx: AuthContext, method: str, parts: list[str], value: Json
) -> Json | None:
    """Owner main path read models (finance/cases.py). Mutations reuse ExecutionService."""
    from finance import cases
    from finance.digest_check import approve_and_queue

    key = (method, "/".join(parts[1:2]), len(parts))
    if key == ("GET", "home", 2):
        return cases.home(service, ctx)
    if key == ("GET", "case", 2):
        return cases.case_detail(service, ctx)
    if method == "POST" and len(parts) == 3 and parts[1] == "case":
        if parts[2] == "options":
            target = value.get("reserve_target_minor")
            require(target is None or type(target) is int, "INVALID_ARGUMENTS", "Integer target")
            return cases.compute_options(service, ctx, target)
        if parts[2] == "select":
            return cases.select_option(service, ctx, str(value.get("key") or ""))
        if parts[2] == "what-if":
            return cases.what_if(service, ctx, value)
    if key == ("GET", "review", 4):
        return cases.review(service, ctx, parts[2], parts[3])
    if method == "POST" and len(parts) == 5 and parts[1] == "review" and parts[4] == "approve":
        return approve_and_queue(service, ctx, parts[2], parts[3], value)
    if key == ("GET", "timeline", 3):
        return cases.timeline(service, ctx, parts[2])
    if method == "GET" and len(parts) == 4 and parts[1] == "plans" and parts[3] == "progress":
        return cases.plan_progress(service, ctx, parts[2])
    if (
        method == "POST"
        and len(parts) == 3
        and parts[1] == "imports"
        and parts[2] in {"preview", "commit"}
    ):
        from finance import mapping

        return (mapping.preview if parts[2] == "preview" else mapping.commit)(
            service.store, ctx, value
        )
    if key == ("GET", "copilot", 3):
        from finance.copilot import view

        return view(service, ctx, parts[2])
    if key == ("GET", "activity", 2):
        return cases.activity(service, ctx)
    if key == ("GET", "context", 2):
        return cases.load_context(service, ctx)
    if key == ("POST", "context", 2):
        return cases.save_context(service, ctx, value)
    return None
