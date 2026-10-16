"""Bounded mock orchestration and server-side READ/COMPUTE/PROPOSE tool registry."""

from __future__ import annotations

import json

from finance.compute import (
    catalog,
    eligibility,
    financing,
    forecast,
    metrics,
    plan_trajectories,
    scenarios,
)
from finance.domain import AuthContext, FinanceError, Json, digest, require, uid
from finance.execution import ExecutionService
from finance.ingestion import snapshot
from finance import agent_data


class ModelGateway:
    def __init__(
        self, provider: str = "mock", max_calls: int = 3, scripted_outputs: list[str] | None = None
    ) -> None:
        self.provider, self.max_calls, self.calls = provider, max_calls, 0
        self.outputs = scripted_outputs or ['{"objective":"MIN_COST"}']

    def task(self, text: str) -> Json:
        require(
            self.provider == "mock",
            "UNSUPPORTED_MODEL_PROVIDER",
            "No authorized live provider or fallback configured",
        )
        for _ in range(3):
            require(self.calls < self.max_calls, "BUDGET_EXCEEDED", "Mock call budget exhausted")
            output = self.outputs[min(self.calls, len(self.outputs) - 1)]
            self.calls += 1
            try:
                result = json.loads(output)
                if (
                    isinstance(result, dict)
                    and set(result) == {"objective"}
                    and result["objective"]
                    in {"MIN_COST", "NO_NEW_DEBT", "HIGHER_RESERVE", "PRESERVE_LIQUIDITY"}
                ):
                    return result
            except (ValueError, TypeError):
                pass
        raise FinanceError("INVALID_MODEL_OUTPUT", "Bounded mock output repair exhausted")


