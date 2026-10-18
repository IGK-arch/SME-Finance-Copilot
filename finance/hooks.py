"""Internal sandbox webhook contract v1; signed wakeups trigger trusted observation."""

import hashlib
import hmac
import json
import time

from finance.domain import AuthContext, Json, require
from finance.execution import ExecutionService


def receive(
    service: ExecutionService,
    ctx: AuthContext,
    secret: str,
    body: bytes,
    timestamp: str,
    signature: str,
) -> Json:
    require(
        bool(secret) and len(body) <= 10000,
        "WEBHOOK_DISABLED",
        "Configured bounded webhook required",
    )
    require(
        timestamp.isascii() and timestamp.isdigit() and abs(time.time() - int(timestamp)) <= 300,
        "WEBHOOK_AUTH_FAILED",
        "Webhook timestamp invalid",
    )
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    require(
        hmac.compare_digest(expected, signature), "WEBHOOK_AUTH_FAILED", "Webhook signature invalid"
    )
    value = json.loads(body)
    require(
        isinstance(value, dict)
        and set(value) == {"event_id"}
        and isinstance(value["event_id"], str)
        and 0 < len(value["event_id"]) <= 160,
        "INVALID_WEBHOOK",
        "Only a bounded event ID is accepted",
    )
    # Do not trust balances/commands in a webhook. Read the sandbox observation API.
    result = service.refresh(ctx)
    with service.store.transaction() as db:
        service.store.authorize(db, ctx)
        old = db.execute(
            "SELECT 1 FROM inbox WHERE tenant_id=? AND provider='sandbox_webhook' AND event_id=?",
            (ctx.tenant_id, value["event_id"]),
        ).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO inbox VALUES(?,'sandbox_webhook',?)",
            (ctx.tenant_id, value["event_id"]),
        )
    return {"status": "RECONCILED", "duplicate": bool(old), "reconciliation": result}
