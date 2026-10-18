"""Approve exactly the reviewed payload, then queue it for the worker.

The browser sends only the payload hash it displayed. The server recompiles the current
command; a different digest (facts/policy/clock changed) is refused, so the human always
approves what the server will send. Approval and queueing remain the existing
ExecutionService.approve/prepare checks (OWNER, freshness, reserve, idempotency).
"""

from __future__ import annotations

from finance.domain import AuthContext, FinanceError, Json, digest, require
from finance.execution import ExecutionService
from finance.worker import enqueue


def step_up(service: ExecutionService, ctx: AuthContext, secret: object) -> None:
    ok = False
    if isinstance(secret, str) and 0 < len(secret) <= 200:
        try:
            again = service.store.authenticate(secret)
            ok = (again.tenant_id, again.user_id, again.role) == (
                ctx.tenant_id,
                ctx.user_id,
                ctx.role,
            )
        except FinanceError:
            ok = False
    if not ok:
        with service.store.transaction() as db:
            service.store.audit(db, ctx, "approval.step_up_failed", {"user_id": ctx.user_id})
    require(ok, "STEP_UP_REQUIRED", "Re-enter your access token to approve a money movement")


def approve_and_queue(
    service: ExecutionService, ctx: AuthContext, plan_id: str, action_id: str, value: Json
) -> Json:
    shown = value.get("payload_hash")
    require(
        isinstance(shown, str) and len(shown) == 64,
        "INVALID_ARGUMENTS",
        "Displayed payload hash required",
    )
    require(value.get("confirm") is True, "INVALID_ARGUMENTS", "Explicit confirmation required")
    step_up(service, ctx, value.get("reauth"))
    fault = "lost_response" if value.get("inject_lost_response") is True else "none"
    command = service.command(ctx, plan_id, action_id)
    require(
        digest(command) == shown,
        "APPROVAL_HASH_MISMATCH",
        "The command changed since you reviewed it; review the refreshed command",
    )
    approval = service.approve(ctx, command)
    action = enqueue(service, ctx, command, fault)
    return {
        "approval": approval,
        "action_id": action["action_id"],
        "status": action["status"],
        "fault_injected": fault != "none",
        "next": "Track the operation timeline; it counts as paid only after reconciliation.",
    }
