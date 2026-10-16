"""Bounded read-completion and domain checks, never financial authorization.

Only the original user task declares read requirements. Tool/document text cannot
add requirements or authority. These checks cover named failure classes, not all
natural-language meanings.
"""

from __future__ import annotations

import re

from finance.agent_data import DATASETS
from finance.domain import Json

VERSION = "answer-quality-v3"
ALIASES = {
    "company": r"профил\w* компани\w*|company profile",
    "accounts": r"банковск\w* счет\w*|счета(?=,)|accounts",
    "beneficiaries": r"бенефициар\w*|beneficiar\w*",
    "memberships": r"роли участников|участник\w* компани\w*|membership\w*|member roles",
    "actions": r"current operations|existing operation",
    "policies": r"политик\w*|polic(?:y|ies)",
    "imports": r"\bимпорт(?:ы|ов)\b|import batches",
    "reviews": r"строк\w* карантин\w*|quarantined review rows",
    "audit": r"аудит\w*",
    "transactions": r"транзакци\w*",
    "allocations": r"распределени\w*",
    "ledger": r"бухгалтерск\w* проводк\w*",
    "inbox": r"входящ\w* событи\w*",
    "snapshots": r"сохран[её]нн\w* снимк\w*",
    "calculations": r"сохран[её]нн\w* расч[её]т\w*",
}
READ = r"\b(?:проверь|прочитай|прочти|перечисли|найди|сопоставь|inspect|read|list|find|check|compare|search)\b"
NEGATED_READ = r"(?:не\s+(?:надо\s+)?|do not\s+|don't\s+)(?:читай|читайте|проверяй|перечисляй|read|list|inspect|check|search)\b"


def requirements(task: str) -> Json:
    """Conservative intent grammar; ambiguous/unnamed requests remain model-led."""
    positive = " ".join(
        s for s in re.split(r"[.!?;\n]", task) if not re.search(NEGATED_READ, s, re.I)
    )
    requested: set[str] = set()
    if re.search(READ, positive, re.I):
        for dataset in DATASETS:
            # Plan children are proposals, not the executed-operations registry.
            scope = positive
            if dataset == "actions":
                scope = re.sub(
                    r"\b(?:planned|its|their|the plan's) actions\b", "", scope, flags=re.I
                )
            if re.search(r"\b" + dataset + r"\b", scope, re.I):
                requested.add(dataset)
        for dataset, pattern in ALIASES.items():
            if re.search(pattern, positive, re.I):
                requested.add(dataset)
    full_document = bool(
        re.search(r"документ|document", positive, re.I)
        and re.search(
            r"целиком|полностью|in full|entire document|including the end", positive, re.I
        )
        and re.search(READ, positive, re.I)
    )
    catalog = bool(re.search(r"перечисли\s+все\s+документ|list\s+all\s+documents", positive, re.I))
    document_search = bool(re.search(r"\bsearch\s+documents\b", positive, re.I))
    if document_search and not (full_document or catalog):
        requested.discard("documents")
    if full_document or catalog:
        requested.add("documents")
    return {
        "version": VERSION,
        "datasets": sorted(requested),
        "document_search": document_search,
        "capabilities": bool(
            re.search(
                r"where\b[^.!?]*\b(?:approve|confirm)|human.only controls|platform capabilities|где\b[^.!?]*подтверд",
                positive,
                re.I,
            )
        ),
        "all_pages": bool(
            re.search(r"все страницы|all pages|every search page|полный перечень", positive, re.I)
        ),
        "full_document": full_document,
        "review_diagnostic": "reviews" in requested
        and bool(re.search(r"ошибк|error|diagnos|почему", positive, re.I)),
    }


