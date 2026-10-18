"""Human import: upload -> column mapping -> normalized preview -> review -> commit.

Two defined templates (generic upload, NOT a bank integration):
  transactions: settled bank movements (date, signed amount or debit/credit, counterparty, reference)
  obligations:  payables/receivables (kind, reference, counterparty, amount, due date)

Values are typed by people in major units ("30 000.00", "¥1,234.50", "(500)"). The
server converts them to integer minor units with Decimal, never float. Ambiguous decimal
separators and dates are reported, not guessed. Commit converts accepted rows to the
existing synthetic-csv-v1 contract and goes through import_csv (quarantine, versions,
source hash). The raw upload and the mapping version are stored for provenance.
"""

from __future__ import annotations

import base64
import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Any
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from finance.domain import AuthContext, FinanceError, Json, canonical, digest, require, uid
from finance.ingestion import COLUMNS, import_csv, snapshot
from finance.store import Store

MAPPING_VERSION = "mapping-v1"
SHANGHAI = timezone(timedelta(hours=8))
MAX_BYTES, MAX_ROWS = 1_000_000, 5000
TEMPLATES: dict[str, dict[str, Any]] = {
    "transactions": {
        "required": ["date", "counterparty"],
        "optional": ["amount", "debit", "credit", "reference", "description"],
        "hint": "Settled bank movements. Positive = money in.",
    },
    "obligations": {
        "required": ["reference", "counterparty", "amount", "due_date"],
        "optional": ["kind", "issued_date", "protected"],
        "hint": "Confirmed invoices you must pay (PAYABLE) or expect to receive (RECEIVABLE).",
    },
}
SYNONYMS = {
    "date": [
        "date",
        "booking date",
        "value date",
        "transaction date",
        "日期",
        "交易日期",
        "记账日期",
        "дата",
    ],
    "amount": ["amount", "sum", "金额", "交易金额", "сумма"],
    "debit": ["debit", "withdrawal", "支出", "借方", "списание", "расход"],
    "credit": ["credit", "deposit", "收入", "贷方", "поступление", "приход"],
    "counterparty": [
        "counterparty",
        "payee",
        "payer",
        "customer",
        "supplier",
        "name",
        "对方",
        "对方户名",
        "客户",
        "供应商",
        "контрагент",
    ],
    "reference": [
        "reference",
        "ref",
        "invoice",
        "invoice no",
        "number",
        "id",
        "单号",
        "发票号",
        "编号",
        "номер",
        "счёт",
        "счет",
    ],
    "description": ["description", "memo", "摘要", "备注", "назначение", "описание"],
    "due_date": ["due", "due date", "due_at", "到期日", "付款日期", "срок", "срок оплаты"],
    "issued_date": ["issued", "issue date", "invoice date", "开票日期", "дата выставления"],
    "kind": ["kind", "type", "direction", "类型", "тип"],
    "protected": ["protected", "critical", "priority", "保护", "защищено"],
}
DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "YYYY/MM/DD": "%Y/%m/%d",
    "DD.MM.YYYY": "%d.%m.%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY年MM月DD日": "%Y年%m月%d日",
}


# ---------------------------------------------------------------- reading files


def read_table(value: Json) -> tuple[list[str], list[list[str]], bytes, str]:
    fmt = value.get("format", "csv")
    require(fmt in {"csv", "xlsx"}, "UNSUPPORTED_SCHEMA", "CSV or XLSX only")
    if fmt == "csv":
        text = value.get("content")
        require(
            isinstance(text, str) and 0 < len(text.encode()) <= MAX_BYTES,
            "INVALID_FILE",
            "CSV up to 1 MB",
        )
        assert isinstance(text, str)
        raw = text.encode("utf-8")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
        rows = [r for r in csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter)]
    else:
        content = value.get("content_base64")
        require(
            isinstance(content, str) and len(content) <= MAX_BYTES * 4 // 3 + 8,
            "INVALID_FILE",
            "XLSX up to 1 MB",
        )
        assert isinstance(content, str)
        try:
            raw = base64.b64decode(content, validate=True)
        except ValueError as exc:
            raise FinanceError("INVALID_FILE", "Invalid file encoding") from exc
        rows = read_xlsx(raw)
        delimiter = "xlsx"
    rows = [r for r in rows if any(c.strip() for c in r)]
    require(len(rows) >= 2, "INVALID_FILE", "A header row and at least one data row are required")
    require(len(rows) - 1 <= MAX_ROWS, "INVALID_FILE", "Row limit is 5000")
    headers = [h.strip() for h in rows[0]]
    require(
        len(set(headers)) == len(headers) and all(headers),
        "INVALID_FILE",
        "Headers must be unique and non-empty",
    )
    width = len(headers)
    body = [(r + [""] * width)[:width] for r in rows[1:]]
    return headers, body, raw, delimiter


