"""Render sandbox operation logs from recorded runs as a reviewer-facing Markdown page."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cny(minor: int) -> str:
    sign = "−" if minor < 0 else ""
    return f"{sign}CNY {abs(minor) // 100:,}.{abs(minor) % 100:02d}"


def golden_section(golden: dict) -> list[str]:
    lines = [
        "## 1. Golden scenario with a lost bank response",
        "",
        "Source: `artifacts/golden-latest.json` (`python -m scripts.demo --lost-response`).",
        f"Mode: {golden['mode']} · model: {golden['model_provider']} · approvals: {golden['approval_mode']}.",
        "",
        "| # | Business date | Action | Amount | Idempotency key | Approval payload hash | After send |",
        "|---|---|---|---|---|---|---|",
    ]
    for n, item in enumerate(golden["timeline"], 1):
        c = item["command"]
        target = c.get("obligation_id") or c["beneficiary_version_id"]
        lines.append(
            f"| {n} | {c['at'][:10]} | {c['kind']} {target} | {cny(c['amount_minor'])} "
            f"| `{c['idempotency_key']}` | `{item['approval']['payload_hash'][:16]}…` "
            f"| {item['after_send']} |"
        )
    ev, rec, plan = (
        golden["independent_evaluation"],
        golden["reconciliation"],
        golden["plan_status"],
    )
    lines += [
        "",
        "UNKNOWN means the sandbox accepted the payment but the response was lost on purpose.",
        "The worker found each one by the same key; no second payment was sent.",
        "",
        "| Result | Value |",
        "|---|---|",
        f"| Plan | {plan['status']}, {plan['settled_actions']}/{plan['total_actions']} actions settled |",
        f"| Reconciliation | {rec['status']}, local {cny(rec['local_cash_minor'])} = bank {cny(rec['provider_cash_minor'])}, discrepancy {cny(rec['discrepancy_minor'])} |",
        f"| Independent evaluator ({ev['evaluator_version']}) | final cash {cny(ev['final_cash_minor'])}, lowest {cny(ev['minimum_cash_minor'])}, "
        f"open payables {cny(ev['remaining_payables_minor'])}, open debt {cny(ev['remaining_debt_minor'])}, "
        f"{ev['movement_count']} bank movements, missed deadlines {len(ev['missed_deadlines'])} |",
        f"| Hash-chained audit records | {len(golden['audit'])} |",
        "",
    ]
    return lines


def e2e_section(e2e: dict) -> list[str]:
    lines = [
        "## 2. Product path through the real server, worker and sandbox",
        "",
        "Source: `artifacts/v03/e2e-latest.json` (`python -m scripts.e2e_v03`).",
        f"Scope: {e2e['scope']}.",
        "",
        "| Step | Details |",
        "|---|---|",
    ]
    for step in e2e["steps"]:
        details = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v}"
            for k, v in step.items()
            if k not in {"at", "step"}
        )
        lines.append(f"| {step['step']} | {details.replace('|', '/')} |")
    passed = sum(1 for v in e2e["checks"].values() if v)
    lines += [
        "",
        f"Checks: **{passed}/{len(e2e['checks'])} PASSED** (overall {'PASSED' if e2e['passed'] else 'FAILED'}).",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    lines += [f"| {k} | {'PASSED' if v else 'FAILED'} |" for k, v in e2e["checks"].items()]
    lines += ["", "Not covered: " + "; ".join(e2e["not_covered"]) + ".", ""]
    return lines


def anchor_section(path: Path) -> list[str]:
    lines = ["## 3. On-chain anchors", ""]
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not entries:
        return lines + [
            "No anchor recorded yet. Run `python -m scripts.anchor_audit send`, then",
            "`verify --tx <hash>`; results are appended to `artifacts/onchain-anchors.json`.",
            "",
        ]
    lines += [
        "The head of the hash-chained audit log is published as the data of a",
        "zero-value transaction on a public testnet; only hashes leave the machine.",
        "`verify` reads the transaction back and recomputes the local chain, so a",
        "rewritten and re-hashed audit history no longer matches. The transaction",
        "can be checked independently in the block explorer link below.",
        "",
        "Source: `artifacts/onchain-anchors.json` (`python -m scripts.anchor_audit`).",
        "",
        "| When | Command | Network | Transaction | Records covered | Chain head | Result |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        result = e.get("status") or ("VALID" if e.get("valid") else "INVALID")
        lines.append(
            f"| {e['at'][:19]} | {e['command']} | {e.get('network', '')} "
            f"| [{e['tx_hash'][:14]}…]({e['explorer_url']}) | {e.get('audit_count')} "
            f"| `{str(e.get('head_hash'))[:16]}…` | {result} |"
        )
    return lines + [""]


def identity_section() -> list[str]:
    """Before/after runs of the settlement-identity tests (risk K15)."""
    folder = ROOT / "artifacts/settlement-fix-20261019"
    runs = []
    for name in ("before.json", "targeted-final.json"):
        path = folder / name
        if path.exists():
            runs.append((name, json.loads(path.read_text(encoding="utf-8"))))
    if not runs:
        return []
    lines = [
        "## 4. Bank-fault safety: wrong settlement identity",
        "",
        "The sandbox can report a settlement with the right amount but the wrong",
        "counterparty or obligation reference. The reconciler must not mark the",
        "action SETTLED, must keep the reserve and must stop further sends.",
        "",
        "| Run | Code | Tests | Result |",
        "|---|---|---|---|",
    ]
    labels = {"before.json": "before the fix", "targeted-final.json": "after the fix"}
    for name, run in runs:
        counts = ", ".join(f"{k} {v}" for k, v in sorted(run["test_counts"].items()))
        lines.append(
            f"| {run['started_at'][:19]} | {labels[name]} | {run['tests_run']} "
            f"| {counts} (`artifacts/settlement-fix-20261019/{name}`) |"
        )
    return lines + [
        "",
        "Design: [ADR 0006](../adr/0006-settlement-identity.md); tests:",
        "`tests/test_settlement_identity.py`.",
        "",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/submission/EXECUTION_EVIDENCE.md")
    args = parser.parse_args()
    golden = json.loads((ROOT / "artifacts/golden-latest.json").read_text(encoding="utf-8"))
    e2e = json.loads((ROOT / "artifacts/v03/e2e-latest.json").read_text(encoding="utf-8"))
    lines = [
        "# Execution evidence: sandbox operation logs",
        "",
        "Topic E is a non-on-chain topic, so the required execution evidence is",
        "simulated-account (sandbox) operation logs and the demo video. All data is",
        "synthetic; the bank is an independent sandbox process with its own database.",
        "",
        "| Evidence | Where |",
        "|---|---|",
        "| Golden scenario: 5 payments, one deliberately lost bank response | [section 1](#1-golden-scenario-with-a-lost-bank-response), `artifacts/golden-latest.json` |",
        "| Product path through the real HTTP server, worker and sandbox bank | [section 2](#2-product-path-through-the-real-server-worker-and-sandbox), `artifacts/v03/e2e-latest.json` |",
        "| On-chain transaction hashes (challenge bonus) | [section 3](#3-on-chain-anchors), `artifacts/onchain-anchors.json` |",
        "| Bank-fault safety: wrong settlement identity | [section 4](#4-bank-fault-safety-wrong-settlement-identity) |",
        "| Demo video (≤ 5 min) | Submitted with the presentation; script in [demo-script.md](demo-script.md) |",
        "",
        "Every table below is generated from the raw artifacts by",
        "`python -m scripts.execution_log` after `python -m scripts.demo --lost-response`",
        "and `python -m scripts.e2e_v03`; nothing is typed by hand.",
        "",
        *golden_section(golden),
        *e2e_section(e2e),
        *anchor_section(ROOT / "artifacts/onchain-anchors.json"),
        *identity_section(),
    ]
    (ROOT / args.output).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