def missing_reads(contract: Json, outputs: list[Json]) -> list[Json]:
    good = [o for o in outputs if o["output"].get("status") == "OK"]
    lists = [o["output"]["result"] for o in good if o["name"] == "list_business_records"]
    listed = {v["dataset"] for v in lists if v.get("offset") == 0}
    missing = [
        {
            "tool": "list_business_records",
            "dataset": d,
            "notice": "Choose the user's literal query; start at offset zero",
        }
        for d in contract["datasets"]
        if d not in listed
    ]
    if contract.get("capabilities") and not any(
        o["name"] == "get_platform_capabilities" for o in good
    ):
        missing.append({"tool": "get_platform_capabilities"})
    if contract.get("document_search"):
        searches = [o["output"]["result"] for o in good if o["name"] == "search_documents"]
        if not any(v.get("offset") == 0 for v in searches):
            missing.append({"tool": "search_documents", "offset": 0})
        if contract["all_pages"]:
            for value in searches:
                next_offset = value.get("next_offset")
                if next_offset is not None and not any(
                    v["collection_hash"] == value["collection_hash"] and v["offset"] == next_offset
                    for v in searches
                ):
                    missing.append({"tool": "search_documents", "offset": next_offset})
    if contract["all_pages"]:
        for value in lists:
            next_offset = value.get("next_offset")
            if next_offset is not None and not any(
                v["dataset"] == value["dataset"]
                and v["query"] == value["query"]
                and v["collection_hash"] == value["collection_hash"]
                and v["offset"] == next_offset
                for v in lists
            ):
                missing.append(
                    {
                        "tool": "list_business_records",
                        "dataset": value["dataset"],
                        "query": value["query"],
                        "offset": next_offset,
                    }
                )
    if (
        contract.get("review_diagnostic")
        and any(v["dataset"] == "reviews" and v["records"] for v in lists)
        and not any(
            o["name"] == "read_business_record"
            and o["output"]["result"].get("dataset") == "reviews"
            for o in good
        )
    ):
        missing.append(
            {
                "tool": "read_business_record",
                "dataset": "reviews",
                "offset": 0,
                "notice": "Read the relevant observed quarantine record for its parser diagnostic; copy its exact record_id.",
            }
        )
    if contract["full_document"]:
        details = [
            o["output"]["result"]
            for o in good
            if o["name"] == "read_business_record"
            and o["output"]["result"].get("dataset") == "documents"
        ]
        # Empty/denied authorized lookups must not force fabricated detail reads.
        visible_documents = any(v["dataset"] == "documents" and v["records"] for v in lists)
        if visible_documents and not details:
            missing.append(
                {
                    "tool": "read_business_record",
                    "dataset": "documents",
                    "offset": 0,
                    "notice": "Read the requested observed document record, including every continuation page",
                }
            )
        for record_id, content_hash in {(v["record_id"], v["content_hash"]) for v in details}:
            pages = {
                v["offset"]: v
                for v in details
                if (v["record_id"], v["content_hash"]) == (record_id, content_hash)
            }
            next_offset = 0
            while next_offset in pages:
                following = pages[next_offset].get("next_offset")
                if following is None:
                    next_offset = None
                    break
                if following <= next_offset:
                    break  # fail closed on malformed continuation, never loop
                next_offset = following
            # Extra overlapping reads cannot invalidate an already complete chain.
            if next_offset is not None:
                missing.append(
                    {
                        "tool": "read_business_record",
                        "dataset": "documents",
                        "record_id": record_id,
                        "offset": next_offset,
                    }
                )
    return missing


def repeated_read(outputs: list[Json]) -> bool:
    """Bound a no-progress loop; distinct pagination calls remain available."""
    reads = {
        "get_platform_capabilities",
        "get_financial_snapshot",
        "get_evidence",
        "search_documents",
        "list_business_records",
        "read_business_record",
        "get_plan_details",
        "get_action_status",
    }
    tail = outputs[-3:]
    return len(tail) == 3 and all(
        o["name"] in reads
        and o["output"].get("status") == "OK"
        and o["name"] == tail[0]["name"]
        and "result" in o["output"]
        and o["output"]["result"] == tail[0]["output"].get("result")
        for o in tail
    )


