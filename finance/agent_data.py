"""Scoped, paginated business reads. No model SQL, file paths or private simulator state."""

from __future__ import annotations

import json
from typing import Any

from finance.domain import AuthContext, FinanceError, Json, canonical, digest, require
from finance.execution import ExecutionService
from finance.ingestion import snapshot

VERSION = "agent-tools-v4"
PAGE_SIZE = 5
TEXT_PAGE = 3000
# Table/column names are server constants. Caller input is never SQL syntax.
TABLES = {
    "memberships": ("memberships", "user_id", "user_id,role,active"),
    "accounts": ("accounts", "account_id", "account_id,currency"),
    "beneficiaries": ("beneficiaries", "version_id", "version_id,logical_id,verified,payload"),
    "policies": ("policies", "version", "version,payload,observed_at"),
    "allocations": (
        "allocations",
        "allocation_id",
        "allocation_id,transaction_id,obligation_id,amount_minor,effective_at,observed_at",
    ),
    "imports": ("imports", "import_id", "import_id,source_id,status,accepted,rejected"),
    "approvals": (
        "approvals",
        "approval_id",
        "approval_id,actor,payload_hash,payload,expires_at,revoked",
    ),
    "actions": (
        "actions",
        "action_id",
        "action_id,idempotency_key,payload_hash,payload,status,approval_id,provider_ref,state_version",
    ),
    "reservations": (
        "reservations",
        "action_id",
        "action_id,account_id,amount_minor,status,included_in_provider_available",
    ),
    "attempts": ("attempts", "attempt_id", "attempt_id,action_id,sent_at,status,request_hash"),
    "jobs": ("execution_jobs", "action_id", "action_id,actor,attempts,last_error,finished"),
    "outbox": ("outbox", "action_id", "action_id,delivered,attempts"),
    "inbox": ("inbox", "event_id", "provider,event_id"),
    "ledger": ("ledger", "entry_id", "entry_id,line,account,amount_minor,currency,effective_at"),
    "audit": (
        "audit",
        "audit_id",
        "audit_id,occurred_at,event_type,payload,previous_hash,event_hash",
    ),
    "extensions": (
        "extension_requests",
        "request_id",
        "request_id,obligation_fact_id,proposed_due_at,status,decision_source_id",
    ),
}
DATASETS = tuple(TABLES) + (
    "company",
    "facts",
    "invoices",
    "transactions",
    "obligations",
    "sources",
    "reviews",
    "documents",
    "plans",
    "snapshots",
    "calculations",
    "workflows",
    "financing_products",
)


def _decoded(row: Any) -> Json:
    value = dict(row)
    if "payload" in value:
        value["payload"] = json.loads(value["payload"])
    return value


