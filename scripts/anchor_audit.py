"""Anchor the audit-chain head on a public testnet, or verify an anchor against local records.

    python -m scripts.anchor_audit wallet               # create/show the testnet wallet address
    python -m scripts.anchor_audit send                 # anchor the current chain head
    python -m scripts.anchor_audit verify --tx 0x...    # check an anchor against local audit
Sending needs `pip install -r requirements-onchain.txt` and testnet coins from a faucet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from finance import anchor
from finance.store import Store

RPC = {
    "sepolia": "https://ethereum-sepolia-rpc.publicnode.com",
    "base-sepolia": "https://sepolia.base.org",
}


def open_store(directory: Path) -> Store:
    pg_config = directory / "postgres.secret.json"
    if pg_config.exists():
        from finance.postgres import PostgresStore

        config = json.loads(pg_config.read_text(encoding="utf-8"))
        return PostgresStore(config["dsn"], directory / "observed")
    return Store(directory / "observed/finance.db")


def wallet(directory: Path, create: bool) -> str:
    path = directory / "anchor-wallet.secret.json"
    if not path.exists():
        if not create:
            raise SystemExit(
                f"No testnet wallet at {path}; run: python -m scripts.anchor_audit wallet"
            )
        from eth_account import Account

        account = Account.create()
        path.write_text(
            json.dumps({"address": account.address, "private_key": account.key.hex()}),
            encoding="utf-8",
        )
    return str(json.loads(path.read_text(encoding="utf-8"))["address"])


EVIDENCE = Path("artifacts/onchain-anchors.json")


def record_evidence(command: str, result: dict) -> None:
    """Append public facts only (hashes, links, check results) for reviewers."""
    entries = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.exists() else []
    keep = ("tx_hash", "network", "chain_id", "explorer_url", "status", "valid", "checks")
    entry = {"command": command} | {k: result[k] for k in keep if k in result}
    entry["audit_count"] = result.get("audit_count", result.get("anchored_count"))
    entry["head_hash"] = result.get("head_hash", result.get("anchored_head"))
    entry["at"] = result.get("anchored_at") or anchor.now()
    EVIDENCE.write_text(json.dumps(entries + [entry], indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["wallet", "send", "verify", "status"])
    parser.add_argument("--directory", default=".runtime/workspace")
    parser.add_argument("--network", choices=sorted(RPC), default="sepolia")
    parser.add_argument("--rpc-url", help="Override the public RPC endpoint")
    parser.add_argument("--tx", help="Transaction hash to verify")
    args = parser.parse_args()
    directory = Path(args.directory)
    tokens = json.loads((directory / "local-login.secret.json").read_text(encoding="utf-8"))
    store = open_store(directory)
    if args.command == "wallet":
        address = wallet(directory, create=True)
        print(json.dumps({"address": address, "fund_with": "testnet faucet only"}, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(anchor.latest(store, store.authenticate(tokens["AUDITOR"])), indent=2))
        return 0
    rpc = anchor.http_rpc(args.rpc_url or RPC[args.network])
    if args.command == "send":
        wallet(directory, create=False)
        key = json.loads((directory / "anchor-wallet.secret.json").read_text(encoding="utf-8"))
        result = anchor.anchor(
            store,
            store.authenticate(tokens["OWNER"]),
            rpc,
            key["private_key"],
            anchor.receipt_waiter(rpc),
        )
    else:
        if not args.tx:
            parser.error("verify needs --tx")
        result = anchor.verify(store, store.authenticate(tokens["AUDITOR"]), rpc, args.tx)
    record_evidence(args.command, result)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", True) else 1


if __name__ == "__main__":
    sys.exit(main())