def project(value: Json) -> Json:
    """Interpret only schema-owned fields; never recursively interpret document text."""
    dataset = value.get("dataset", "")
    flags = {
        "jobs": {"finished": ("NOT_COMPLETED", "COMPLETED")},
        "outbox": {"delivered": ("NOT_DELIVERED", "DELIVERED")},
        "approvals": {"revoked": ("NOT_REVOKED", "REVOKED")},
    }.get(dataset, {})

    def row(record: Json) -> Json:
        interpreted = dict(record)
        for name, states in flags.items():
            if type(record.get(name)) in {int, bool} and record[name] in (0, 1):
                interpreted[name + "_state"] = states[int(record[name])]
        return interpreted

    result = dict(value)
    if isinstance(value.get("payload"), dict):
        result["preconditions_scope"] = (
            "Payload preconditions name requirements, not a current validation result. Do not call them unmet or satisfied without an actual check."
        )
    payload = value.get("payload")
    if isinstance(payload, dict) and payload.get("kind") == "DRAW_LOAN":
        result["operation_interpretation"] = {
            "cash_direction": "INCOMING_TO_COMPANY",
            "counterparty_role": "LENDER_NOT_PAYMENT_RECIPIENT",
            "scope": "Loan draw credits the company's account by cash_delta_minor; it does not pay the lender. amount_minor is principal, not reserved cash. RESERVED is a protocol state, not evidence of a positive money hold. Read reservations for actual reserved amount. Copy completion_predicate exactly.",
        }
    if flags:
        if isinstance(value.get("records"), list):
            result["records"] = [row(r) for r in value["records"]]
        if isinstance(value.get("record"), dict):
            result["record"] = row(value["record"])
    notes = {
        "company": "role denotes the current authenticated member's role; a company itself has no OWNER role. data_version belongs to company data, not membership version.",
        "jobs": "finished_state is job completion; actor is the requester, not proof that the job ran. No recorded error is not proof of success. record_id is the action_id here, not an attempt_id.",
        "audit": "Audit rows describe recorded events; no cryptographic chain verification tool ran. Summarize relevant events, omit internal hashes unless explicitly requested.",
        "outbox": "delivered_state is outbox acknowledgement, not payment settlement. Missing acknowledgement does not prove the provider never received the command. UNKNOWN requires status lookup before any retry; this read does not decide whether to resend.",
        "approvals": "Not revoked does not establish still-valid approval: expiry and current preconditions are checked by executor. OWNER payment approval is not lender credit approval.",
        "reservations": "An active reservation row can hold zero money for incoming financing. Quote amount_minor, not the operation's loan principal as reserved cash.",
        "extensions": "WAITING_OBSERVED_CONFIRMATION means no supplier decision has been observed; it does not prove rejection or lack of actual agreement.",
        "invoices": "Invoice recognition is not cash. Observed settlement and allocation are separate; payment does not automatically reconcile this invoice. Aggregate cash and receivables alone cannot prove a particular invoice's payment status.",
        "obligations": "This registry can include incoming receivables and outgoing payables. A sum across both directions is not the company's debt or funding need; use metrics for payable/receivable totals separately.",
        "financing_products": "Catalog terms and known eligibility checks are not lender approval. OWNER approval authorizes one platform payment only; it cannot grant credit.",
        "reviews": "Use validation_diagnostic if present. Empty optional beneficiary/reference fields are not defects by themselves. Rejected rows do not invalidate already accepted rows.",
    }
    if dataset in notes:
        result["interpretation_scope"] = notes[dataset]
    if "total_characters" in value:
        result["length_scope"] = (
            "total_characters counts serialized JSON record including metadata, not document text length"
        )
    return result


