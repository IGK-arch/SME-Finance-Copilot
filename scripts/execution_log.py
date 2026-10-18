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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/submission/EXECUTION_EVIDENCE.md")
    args = parser.parse_args()
    golden = json.loads((ROOT / "artifacts/golden-latest.json").read_text(encoding="utf-8"))
    e2e = json.loads((ROOT / "artifacts/v03/e2e-latest.json").read_text(encoding="utf-8"))
    lines = [
        "# Execution evidence: sandbox operation logs",
        "",
        "Topic E is a non-on-chain topic, so execution evidence is simulated-account",
        "operation logs; section 3 lists the on-chain anchors made for the challenge bonus. All data is synthetic; the bank is an independent sandbox process",
        "with its own database. Regenerate this page with `python -m scripts.execution_log`",
        "after re-running the two commands below.",
        "",
        *golden_section(golden),
        *e2e_section(e2e),
        *anchor_section(ROOT / "artifacts/onchain-anchors.json"),
    ]
    (ROOT / args.output).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