def records(service: ExecutionService, ctx: AuthContext, dataset: str) -> list[Json]:
    require(dataset in DATASETS, "INVALID_TOOL_ARGUMENTS", "Unknown business dataset")
    store = service.store
    company = store.company(ctx)  # Reauthorize on every call, including reads from old IDs.
    clock = company["clock"]
    with store.connect() as db:
        store.authorize(db, ctx)
        denied_sources = {
            r["source_id"]
            for r in db.execute(
                "SELECT source_id,read_roles FROM documents WHERE tenant_id=?", (ctx.tenant_id,)
            )
            if ctx.role not in json.loads(r["read_roles"])
        }
        if dataset in TABLES:
            table, identifier, columns = TABLES[dataset]
            rows = [
                _decoded(r)
                for r in db.execute(
                    f"SELECT {columns} FROM {table} WHERE tenant_id=?", (ctx.tenant_id,)
                )
            ]
            values = []
            for r in rows:
                if r.get("observed_at") and r["observed_at"] > clock:
                    continue
                if r.get("effective_at") and r["effective_at"] > clock:
                    continue
                if dataset == "audit" and any(s in canonical(r) for s in denied_sources):
                    continue
                key = str(r[identifier])
                if dataset == "ledger":
                    key += ":" + str(r["line"])
                if dataset == "inbox":
                    key = r["provider"] + ":" + key
                values.append({"record_id": key, **r})
        elif dataset == "company":
            values = [
                {
                    "record_id": ctx.tenant_id,
                    "name": company["name"],
                    "profile": json.loads(company["profile"]),
                    "as_of": clock,
                    "data_version": company["data_version"],
                    "stopped": bool(company["stopped"]),
                    "role": ctx.role,
                }
            ]
        elif dataset in {"facts", "invoices", "transactions"}:
            if dataset == "facts":
                facts = [
                    _decoded(r)
                    for r in db.execute(
                        "SELECT * FROM facts WHERE tenant_id=? AND observed_at<=? ORDER BY fact_id",
                        (ctx.tenant_id, clock),
                    )
                ]
                for f in facts:
                    f["value"] = f.pop("payload")
            else:
                facts = store.facts(db, ctx.tenant_id, clock, clock)
                kind = "INVOICE" if dataset == "invoices" else "TRANSACTION"
                facts = [f for f in facts if f["kind"] == kind]
            values = [
                {
                    **f["value"],
                    **{k: v for k, v in f.items() if k not in {"value", "tenant_id"}},
                    "record_id": f["fact_id"],
                }
                for f in facts
                if f["source_id"] not in denied_sources
            ]
        elif dataset in {"obligations", "financing_products"}:
            snap = snapshot(store, ctx)
            key = "fact_id" if dataset == "obligations" else "product_id"
            values = [{"record_id": v[key], **v} for v in snap[dataset]]
        elif dataset in {"plans", "snapshots", "calculations"}:
            kind = {"plans": "plan", "snapshots": "snapshot", "calculations": "agent_calculation"}[
                dataset
            ]
            values = [
                {"record_id": r["object_id"], **json.loads(r["payload"])}
                for r in db.execute(
                    "SELECT object_id,payload FROM objects WHERE tenant_id=? AND kind=? ORDER BY object_id",
                    (ctx.tenant_id, kind),
                )
            ]
            values = [v for v in values if not any(s in canonical(v) for s in denied_sources)]
        elif dataset in {"documents", "sources"}:
            if dataset == "documents":
                document_rows = db.execute(
                    "SELECT document_id,version,source_id,title,text_content,read_roles,observed_at FROM documents WHERE tenant_id=? AND observed_at<=? ORDER BY document_id,version",
                    (ctx.tenant_id, clock),
                )
                values = [
                    {
                        "record_id": r["document_id"] + ":" + str(r["version"]),
                        "document_id": r["document_id"],
                        "version": r["version"],
                        "source_id": r["source_id"],
                        "title": r["title"],
                        "text": r["text_content"],
                        "observed_at": r["observed_at"],
                        "trust": "UNTRUSTED_DATA",
                    }
                    for r in document_rows
                    if r["source_id"] not in denied_sources
                ]
            else:
                values = [
                    {"record_id": r["source_id"], **dict(r)}
                    for r in db.execute(
                        "SELECT source_id,provider,content_hash,observed_at FROM sources WHERE tenant_id=? AND observed_at<=? ORDER BY source_id",
                        (ctx.tenant_id, clock),
                    )
                    if r["source_id"] not in denied_sources
                ]
        elif dataset == "reviews":
            values = []
            for r in db.execute(
                "SELECT q.*,d.decision,d.reason,d.corrected_source_id,d.observed_at FROM quarantine q LEFT JOIN review_decisions d ON q.tenant_id=d.tenant_id AND q.import_id=d.import_id AND q.row_number=d.row_number WHERE q.tenant_id=? ORDER BY q.import_id,q.row_number",
                (ctx.tenant_id,),
            ):
                item = dict(r)
                item.pop("tenant_id", None)
                item["raw"] = json.loads(item["raw"])
                values.append({"record_id": r["import_id"] + ":" + str(r["row_number"]), **item})
        else:  # Workflows are scoped to their creator AND original role.
            values = []
            for r in db.execute(
                "SELECT run_id,task,provider,status,created_at,updated_at FROM workflow_runs WHERE tenant_id=? AND actor=? ORDER BY run_id",
                (ctx.tenant_id, ctx.user_id),
            ):
                access = db.execute(
                    "SELECT payload FROM workflow_events WHERE tenant_id=? AND run_id=? AND node='access_check' ORDER BY event_id LIMIT 1",
                    (ctx.tenant_id, r["run_id"]),
                ).fetchone()
                if access and json.loads(access[0]).get("role") == ctx.role:
                    values.append({"record_id": r["run_id"], **dict(r)})
    return sorted(values, key=lambda item: item["record_id"])