def errors(text: str, outputs: list[Json], task: str = "") -> list[str]:
    """Narrow contradiction checks; do not advertise universal semantic validation."""
    result = []
    if re.search(r"受保护|protected|защищ", task, re.I) and re.search(
        r"唯一(?:合规)?(?:路径|办法|方式).{0,100}(?:修改|取消|移除|关闭).{0,30}保护"
        r"|(?:to (?:postpone|defer)|only (?:compliant )?(?:path|way)).{0,100}(?:remove|disable|change|modify).{0,60}(?:protect|policy)"
        r"|(?:чтобы (?:отложить|перенести)|единственн\w* (?:путь|способ)).{0,100}(?:отключ|снять|измен).{0,60}(?:защит|политик)",
        text,
        re.I,
    ):
        result.append(
            "Do not recommend changing/removing payment protections as a workaround. Explain the protected-payment restriction and allowed alternatives within the existing policy; omit claims of a unique compliant workaround."
        )
    rows = [o["output"]["result"] for o in outputs if o["output"].get("status") == "OK"]
    jobs = [r for v in rows if v.get("dataset") == "jobs" for r in v.get("records", [])]
    clauses = re.split(r"[.!?\n]", text)
    incoming = [
        v
        for v in rows
        if isinstance(v.get("payload"), dict) and v["payload"].get("kind") == "DRAW_LOAN"
    ]
    if incoming:
        for s in clauses:
            if not re.search(r"\bне\b|\bnot\b|погаш|repay", s, re.I) and re.search(
                r"кредитору.{0,30}со сч[её]та|(?:плат[её]ж|выплат\w*|перевод) кредитору|сумма (?:уже )?зарезервирован|payment to (?:the )?lender",
                s,
                re.I,
            ):
                result.append(
                    "DRAW_LOAN is incoming money to the company, not payment to its lender. RESERVED alone does not establish any reserved cash amount; omit unobserved cash-hold claims."
                )
    for token in re.findall(r"\bSETTLED_AND_[A-Z_]+\b", text):
        if token != "SETTLED_AND_RECONCILED":
            result.append(
                "Copy the observed completion_predicate exactly; do not invent compound protocol statuses."
            )
    if jobs and all(r.get("finished") == 0 for r in jobs):
        for s in clauses:
            if re.search(r"\bjobs?\b|задач\w*|задани\w*", s, re.I) and re.search(
                r"completed|finished|выполнен|завершен|завершён", s, re.I
            ):
                if not re.search(
                    r"NOT_COMPLETED|не\s+(?:был[ао]?\s+)?(?:выполнен|заверш[её]н)|not\s+(?:yet\s+)?(?:completed|finished)",
                    s,
                    re.I,
                ):
                    result.append(
                        "Observed jobs are NOT_COMPLETED. Actor names and absence of errors do not prove execution; use finished_state reference."
                    )
    if any(
        o["output"].get("error", {}).get("code") == "NOT_FOUND"
        for o in outputs
        if o["output"].get("error")
    ):
        if re.search(
            r"не связан\w* с времен|не из-за времен|not (?:due to|because of) (?:the )?(?:time|cutoff)",
            text,
            re.I,
        ):
            result.append(
                "NOT_FOUND does not establish why a source is unavailable; do not rule out observation cutoff or permissions."
            )
    for s in clauses:
        if re.search(r"кредитн\w* одобрени|lender approval|credit approval", s, re.I) and re.search(
            r"OWNER|владел|owner", s, re.I
        ):
            if not re.search(r"\bне\b|\bnot\b|не равн|отдельн|different|distinct", s, re.I):
                result.append(
                    "OWNER payment authorization is distinct from lender credit approval. Catalog eligibility grants neither."
                )
    if any(v.get("dataset") == "reviews" for v in rows) and re.search(
        r"код(?: ошибки)?\s*[:—-]?\s*\d+", text, re.I
    ):
        result.append(
            "The observed quarantine error code is a named parser code, not a count or row number. Quote its code reference or omit it."
        )
    return list(dict.fromkeys(result))
