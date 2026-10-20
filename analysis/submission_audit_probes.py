"""Readiness audit probes, synthetic isolated runtimes; report observations, not fixes.

Run with python -m analysis.submission_audit_probes. No production data or model calls.
Provider observations are deliberately corrupted to test reconciliation boundaries.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from finance import anchor
from finance.agents import ToolRegistry
from finance.compute import analysis
from finance.ingestion import snapshot
from scripts.runtime import Runtime


def settlement_probe(field: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="sme-audit-") as folder, Runtime(Path(folder)) as r:
        service, ctx = r.service, r.ctx
        plan = service.make_plan(ctx)["plan"]
        r.advance(1)
        draw = next(a for a in plan["actions"] if a["kind"] == "DRAW_LOAN")
        command = service.command(ctx, plan["plan_id"], draw["action_id"])
        service.approve(ctx, command)
        service.prepare(ctx, command)
        service.deliver(ctx, command["action_id"])
        r.settle()
        r.advance(4)
        pay = next(a for a in plan["actions"] if a["obligation_id"] == "salary")
        command = service.command(ctx, plan["plan_id"], pay["action_id"])
        service.approve(ctx, command)
        service.prepare(ctx, command)
        service.deliver(ctx, command["action_id"])
        r.admin("/admin/advance", {"clock": r.store.company(ctx)["clock"]})
        observation = service.adapter.observation()
        movement = next(
            m for m in observation["movements"] if m.get("stable_key") == command["idempotency_key"]
        )
        previous = movement[field]
        movement[field] = "synthetic_wrong_" + field
        result = service.refresh(ctx, observation)
        action = service.action(ctx, command["action_id"])
        salary = next(
            o for o in snapshot(r.store, ctx)["obligations"] if o["external_id"] == "salary"
        )
        with r.store.connect() as db:
            reserve = db.execute(
                "SELECT status FROM reservations WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, command["action_id"]),
            ).fetchone()
        return {
            "probe": "settlement_wrong_" + field,
            "input": {"field": field, "original": previous, "replacement": movement[field]},
            "action_status": action["status"],
            "reservation_status": reserve[0] if reserve else None,
            "salary_outstanding_minor": salary["outstanding_minor"],
            "stopped": r.store.company(ctx)["stopped"],
            "reconciliation": result,
            "finding_reproduced": action["status"] == "SETTLED" and salary["outstanding_minor"] > 0,
        }


def anchor_privacy_probe() -> dict:
    tag = anchor.tenant_tag("demo_company").hex()
    candidates = ["other_company", "demo_company", "unknown_company"]
    guessed = [c for c in candidates if anchor.tenant_tag(c).hex() == tag]
    return {
        "probe": "anchor_tenant_tag_dictionary",
        "payload_bytes": anchor.PAYLOAD_BYTES,
        "known_candidate_recovered": guessed == ["demo_company"],
        "interpretation": "Public deterministic tag is pseudonymous, not anonymous or secretly salted.",
    }


def business_health_probe() -> dict:
    with (
        tempfile.TemporaryDirectory(prefix="sme-health-audit-") as folder,
        Runtime(Path(folder)) as r,
    ):
        snap = snapshot(r.store, r.ctx)
        health = analysis(snap)
        registry = ToolRegistry(r.service, r.ctx)
        result = registry.call("calculate_business_metrics", {"snapshot_id": snap["snapshot_id"]})
        return {
            "probe": "business_health_tool_contract",
            "available_tools": sorted(registry.ARGUMENTS),
            "agent_metric_keys": sorted(result["result"]["metrics"]),
            "business_health_keys": sorted(health),
            "missing_computed_metrics": sorted(set(health) - set(result["result"])),
            "interpretation": "The Money page's new business-health computation is not exposed by the metrics tool. Raw inputs remain accessible.",
        }


def main() -> None:
    report = {
        "scope": "Synthetic provider-fault injection. No financial operation outside the local sandbox.",
        "probes": [
            settlement_probe("counterparty"),
            settlement_probe("reference"),
            anchor_privacy_probe(),
            business_health_probe(),
        ],
    }
    out = Path("artifacts/submission-audit-20261019/adversarial-probes.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