def _summary(value: Json) -> Json:
    result = {}
    for key, item in value.items():
        if key in {
            "text",
            "content",
            "payload",
            "facts",
            "obligations",
            "paths",
            "actions",
            "events",
            "messages",
        }:
            continue
        if isinstance(item, (str, int, bool)) or item is None:
            result[key] = item[:200] if isinstance(item, str) else item
    return result


def list_records(
    service: ExecutionService, ctx: AuthContext, dataset: str, query: str, offset: int
) -> Json:
    values = records(service, ctx, dataset)
    # Literal case-insensitive substring over authorized records; no query language.
    matches = [v for v in values if query.casefold() in canonical(v).casefold()]
    page = matches[offset : offset + PAGE_SIZE]
    totals = {
        key: sum(v.get(key, 0) for v in matches if type(v.get(key)) is int)
        for key in ("amount_minor", "outstanding_minor", "total_cost_minor")
        if any(type(v.get(key)) is int for v in matches)
    }
    if dataset == "facts":
        # Versions of one economic fact are alternatives, never additive debt.
        totals = {}
    return {
        "contract_version": VERSION,
        "dataset": dataset,
        "query": query,
        "records": [_summary(v) for v in page],
        "total_matches": len(matches),
        "offset": offset,
        "next_offset": offset + PAGE_SIZE if offset + PAGE_SIZE < len(matches) else None,
        "collection_hash": digest(matches),
        "field_totals": totals,
        "totals_scope": "History includes superseded versions; no financial aggregation is valid. Use current obligations or metrics."
        if dataset == "facts"
        else "All matching rows, not just this page. Field sums are not revenue or cash balance.",
        "detail_tool": "read_business_record",
        "trust": "UNTRUSTED_DATA",
    }


def read_record(
    service: ExecutionService, ctx: AuthContext, dataset: str, record_id: str, offset: int
) -> Json:
    value = next((v for v in records(service, ctx, dataset) if v["record_id"] == record_id), None)
    require(value is not None, "NOT_FOUND", "Authorized business record not found")
    assert value is not None
    if dataset == "sources":
        value = value | service.store.evidence(ctx, record_id)
    elif dataset == "plans":
        value = value | {"execution": service.plan_status(ctx, record_id)}
    elif dataset == "reviews":
        from finance.ingestion import parse_row

        diagnostic: Json = {"scope": "CURRENT_PARSER_RECHECK_NOT_IMPORT_ACCEPTANCE"}
        try:
            parse_row(value["raw"], service.store.company(ctx)["clock"])
        except FinanceError as exc:
            diagnostic.update({"status": "REJECTED", "code": exc.code, "message": str(exc)})
            if exc.safe_message == "Amounts/versions must be integers":
                diagnostic["invalid_integer_fields"] = [
                    field
                    for field in ("amount_minor", "version")
                    if not (
                        value["raw"][field].lstrip("-")
                        if field == "amount_minor"
                        else value["raw"][field]
                    ).isdigit()
                ]
                diagnostic["field_scope"] = (
                    "Only these fields failed the parser's integer check; do not attribute this error to the other fields."
                )
        else:
            diagnostic.update(
                {
                    "status": "PARSER_PASSED",
                    "notice": "Original quarantine decision remains; parser success alone does not establish business validity or accept this row.",
                }
            )
        value = value | {"validation_diagnostic": diagnostic}
    elif dataset == "workflows":
        from finance.workflows import WorkflowEngine

        value = WorkflowEngine(service).read(ctx, record_id)
        # Recheck source ACLs even when an older workflow used to be readable.
        with service.store.connect() as db:
            for row in db.execute(
                "SELECT source_id,read_roles FROM documents WHERE tenant_id=?", (ctx.tenant_id,)
            ):
                require(
                    ctx.role in json.loads(row["read_roles"])
                    or row["source_id"] not in canonical(value),
                    "POLICY_DENIED",
                    "Workflow includes restricted evidence",
                )
    text = canonical(value)
    require(offset <= len(text), "INVALID_TOOL_ARGUMENTS", "Offset exceeds record length")
    result: Json = {
        "contract_version": VERSION,
        "dataset": dataset,
        "record_id": record_id,
        "content_hash": digest(value),
        "offset": offset,
        "total_characters": len(text),
        "next_offset": offset + TEXT_PAGE if offset + TEXT_PAGE < len(text) else None,
        "trust": "UNTRUSTED_DATA",
    }
    if len(text) <= TEXT_PAGE and offset == 0:
        result["record"] = value
    else:
        result["json_fragment"] = text[offset : offset + TEXT_PAGE]
        result["notice"] = (
            "Partial JSON text. Continue with next_offset; compare content_hash across pages. Do not treat an omitted field as absent."
        )
    return result


