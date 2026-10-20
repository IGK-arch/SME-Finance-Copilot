"""FastAPI transport over the existing authorized domain dispatcher."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from finance.api import dispatch
from finance.domain import AuthContext, FinanceError, Json, canonical, require, uid
from finance.execution import ExecutionService

# Security events (failed sign-ins, denied origins/hosts, lockouts) go to this logger.
# Records carry the event name, method, path and client address only: never headers,
# cookies, tokens or bodies. Values are JSON-escaped so they cannot forge log lines.
SECURITY_LOG = logging.getLogger("sme.security")


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: str = Field(min_length=1, max_length=2000)
    context: dict[str, str] | None = None
    background: bool = False


SESSION_COOKIE = "sme_session"
SESSION_SECONDS = 8 * 3600
NAME = re.compile(r"^[a-z0-9_-]{1,40}\.(js|css|svg)$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
LEGACY_MONEY_ROUTE = re.compile(r"^(approvals|actions/[^/]+/dispatch)$")


class FailureLimiter:
    """Failed attempts per client address within a sliding window."""

    MAX_CLIENTS = 10000

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit, self.window = limit, window_seconds
        self.events: dict[str, list[float]] = {}

    def _recent(self, client: str) -> list[float]:
        cutoff = time.monotonic() - self.window
        recent = [t for t in self.events.get(client, []) if t > cutoff]
        if recent:
            self.events[client] = recent
        else:
            self.events.pop(client, None)
        return recent

    def blocked(self, client: str) -> bool:
        return len(self._recent(client)) >= self.limit

    def fail(self, client: str) -> None:
        if client not in self.events and len(self.events) >= self.MAX_CLIENTS:
            self.events.pop(next(iter(self.events)))
        self.events.setdefault(client, []).append(time.monotonic())


def public_origin() -> str | None:
    value = os.getenv("SME_PUBLIC_ORIGIN", "").rstrip("/")
    if not value:
        return None
    parsed = urlparse(value)
    require(
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.username,
        "UNSAFE_CONFIGURATION",
        "SME_PUBLIC_ORIGIN must be an https origin without path",
    )
    return f"{parsed.scheme}://{parsed.netloc}"


def legacy_enabled() -> bool:
    return os.getenv("SME_ENABLE_LEGACY") == "1"


def allowed_hosts(include_public: bool = True) -> set[str]:
    """Loopback names, hosts listed in SME_ALLOWED_HOSTS (comma-separated) and, for the
    Host check, the hostname of SME_PUBLIC_ORIGIN. Origins on the public host must match
    the exact https origin instead (see check_origin), so it is excluded there."""
    extra = os.getenv("SME_ALLOWED_HOSTS", "")
    hosts = LOOPBACK_HOSTS | {h.strip().lower() for h in extra.split(",") if h.strip()}
    public = public_origin() if include_public else None
    if public:
        hosts.add(str(urlparse(public).hostname))
    return hosts


def client_address(request: Request) -> str:
    """Peer address for per-client limits (behind Caddy: the forwarded client address)."""
    return request.client.host if request.client else "unknown"


def host_allowed(host: str) -> bool:
    """Reject DNS-rebinding requests: the Host header must name this server."""
    try:
        return bool(host) and urlparse("//" + host).hostname in allowed_hosts()
    except ValueError:
        return False


def security_event(event: str, request: Request, **fields: Any) -> None:
    client = request.client.host if request.client else None
    SECURITY_LOG.warning(
        "security_event %s",
        canonical(
            {
                "event": event,
                "method": request.method,
                "path": request.url.path[:200],
                "client": client,
            }
            | fields
        ),
    )


JSON_STRING = re.compile(rb'"(?:[^"\\]|\\.)*"', re.DOTALL)
JSON_BRACKET = re.compile(rb"[\[\]{}]")
MAX_JSON_DEPTH = 64


def parse_body(body: bytes | bytearray) -> Any:
    """Strict JSON: NaN/Infinity are refused and deep nesting is a shape error.

    Depth is bounded before decoding: the C decoder recurses per level, and in a worker
    thread a hostile body could exhaust the native stack before Python's recursion limit.
    """
    depth = 0
    for bracket in JSON_BRACKET.finditer(JSON_STRING.sub(b"", bytes(body))):
        depth += 1 if bracket.group() in (b"[", b"{") else -1
        if depth > MAX_JSON_DEPTH:
            raise ValueError("JSON nesting too deep")

    def non_finite(name: str) -> None:
        raise ValueError("Non-finite number " + name)

    return json.loads(body, parse_constant=non_finite)


def check_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlparse(origin)
        public = public_origin()
        try:
            hosts = allowed_hosts(include_public=False)
            local = parsed.scheme in ("http", "https") and parsed.hostname in hosts
            deployed = public is not None and f"{parsed.scheme}://{parsed.netloc}" == public
            ok = (local or deployed) and parsed.netloc == request.headers.get("host")
        except ValueError:
            ok = False
        if not ok:
            security_event("origin_denied", request, origin=origin[:200])
        require(ok, "POLICY_DENIED", "Cross-origin request denied")


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
    sign_in_failures = FailureLimiter(limit=20, window_seconds=300)
    # API bearer tokens get their own budget so guessing them cannot lock out browser sign-in.
    bearer_failures = FailureLimiter(limit=20, window_seconds=300)
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
        if host_allowed(request.headers.get("host", "")):
            response = await call_next(request)
        else:
            security_event("host_denied", request, host=request.headers.get("host", "")[:200])
            response = JSONResponse(
                {
                    "error": {
                        "code": "POLICY_DENIED",
                        "safe_message": "Unexpected Host header",
                        "retryable": False,
                    }
                },
                status_code=400,
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if public_origin():
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "object-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.get("/")
    async def index():
        return FileResponse(root / "index.html")

    @app.get("/legacy")
    async def legacy_index():
        if not legacy_enabled():
            return JSONResponse({"error": {"code": "NOT_FOUND"}}, status_code=404)
        return FileResponse(root / "legacy" / "index.html")

    @app.get("/legacy/{name}")
    async def legacy_asset(name: str):
        if not legacy_enabled() or name not in {"app.js", "style.css"}:
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

    @app.post("/session")
    async def create_session(request: Request):
        try:
            check_origin(request)
            client = client_address(request)
            if sign_in_failures.blocked(client):
                security_event("sign_in_rate_limited", request)
            require(
                not sign_in_failures.blocked(client),
                "RATE_LIMITED",
                "Too many failed sign-ins; wait five minutes",
            )
            body = parse_body(await request.body())
            require(
                isinstance(body, dict)
                and set(body) == {"token"}
                and isinstance(body["token"], str),
                "INVALID_ARGUMENTS",
                "Token required",
            )
            try:
                ctx = await run_in_threadpool(service.store.authenticate, body["token"])
            except FinanceError:
                sign_in_failures.fail(client)
                security_event("sign_in_failed", request)
                raise
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
                    service.store.audit(db, ctx, "session.created", {"user_id": ctx.user_id})

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
                secure=request.url.scheme == "https" or public_origin() is not None,
                path="/",
            )
            return response
        except FinanceError as exc:
            return JSONResponse(
                {"error": exc.envelope()},
                status_code={"UNAUTHORIZED": 401, "RATE_LIMITED": 429}.get(exc.code, 403),
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
            check_origin(request)
            ctx = await run_in_threadpool(session_context, service, raw)

            def revoke() -> None:
                with service.store.transaction() as db:
                    service.store.put_object(
                        db, ctx.tenant_id, "session_revoked", _session_key(raw), {"at": time.time()}
                    )
                    service.store.audit(db, ctx, "session.revoked", {"user_id": ctx.user_id})

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
            check_origin(request)
            bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
            cookie = request.cookies.get(SESSION_COOKIE)
            if bearer:
                client = client_address(request)
                if bearer_failures.blocked(client):
                    security_event("bearer_rate_limited", request)
                require(
                    not bearer_failures.blocked(client),
                    "RATE_LIMITED",
                    "Too many failed token attempts; wait five minutes",
                )
                try:
                    ctx = service.store.authenticate(bearer)
                except FinanceError:
                    bearer_failures.fail(client)
                    security_event("bearer_auth_failed", request)
                    raise
            else:
                require(bool(cookie), "UNAUTHORIZED", "Sign in required")
                # Cookie sessions need a header a cross-site form cannot send (CSRF).
                if request.method != "GET" and request.headers.get("X-SME-Request") != "1":
                    security_event("csrf_header_missing", request)
                require(
                    request.method == "GET" or request.headers.get("X-SME-Request") == "1",
                    "POLICY_DENIED",
                    "Missing request header",
                )
                try:
                    ctx = await run_in_threadpool(session_context, service, cookie or "")
                except FinanceError:
                    security_event("session_rejected", request)
                    raise
                require(
                    not (request.method == "POST" and LEGACY_MONEY_ROUTE.match(resource)),
                    "POLICY_DENIED",
                    "Browser sessions approve money only through review + step-up",
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                require(len(body) <= 1_000_000, "INVALID_ARGUMENTS", "Request body too large")
            value = parse_body(body) if body else {}
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
            code = {
                "UNAUTHORIZED": 401,
                "STEP_UP_REQUIRED": 403,
                "STEP_UP_LOCKED": 429,
                "RATE_LIMITED": 429,
                "POLICY_DENIED": 403,
                "NOT_FOUND": 404,
            }.get(exc.code, 409)
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
