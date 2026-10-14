"""FastAPI transport over the existing authorized domain dispatcher."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from finance.api import dispatch
from finance.domain import AuthContext, FinanceError, Json, require, uid
from finance.execution import ExecutionService


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: str = Field(min_length=1, max_length=2000)
    context: dict[str, str] | None = None
    background: bool = False


SESSION_COOKIE = "sme_session"
SESSION_SECONDS = 8 * 3600
NAME = re.compile(r"^[a-z0-9_-]{1,40}\.(js|css|svg)$")


def _session_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def session_context(service: ExecutionService, raw: str) -> AuthContext:
    """Server-side session: real-time expiry, revocation, and membership re-check."""
    key = _session_key(raw)
    with service.store.connect() as db:
        row = db.execute(
            "SELECT tenant_id,payload FROM objects WHERE kind='session' AND object_id=?", (key,)
        ).fetchone()
        require(row is not None, "UNAUTHORIZED", "Session not found; sign in again")
        payload = json.loads(row[1])
        revoked = db.execute(
            "SELECT 1 FROM objects WHERE tenant_id=? AND kind='session_revoked' AND object_id=?",
            (row[0], key),
        ).fetchone()
        require(
            not revoked and payload["expires_at"] > time.time(), "UNAUTHORIZED", "Session expired"
        )
        member = db.execute(
            "SELECT role FROM memberships WHERE tenant_id=? AND user_id=? AND active=1 AND token_hash=?",
            (row[0], payload["user_id"], payload["token_hash"]),
        ).fetchone()
        require(member is not None, "UNAUTHORIZED", "Membership changed; sign in again")
    return AuthContext(row[0], payload["user_id"], member[0])


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reserve_minor: int = Field(ge=0, le=10**12)
    protected: list[str]


def make_app(
    service: ExecutionService,
    demo_advance: Callable[[], Json] | None = None,
    demo_decision: Callable[[Json], Json] | None = None,
    webhook: tuple[AuthContext, str] | None = None,
) -> FastAPI:
    app = FastAPI(title="SME Finance Copilot", version="0.3.0")
    root = Path(__file__).resolve().parent.parent / "web"

    @app.post("/hooks/sandbox")
    async def sandbox_hook(request: Request):
        from finance.hooks import receive

        try:
            require(webhook is not None, "WEBHOOK_DISABLED", "Webhook not configured")
            assert webhook is not None
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                require(len(body) <= 10000, "INVALID_WEBHOOK", "Webhook size limit")
            return await run_in_threadpool(
                receive,
                service,
                webhook[0],
                webhook[1],
                bytes(body),
                request.headers.get("X-SME-Timestamp", ""),
                request.headers.get("X-SME-Signature", ""),
            )
        except (FinanceError, ValueError) as exc:
            return JSONResponse(
                {
                    "error": exc.envelope()
                    if isinstance(exc, FinanceError)
                    else {"code": "INVALID_WEBHOOK"}
                },
                status_code=403,
            )

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.get("/")
    async def index():
        return FileResponse(root / "index.html")

    @app.get("/legacy")
    async def legacy_index():
        return FileResponse(root / "legacy" / "index.html")

    @app.get("/legacy/{name}")
    async def legacy_asset(name: str):
        if name not in {"app.js", "style.css"}:
            return JSONResponse({"error": {"code": "NOT_FOUND"}}, status_code=404)
        return FileResponse(
            root / "legacy" / name,
            media_type="text/javascript" if name.endswith(".js") else "text/css",
        )

    @app.get("/assets/{name}")
    async def asset(name: str):
        path = root / name
        if not NAME.match(name) or not path.is_file():
            return JSONResponse({"error": {"code": "NOT_FOUND"}}, status_code=404)
        kind = {"js": "text/javascript", "css": "text/css", "svg": "image/svg+xml"}[
            name.rsplit(".", 1)[1]
        ]
        return FileResponse(path, media_type=kind)

    def same_origin(request: Request) -> None:
        origin = request.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            require(
                parsed.scheme in ("http", "https")
                and parsed.hostname == "127.0.0.1"
                and parsed.netloc == request.headers.get("host"),
                "POLICY_DENIED",
                "Cross-origin request denied",
            )

    @app.post("/session")
    async def create_session(request: Request):
        try:
            same_origin(request)
            body = await request.json()
            require(
                isinstance(body, dict)
                and set(body) == {"token"}
                and isinstance(body["token"], str),
                "INVALID_ARGUMENTS",
                "Token required",
            )
            ctx = await run_in_threadpool(service.store.authenticate, body["token"])
            raw = secrets.token_urlsafe(32)
            expires = time.time() + SESSION_SECONDS

            def save() -> None:
                with service.store.transaction() as db:
                    service.store.authorize(db, ctx)
                    service.store.put_object(
                        db,
                        ctx.tenant_id,
                        "session",
                        _session_key(raw),
                        {
                            "user_id": ctx.user_id,
                            "role": ctx.role,
                            "token_hash": service.store.token_hash(body["token"]),
                            "created_at": time.time(),
                            "expires_at": expires,
                        },
                    )
                    service.store.audit(
                        db, ctx.tenant_id, "session.created", {"user_id": ctx.user_id}
                    )

            await run_in_threadpool(save)
            response = JSONResponse(
                {"result": {"role": ctx.role, "user_id": ctx.user_id, "expires_at": expires}}
            )
            response.set_cookie(
                SESSION_COOKIE,
                raw,
                max_age=SESSION_SECONDS,
                httponly=True,
                samesite="strict",
                secure=request.url.scheme == "https",
                path="/",
            )
            return response
        except FinanceError as exc:
            return JSONResponse(
                {"error": exc.envelope()}, status_code=401 if exc.code == "UNAUTHORIZED" else 403
            )
        except (ValueError, KeyError, TypeError):
            return JSONResponse(
                {
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "safe_message": "Invalid sign-in request",
                        "retryable": False,
                    }
                },
                status_code=400,
            )

    @app.post("/session/logout")
    async def logout(request: Request):
        raw = request.cookies.get(SESSION_COOKIE, "")
        try:
            same_origin(request)
            ctx = await run_in_threadpool(session_context, service, raw)

            def revoke() -> None:
                with service.store.transaction() as db:
                    service.store.put_object(
                        db, ctx.tenant_id, "session_revoked", _session_key(raw), {"at": time.time()}
                    )
                    service.store.audit(
                        db, ctx.tenant_id, "session.revoked", {"user_id": ctx.user_id}
                    )

            await run_in_threadpool(revoke)
        except FinanceError:
            pass
        response = JSONResponse({"result": {"signed_out": True}})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.api_route("/v1/{resource:path}", methods=["GET", "POST"])
    async def endpoint(resource: str, request: Request):
        request_id = uid("request")
        try:
            origin = request.headers.get("Origin")
            if origin:
                parsed = urlparse(origin)
                require(
                    parsed.scheme == "http"
                    and parsed.hostname == "127.0.0.1"
                    and parsed.netloc == request.headers.get("host"),
                    "POLICY_DENIED",
                    "Cross-origin request denied",
                )
            bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
            cookie = request.cookies.get(SESSION_COOKIE)
            if bearer:
                ctx = service.store.authenticate(bearer)
            else:
                require(bool(cookie), "UNAUTHORIZED", "Sign in required")
                # Cookie sessions need a header a cross-site form cannot send (CSRF).
                require(
                    request.method == "GET" or request.headers.get("X-SME-Request") == "1",
                    "POLICY_DENIED",
                    "Missing request header",
                )
                ctx = await run_in_threadpool(session_context, service, cookie or "")
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                require(len(body) <= 1_000_000, "INVALID_ARGUMENTS", "Request body too large")
            value = json.loads(body) if body else {}
            require(isinstance(value, dict), "INVALID_ARGUMENTS", "JSON object required")
            require(
                "tenant" not in value and "tenant_id" not in value,
                "POLICY_DENIED",
                "Tenant comes from membership",
            )
            if request.method == "POST" and resource == "workflows":
                value = TaskRequest.model_validate(value).model_dump()
                if value.pop("background"):
                    from finance.copilot import start_background

                    return {
                        "schema_version": 1,
                        "request_id": request_id,
                        "result": await run_in_threadpool(start_background, service, ctx, value),
                    }
                from finance.copilot import compose_task

                value = {
                    "task": await run_in_threadpool(
                        compose_task, service, ctx, value["task"], value.get("context")
                    )
                }
            parts = resource.split("/")
            if (
                request.method == "POST"
                and len(parts) == 3
                and parts[0] == "workflows"
                and parts[2] == "resume"
                and value.pop("background", False) is True
            ):
                from finance.copilot import resume_background

                return {
                    "schema_version": 1,
                    "request_id": request_id,
                    "result": await run_in_threadpool(
                        resume_background, service, ctx, parts[1], value
                    ),
                }
            if request.method == "POST" and resource == "settings":
                value = PolicyRequest.model_validate(value).model_dump()
            result = await run_in_threadpool(
                dispatch,
                service,
                ctx,
                request.method,
                "/v1/" + resource,
                value,
                demo_advance,
                True,
                demo_decision,
            )
            return {"schema_version": 1, "request_id": request_id, "result": result}
        except FinanceError as exc:
            code = {"UNAUTHORIZED": 401, "POLICY_DENIED": 403, "NOT_FOUND": 404}.get(exc.code, 409)
            return JSONResponse(
                {"request_id": request_id, "error": exc.envelope()}, status_code=code
            )
        except (ValueError, KeyError, TypeError, AttributeError, ValidationError):
            return JSONResponse(
                {
                    "request_id": request_id,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "safe_message": "Invalid request shape or value",
                        "retryable": False,
                    },
                },
                status_code=400,
            )
        except Exception:
            import logging

            logging.exception("API failure %s", request_id)
            return JSONResponse(
                {
                    "request_id": request_id,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "safe_message": "Request failed; no success asserted",
                        "retryable": False,
                    },
                },
                status_code=500,
            )

    return app