class ToolRegistry:
    INTEGER_BOUNDS = {
        "amount_minor": (1, 12000000),
        "offset": (0, 10000000),
        "delay_days": (0, 365),
        "receipt_bps": (0, 10000),
    }
    ARGUMENTS: dict[str, set[str]] = {
        "get_financial_snapshot": set(),
        "get_evidence": {"source_id"},
        "calculate_business_metrics": {"snapshot_id"},
        "forecast_cashflow": {"snapshot_id"},
        "screen_financing_products": {"snapshot_id"},
        "simulate_financing": {"snapshot_id", "product_id", "amount_minor"},
        "stress_test_plan": {"plan_id"},
        "optimize_plan": {"objective"},
        "prepare_action": {"plan_id", "action_id"},
        "get_action_status": {"action_id"},
        "search_documents": {"query"},
        "list_business_records": {"dataset", "query", "offset"},
        "read_business_record": {"dataset", "record_id", "offset"},
        "get_plan_details": {"plan_id", "offset"},
        "get_platform_capabilities": set(),
        "what_if_cashflow": {"snapshot_id", "delay_days", "receipt_bps"},
        "propose_supplier_extension": {"fact_id", "due_at"},
    }
    OPTIONAL_ARGUMENTS = {"search_documents": {"offset"}}

    def __init__(self, service: ExecutionService, ctx: AuthContext) -> None:
        self.service, self.ctx = service, ctx
        self.cache: dict[str, Json] = {}

    def call(self, name: str, arguments: Json) -> Json:
        try:
            require(
                isinstance(name, str) and name in self.ARGUMENTS,
                "UNKNOWN_TOOL",
                "Tool is not in the server allowlist",
            )
            require(
                isinstance(arguments, dict)
                and self.ARGUMENTS[name] <= set(arguments)
                and set(arguments)
                <= self.ARGUMENTS[name] | self.OPTIONAL_ARGUMENTS.get(name, set())
                and all(
                    (
                        type(v) is int
                        and self.INTEGER_BOUNDS[key][0] <= v <= self.INTEGER_BOUNDS[key][1]
                    )
                    if key in self.INTEGER_BOUNDS
                    else (isinstance(v, str) and len(v) <= 200)
                    for key, v in arguments.items()
                ),
                "INVALID_TOOL_ARGUMENTS",
                "Exact typed tool arguments required",
            )
            if "dataset" in arguments:
                require(
                    arguments["dataset"] in agent_data.DATASETS,
                    "INVALID_TOOL_ARGUMENTS",
                    "Unknown business dataset",
                )
            company = self.service.store.company(self.ctx)
            with self.service.store.connect() as db:
                self.service.store.authorize(db, self.ctx)
                policy_scope = self.service.store.policy(db, self.ctx.tenant_id)["version"]
            key = digest(
                [
                    self.ctx.tenant_id,
                    self.ctx.role,
                    company["data_version"],
                    company["clock"],
                    policy_scope,
                    name,
                    arguments,
                    agent_data.VERSION,
                ]
            )
            # Writes/proposals are never cached. Evidence cache is scoped to current ACL.
            cacheable = name in {
                "get_financial_snapshot",
                "calculate_business_metrics",
                "forecast_cashflow",
                "screen_financing_products",
                "simulate_financing",
            }
            if key in self.cache and cacheable:
                return self.cache[key]
            store = self.service.store
            snap = None
            if "snapshot_id" in arguments:
                snap = store.get_object(self.ctx, "snapshot", arguments["snapshot_id"])
            if name == "list_business_records":
                result = agent_data.list_records(self.service, self.ctx, **arguments)
            elif name == "read_business_record":
                result = agent_data.read_record(self.service, self.ctx, **arguments)
            elif name == "get_plan_details":
                result = agent_data.plan_details(self.service, self.ctx, **arguments)
            elif name == "get_platform_capabilities":
                result = agent_data.capabilities()
            elif name == "what_if_cashflow":
                assert snap is not None
                from finance.planner import solve

                scenario_set = [
                    {
                        "scenario_id": "user_what_if",
                        "delay_days": arguments["delay_days"],
                        "receipt_bps": arguments["receipt_bps"],
                        "provenance": "USER_ASSUMPTION",
                        "calibration_status": "UNCALIBRATED",
                    }
                ]
                result = {
                    "label": "SCENARIO ONLY; actual facts unchanged; hypothetical plan is not registered for execution",
                    "forecast": forecast(snap, scenario_set=scenario_set),
                    "hypothetical_plan": solve(snap, "MIN_COST", scenario_set=scenario_set),
                }
            elif name == "propose_supplier_extension":
                from finance.contingency import request_extension

                result = request_extension(
                    store, self.ctx, arguments["fact_id"], arguments["due_at"]
                )
            elif name == "search_documents":
                from finance.workspace import retrieve

                result = retrieve(
                    store, self.ctx, arguments["query"], offset=arguments.get("offset", 0)
                )
            elif name == "get_financial_snapshot":
                result = snapshot(store, self.ctx)
                snap = result
            elif name == "get_evidence":
                result = store.evidence(self.ctx, arguments["source_id"])
            elif name == "calculate_business_metrics":
                if snap is None:
                    raise FinanceError("INVALID_TOOL_ARGUMENTS", "Snapshot required")
                result = metrics(snap)
            elif name == "forecast_cashflow":
                if snap is None:
                    raise FinanceError("INVALID_TOOL_ARGUMENTS", "Snapshot required")
                result = forecast(snap)
            elif name == "screen_financing_products":
                if snap is None:
                    raise FinanceError("INVALID_TOOL_ARGUMENTS", "Snapshot required")
                result = {
                    "screens": [
                        eligibility(snap["profile"], p)
                        for p in snap.get("financing_products", catalog(snap["as_of"]))
                    ]
                }
            elif name == "simulate_financing":
                if snap is None:
                    raise FinanceError("INVALID_TOOL_ARGUMENTS", "Snapshot required")
                item = next(
                    (
                        p
                        for p in snap.get("financing_products", catalog(snap["as_of"]))
                        if p["product_id"] == arguments["product_id"]
                    ),
                    None,
                )
                if item is None:
                    raise FinanceError("UNSUPPORTED_PRODUCT_TERMS", "Unknown DEMO product")
                result = financing(item, arguments["amount_minor"])
            elif name == "stress_test_plan":
                plan = store.get_object(self.ctx, "plan", arguments["plan_id"])
                base = store.get_object(self.ctx, "snapshot", plan["snapshot_id"])
                result = {
                    "paths": plan_trajectories(base, plan, scenarios()),
                    "calibration_status": "UNCALIBRATED_DEMO",
                }
            elif name == "optimize_plan":
                result = self.service.make_plan(self.ctx, arguments["objective"])
            elif name == "prepare_action":
                result = agent_data.prepare_proposal(self.service, self.ctx, **arguments)
            else:
                result = self.service.action(self.ctx, arguments["action_id"])
            envelope: Json = {
                "status": "OK",
                "result_id": uid("result"),
                "snapshot_id": snap["snapshot_id"] if snap else None,
                "result": result,
                "evidence_refs": snap["evidence_refs"] if snap else [],
                "warnings": [],
                "missing_fields": [],
                "calculation_version": agent_data.VERSION,
                "error": None,
            }
            if name in {
                "calculate_business_metrics",
                "forecast_cashflow",
                "screen_financing_products",
                "simulate_financing",
                "stress_test_plan",
                "what_if_cashflow",
            }:
                with store.transaction() as db:
                    store.authorize(db, self.ctx)
                    store.put_object(
                        db,
                        self.ctx.tenant_id,
                        "agent_calculation",
                        envelope["result_id"],
                        {
                            "tool": name,
                            "arguments": arguments,
                            "result": result,
                            "contract_version": agent_data.VERSION,
                        },
                    )
            if cacheable:
                self.cache[key] = envelope
            return envelope
        except FinanceError as exc:
            return {
                "status": "ERROR",
                "result_id": None,
                "snapshot_id": None,
                "result": None,
                "evidence_refs": [],
                "warnings": [],
                "missing_fields": [],
                "calculation_version": None,
                "error": exc.envelope(),
            }


def workflow(
    service: ExecutionService, ctx: AuthContext, text: str, gateway: ModelGateway | None = None
) -> Json:
    require(isinstance(text, str) and 0 < len(text) <= 2000, "INVALID_TASK", "Task text required")
    gateway = gateway or ModelGateway()
    intent = gateway.task(text)
    registry = ToolRegistry(service, ctx)
    observed = registry.call("get_financial_snapshot", {})
    require(observed["status"] == "OK", "WORKFLOW_FAILED", "Snapshot access failed")
    snap_id = observed["result"]["snapshot_id"]
    outputs = [
        registry.call("calculate_business_metrics", {"snapshot_id": snap_id}),
        registry.call("forecast_cashflow", {"snapshot_id": snap_id}),
        registry.call("screen_financing_products", {"snapshot_id": snap_id}),
        registry.call("optimize_plan", intent),
    ]
    state: Json = {
        "workflow_id": uid("workflow"),
        "model_provider": "mock",
        "mock_label": "Deterministic test double",
        "phase": "PROPOSED" if all(o["status"] == "OK" for o in outputs) else "FAILED",
        "snapshot_id": snap_id,
        "objective": intent["objective"],
        "outputs": outputs,
        "model_usage": {
            "calls": gateway.calls,
            "tokens": None,
            "cost": None,
            "live_metrics_status": "NOT_RUN",
        },
        "note": "No money execution tools are exposed to the model",
    }
    with service.store.transaction() as db:
        service.store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        service.store.put_object(db, ctx.tenant_id, "workflow", state["workflow_id"], state)
    return state