def plan_details(
    service: ExecutionService, ctx: AuthContext, plan_id: str, offset: int = 0
) -> Json:
    plan = service.store.get_object(ctx, "plan", plan_id)
    execution = service.plan_status(ctx, plan_id)
    actions = [
        a | {"execution_status": status}
        for a, status in zip(plan["actions"], execution["action_states"])
    ]
    return {
        "plan_id": plan_id,
        "snapshot_id": plan["snapshot_id"],
        "total_cost_minor": plan["total_cost_minor"],
        "quote": plan["quote"],
        "actions": actions[offset : offset + PAGE_SIZE],
        "total_actions": len(actions),
        "next_offset": offset + PAGE_SIZE if offset + PAGE_SIZE < len(actions) else None,
        "execution": execution,
        "evidence_refs": plan["evidence_refs"],
        "note": "Planned actions are proposals. AWAITING_APPROVAL is not submission or settlement.",
    }


def prepare_proposal(
    service: ExecutionService, ctx: AuthContext, plan_id: str, action_id: str
) -> Json:
    with service.store.connect() as db:
        service.store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
    plan = service.store.get_object(ctx, "plan", plan_id)
    target = next((a for a in plan["actions"] if a["action_id"] == action_id), None)
    require(target is not None, "NOT_FOUND", "Action must belong to the scoped plan")
    try:
        command = service.command(ctx, plan_id, action_id)
        with service.store.connect() as db:
            observed = db.execute(
                "SELECT status FROM actions WHERE tenant_id=? AND action_id=?",
                (ctx.tenant_id, action_id),
            ).fetchone()
        return {
            "status": "PROPOSAL_ONLY",
            "readiness": "EXISTING_OPERATION" if observed else "EXACT_APPROVAL_REQUIRED",
            "observed_status": observed[0] if observed else "NOT_SUBMITTED",
            "plan_id": plan_id,
            "action_id": action_id,
            "command": command,
            "executed": False,
        }
    except FinanceError as exc:
        if exc.code != "PRECONDITION_FAILED":
            raise
        return {
            "status": "PROPOSAL_ONLY",
            "readiness": "WAITING_PRECONDITIONS",
            "plan_id": plan_id,
            "action_id": action_id,
            "action": target,
            "reason": exc.envelope(),
            "command": None,
            "executed": False,
        }


def capabilities() -> Json:
    return {
        "contract_version": VERSION,
        "datasets": list(DATASETS),
        "automatic": "Scoped reads, metrics, forecasts, financing calculations, planning, what-if and proposal preparation.",
        "human_controls": [
            {
                "operation": "Import CSV or documents; correct/discard quarantined rows; allocate settlements",
                "route": "#documents",
                "authority": "OWNER/ACCOUNTANT",
            },
            {
                "operation": "Change reserve/protected payments",
                "route": "#settings",
                "authority": "OWNER",
            },
            {
                "operation": "Approve/revoke exact payment; dispatch/recover; stop new sends",
                "route": "#plans",
                "authority": "Only OWNER may approve/revoke an exact payment; ACCOUNTANT cannot approve. Server worker dispatches after approval and current precondition checks.",
            },
            {
                "operation": "Cancel remaining plan",
                "route": "#plans",
                "authority": "OWNER; sent operations still reconcile",
            },
            {
                "operation": "Refresh/reconcile observed sandbox events",
                "route": "#home",
                "authority": "Server observation contract",
            },
            {
                "operation": "Confirm a supplier-extension decision or advance demo clock",
                "route": "#obligations",
                "authority": "Human demo controls; never model authority",
            },
        ],
        "unsupported": [
            "Real banking/ERP connectors",
            "Real notifications",
            "OCR/OFD/XML",
            "Private future simulator truth",
        ],
    }