def read_xlsx(raw: bytes) -> list[list[str]]:
    """First worksheet only, values only (no formulas evaluated, no macros, bounded size)."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            total = sum(i.file_size for i in z.infolist())
            require(
                total <= 20 * MAX_BYTES, "INVALID_FILE", "Workbook expands beyond the safe limit"
            )
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            shared: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall(
                    "m:si", ns
                ):
                    shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
            sheets = sorted(
                n for n in z.namelist() if re.match(r"^xl/worksheets/sheet\d+\.xml$", n)
            )
            require(bool(sheets), "INVALID_FILE", "No worksheet found")
            root = ElementTree.fromstring(z.read(sheets[0]))
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as exc:
        raise FinanceError("INVALID_FILE", "Not a readable XLSX workbook") from exc
    rows: list[list[str]] = []
    for row in root.iter("{%s}row" % ns["m"]):
        cells: dict[int, str] = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            letters = re.match(r"[A-Z]{0,3}", ref).group(0)  # type: ignore[union-attr]
            for ch in letters:
                col = col * 26 + ord(ch) - 64
            require(col <= 16384, "INVALID_FILE", "Cell reference outside the worksheet")
            kind, v = c.get("t"), c.find("m:v", ns)
            if kind == "s" and v is not None:
                try:
                    text = shared[int(v.text or 0)]
                except (ValueError, IndexError) as exc:
                    raise FinanceError("INVALID_FILE", "Broken shared-string reference") from exc
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter("{%s}t" % ns["m"]))
            else:
                text = v.text if v is not None and v.text else ""
                if c.get("s") and re.fullmatch(r"\d{5}(\.0+)?", text or ""):
                    text = "serial:" + text.split(".")[0]  # likely a date; parsed explicitly below
            cells[max(col - 1, 0)] = text
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
        require(len(rows) <= MAX_ROWS + 1, "INVALID_FILE", "Row limit is 5000")
    return rows


# ---------------------------------------------------------------- normalization


def suggest(headers: list[str], template: str) -> dict[str, str | None]:
    fields = TEMPLATES[template]["required"] + TEMPLATES[template]["optional"]
    result: dict[str, str | None] = {}
    lowered = {h: h.strip().lower() for h in headers}
    for field in fields:
        names = SYNONYMS.get(field, [field])
        match = next((h for h, l in lowered.items() if l in names), None) or next(
            (h for h, l in lowered.items() if any(n in l for n in names if len(n) > 2)), None
        )
        result[field] = match if match not in result.values() else None
    return result


def parse_amount(text: str, decimal: str) -> int:
    value = text.strip()
    negative = value.startswith("(") and value.endswith(")")
    value = re.sub(r"(CNY|RMB|¥|￥|元|\s| |')", "", value.strip("()"))
    if value.startswith("-"):
        negative, value = not negative, value[1:]
    elif value.startswith("+"):
        value = value[1:]
    require(bool(value), "INVALID_AMOUNT", "Empty amount")
    other = "," if decimal == "." else "."
    if re.fullmatch(r"\d{1,3}[.,]\d{3}", value):
        raise FinanceError(
            "AMBIGUOUS_DECIMAL", "Could be a thousands separator or decimals; confirm the separator"
        )
    if decimal == ".":
        if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?|\d+(\.\d+)?", value) is None:
            raise FinanceError(
                "AMBIGUOUS_DECIMAL" if re.fullmatch(r"\d+,\d{1,2}", value) else "INVALID_AMOUNT",
                "Amount does not match the chosen '.' decimal separator",
            )
        value = value.replace(",", "")
    else:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?|\d+(,\d+)?", value) is None:
            raise FinanceError(
                "AMBIGUOUS_DECIMAL" if re.fullmatch(r"\d+\.\d{1,2}", value) else "INVALID_AMOUNT",
                "Amount does not match the chosen ',' decimal separator",
            )
        value = value.replace(".", "").replace(",", ".")
    del other
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise FinanceError("INVALID_AMOUNT", "Not a decimal amount") from exc
    require(
        amount == amount.quantize(Decimal("0.01")), "INVALID_AMOUNT", "More than 2 decimal places"
    )
    result = int(amount * 100)
    require(result < 10**15, "INVALID_AMOUNT", "Amount outside supported range")
    return -result if negative else result


def parse_date(text: str, fmt: str) -> date:
    value = text.strip()
    if value.startswith("serial:"):
        return date(1899, 12, 30) + timedelta(days=int(value[7:]))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", value):
        return date.fromisoformat(value[:10])
    if fmt == "auto":
        hits = set()
        for pattern in DATE_FORMATS.values():
            try:
                hits.add(datetime.strptime(value, pattern).date())
            except ValueError:
                continue
        require(
            len(hits) <= 1,
            "AMBIGUOUS_DATE",
            "Date could be day-first or month-first; choose the date format",
        )
        require(len(hits) == 1, "INVALID_DATE", "Unrecognized date")
        return hits.pop()
    require(fmt in DATE_FORMATS, "INVALID_ARGUMENTS", "Unknown date format")
    try:
        return datetime.strptime(value, DATE_FORMATS[fmt]).date()
    except ValueError as exc:
        raise FinanceError("INVALID_DATE", "Date does not match the chosen format") from exc


def business_midnight(day: date) -> str:
    return (
        datetime(day.year, day.month, day.day, tzinfo=SHANGHAI)
        .astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
    )


def normalize(store: Store, ctx: AuthContext, value: Json) -> Json:
    template = value.get("template")
    require(
        template in TEMPLATES, "INVALID_ARGUMENTS", "Template must be transactions or obligations"
    )
    assert isinstance(template, str)
    headers, body, raw, delimiter = read_table(value)
    mapping = value.get("mapping") or suggest(headers, template)
    require(isinstance(mapping, dict), "INVALID_ARGUMENTS", "Mapping must be an object")
    fields = TEMPLATES[template]["required"] + TEMPLATES[template]["optional"]
    require(set(mapping) <= set(fields), "INVALID_ARGUMENTS", "Unknown target field")
    require(
        all(v is None or v in headers for v in mapping.values()),
        "INVALID_ARGUMENTS",
        "Mapped column not in file",
    )
    options: dict[str, Any] = {
        "decimal": ".",
        "date_format": "auto",
        "kind": None,
        "namespace": "upload_" + template,
    } | (value.get("options") or {})
    require(
        options["decimal"] in {".", ","}, "INVALID_ARGUMENTS", "Decimal separator must be . or ,"
    )
    require(
        options["date_format"] == "auto" or options["date_format"] in DATE_FORMATS,
        "INVALID_ARGUMENTS",
        "Unknown date format",
    )
    require(
        options["kind"] in {None, "PAYABLE", "RECEIVABLE"},
        "INVALID_ARGUMENTS",
        "Kind must be PAYABLE or RECEIVABLE",
    )
    require(
        isinstance(options["namespace"], str)
        and re.fullmatch(r"[a-z0-9_]{3,40}", options["namespace"]) is not None
        and options["namespace"] != "sandbox",
        "INVALID_ARGUMENTS",
        "Namespace: 3–40 lowercase letters, digits, _",
    )
    missing = [f for f in TEMPLATES[template]["required"] if not mapping.get(f)]
    if (
        template == "transactions"
        and not mapping.get("amount")
        and not (mapping.get("debit") or mapping.get("credit"))
    ):
        missing.append("amount or debit/credit")
    if template == "obligations" and not mapping.get("kind") and not options["kind"]:
        missing.append("kind (column or fixed choice)")
    snap = snapshot(store, ctx)
    clock = snap["as_of"]
    existing = {(f["provider"], f["kind"], f["external_id"]): f for f in snap["facts"]}
    rows: list[Json] = []
    for number, cells in enumerate(body, 2):
        cell = {f: cells[headers.index(c)] if c else "" for f, c in mapping.items()}
        item: Json = {"row": number, "raw": dict(zip(headers, cells)), "errors": [], "warnings": []}
        try:
            if missing:
                raise FinanceError("MAPPING_INCOMPLETE", "Map: " + ", ".join(missing))
            if template == "transactions":
                if cell.get("amount"):
                    amount = parse_amount(cell["amount"], options["decimal"])
                else:
                    credit = (
                        parse_amount(cell["credit"], options["decimal"])
                        if cell.get("credit")
                        else 0
                    )
                    debit = (
                        parse_amount(cell["debit"], options["decimal"]) if cell.get("debit") else 0
                    )
                    require(
                        not (credit and debit), "INVALID_AMOUNT", "Both debit and credit are filled"
                    )
                    amount = credit - abs(debit)
                require(amount != 0, "INVALID_AMOUNT", "Zero movement")
                day = parse_date(cell["date"], options["date_format"])
                when = business_midnight(day)
                require(
                    when <= clock,
                    "FUTURE_TRANSACTION",
                    "A settled movement cannot be after the business clock",
                )
                ref = (cell.get("reference") or "").strip() or "tx_" + digest([number, cells])[:12]
                item["normalized"] = {
                    "kind": "TRANSACTION",
                    "external_id": ref,
                    "amount_minor": amount,
                    "event_time": when,
                    "due_at": "",
                    "counterparty": cell["counterparty"].strip()[:80],
                    "status": "SETTLED",
                    "reference": (cell.get("description") or "")[:120],
                    "protected": "false",
                }
                item["warnings"].append(
                    "Settled movements change confirmed cash. The sandbox bank must observe them too, or reconciliation will stop new sends."
                )
            else:
                kind = (options["kind"] or cell.get("kind", "")).strip().upper()
                kind = {
                    "AP": "PAYABLE",
                    "PAY": "PAYABLE",
                    "应付": "PAYABLE",
                    "AR": "RECEIVABLE",
                    "RECEIVE": "RECEIVABLE",
                    "应收": "RECEIVABLE",
                }.get(kind, kind)
                require(
                    kind in {"PAYABLE", "RECEIVABLE"},
                    "INVALID_ROW",
                    "Kind must be PAYABLE or RECEIVABLE",
                )
                amount = parse_amount(cell["amount"], options["decimal"])
                require(amount > 0, "INVALID_AMOUNT", "Obligation amount must be positive")
                due = business_midnight(parse_date(cell["due_date"], options["date_format"]))
                issued = (
                    business_midnight(parse_date(cell["issued_date"], options["date_format"]))
                    if cell.get("issued_date")
                    else clock
                )
                ref = cell["reference"].strip()
                require(
                    0 < len(ref) <= 120 and re.fullmatch(r"[^\s,]+", ref) is not None,
                    "INVALID_ROW",
                    "Reference without spaces/commas required",
                )
                party = cell["counterparty"].strip()[:80]
                protected = str(cell.get("protected", "")).strip().lower() in {
                    "true",
                    "yes",
                    "1",
                    "y",
                    "是",
                    "да",
                }
                item["normalized"] = {
                    "kind": kind,
                    "external_id": ref,
                    "amount_minor": amount,
                    "event_time": min(issued, clock),
                    "due_at": due,
                    "counterparty": party,
                    "status": "CONFIRMED",
                    "reference": "",
                    "protected": "true" if protected else "false",
                }
                if kind == "PAYABLE" and party not in {"salary", "rent", "supplier"}:
                    item["warnings"].append(
                        "No verified beneficiary for this counterparty: payments stay blocked until one is verified."
                    )
            norm = item["normalized"]
            prior = existing.get((options["namespace"], norm["kind"], norm["external_id"]))
            norm["version"] = (prior["version"] + 1) if prior else 1
            if prior:
                pv = prior["value"]
                changes = {
                    k: [pv.get(k), norm[k]]
                    for k in ("amount_minor", "due_at", "counterparty")
                    if pv.get(k) != norm[k]
                }
                item["update"] = {"from_version": prior["version"], "changes": changes}
                if not changes:
                    item["warnings"].append(
                        "Identical to the current version; it will be skipped by version rules."
                    )
            item["display"] = (
                f"{'-' if norm['amount_minor'] < 0 else ''}CNY {abs(norm['amount_minor']) // 100:,}.{abs(norm['amount_minor']) % 100:02d}"
            )
        except FinanceError as exc:
            item["errors"].append({"code": exc.code, "text": exc.safe_message})
        rows.append(item)
    ok = [r for r in rows if not r["errors"]]
    return {
        "template": template,
        "mapping_version": MAPPING_VERSION,
        "headers": headers,
        "mapping": mapping,
        "suggested": suggest(headers, template),
        "options": options,
        "delimiter": delimiter,
        "missing": missing,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "ready": len(ok),
            "errors": len(rows) - len(ok),
            "updates": sum(1 for r in ok if r.get("update")),
            "total_minor": sum(r["normalized"]["amount_minor"] for r in ok),
        },
        "raw_digest": digest(raw.hex()),
        "_raw": raw,
        "_clock": clock,
    }


def preview(store: Store, ctx: AuthContext, value: Json) -> Json:
    with store.connect() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
    result = normalize(store, ctx, value)
    result.pop("_raw"), result.pop("_clock")
    return result


def commit(store: Store, ctx: AuthContext, value: Json) -> Json:
    require(value.get("confirm") is True, "INVALID_ARGUMENTS", "Explicit confirmation required")
    result = normalize(store, ctx, value)
    require(
        value.get("raw_digest") == result["raw_digest"],
        "STALE_PREVIEW",
        "File changed since the preview",
    )
    require(not result["missing"], "MAPPING_INCOMPLETE", "Complete the mapping first")
    raw, clock = result["_raw"], result["_clock"]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    for r in result["rows"]:
        if r["errors"]:
            # Keep the row visible in quarantine instead of dropping it silently.
            writer.writerow(
                {c: "" for c in COLUMNS}
                | {
                    "kind": "INVALID",
                    "external_id": f"row_{r['row']}",
                    "version": "1",
                    "currency": "CNY",
                    "protected": "false",
                    "status": "CONFIRMED",
                    "reference": canonical(r["errors"])[:200],
                    "event_time": clock,
                    "observed_time": clock,
                    "amount_minor": "0",
                }
            )
            continue
        n = r["normalized"]
        writer.writerow(
            {
                "kind": n["kind"],
                "external_id": n["external_id"],
                "version": str(n["version"]),
                "event_time": n["event_time"],
                "observed_time": clock,
                "amount_minor": str(n["amount_minor"]),
                "currency": "CNY",
                "due_at": n["due_at"],
                "counterparty": n["counterparty"],
                "beneficiary_version": (n["counterparty"] + "_v1")
                if n["kind"] == "PAYABLE" and n["counterparty"] in {"salary", "rent", "supplier"}
                else "",
                "reference": n["reference"],
                "protected": n["protected"],
                "status": n["status"],
            }
        )
    namespace = result["options"]["namespace"]
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        raw_source, _ = store.source(db, ctx.tenant_id, "raw_upload_" + namespace, raw, clock)
    imported = import_csv(
        store,
        ctx,
        out.getvalue().encode("utf-8"),
        namespace,
        clock,
        value.get("closing_balance_minor"),
    )
    record = {
        "mapping_version": MAPPING_VERSION,
        "template": result["template"],
        "mapping": result["mapping"],
        "options": result["options"],
        "raw_source_id": raw_source,
        "import": imported,
        "summary": result["summary"],
        "actor": ctx.user_id,
    }
    with store.transaction() as db:
        store.authorize(db, ctx, {"OWNER", "ACCOUNTANT"})
        store.put_object(db, ctx.tenant_id, "import_mapping", uid("import_mapping"), record)
        store.audit(
            db,
            ctx.tenant_id,
            "import.mapped",
            {"import_id": imported.get("import_id"), "raw_source_id": raw_source},
        )
    return record
