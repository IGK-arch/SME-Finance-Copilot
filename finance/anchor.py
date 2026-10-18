"""Public-testnet anchoring of the hash-chained audit log (on-chain proof of integrity).

Only hashes leave the machine: a fixed tag, a salted tenant tag, the number of audit
records covered and the chain head. No amounts, names or identifiers are published.
Mainnet is refused; the wallet holds testnet coins only and never touches business money.
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable
from urllib.request import Request, urlopen

from finance.domain import AuthContext, FinanceError, Json, digest, now, require
from finance.store import Store

MAGIC = b"SMEAUDIT1"
PAYLOAD_BYTES = len(MAGIC) + 16 + 8 + 32
ANCHOR_ROLES = {"OWNER", "ADMIN"}
TESTNETS: dict[int, Json] = {
    11155111: {"name": "Ethereum Sepolia", "explorer": "https://sepolia.etherscan.io/tx/"},
    84532: {"name": "Base Sepolia", "explorer": "https://sepolia.basescan.org/tx/"},
}
Rpc = Callable[[str, list], object]


def tenant_tag(tenant_id: str) -> bytes:
    return hashlib.sha256(b"sme-anchor-tenant:" + tenant_id.encode()).digest()[:16]


def encode(tenant_id: str, count: int, head_hash: str) -> str:
    require(0 < count < 2**64, "INVALID_ANCHOR", "Anchor needs at least one audit record")
    head = bytes.fromhex(head_hash)
    require(len(head) == 32, "INVALID_ANCHOR", "Head hash must be 32 bytes")
    return "0x" + (MAGIC + tenant_tag(tenant_id) + count.to_bytes(8, "big") + head).hex()


def decode(data: str) -> Json:
    raw = bytes.fromhex(data.removeprefix("0x"))
    require(
        len(raw) == PAYLOAD_BYTES and raw.startswith(MAGIC),
        "INVALID_ANCHOR",
        "Transaction data is not an SME audit anchor",
    )
    body = raw[len(MAGIC) :]
    return {
        "tenant_tag": body[:16].hex(),
        "count": int.from_bytes(body[16:24], "big"),
        "head_hash": body[24:].hex(),
    }


def chain_prefix(store: Store, ctx: AuthContext, count: int | None = None) -> Json:
    """Recompute the audit chain and return the head after `count` records (default: all)."""
    rows = store.audit_log(ctx)
    previous = "0" * 64
    for n, row in enumerate(rows[:count] if count is not None else rows, 1):
        expected = digest(
            [previous, row["occurred_at"], row["event_type"], json.loads(row["payload"])]
        )
        if row["previous_hash"] != previous or row["event_hash"] != expected:
            return {"valid": False, "first_bad_audit_id": row["audit_id"], "checked": n - 1}
        previous = row["event_hash"]
    covered = min(count, len(rows)) if count is not None else len(rows)
    return {"valid": True, "count": covered, "head_hash": previous, "total": len(rows)}


def http_rpc(url: str, timeout: float = 30.0) -> Rpc:
    require(url.startswith("https://"), "INVALID_RPC", "Use an https RPC endpoint")
    state = {"id": 0}

    def call(method: str, params: list) -> object:
        state["id"] += 1
        body = json.dumps({"jsonrpc": "2.0", "id": state["id"], "method": method, "params": params})
        # Public RPC gateways reject urllib's default User-Agent with 403.
        headers = {"Content-Type": "application/json", "User-Agent": "sme-finance-copilot/0.3"}
        request = Request(url, body.encode(), headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                reply = json.loads(response.read())
        except OSError as error:
            raise FinanceError("RPC_UNREACHABLE", f"Cannot reach the RPC endpoint: {error}")
        require("error" not in reply, "RPC_ERROR", str(reply.get("error")))
        return reply["result"]

    return call


def testnet(rpc: Rpc) -> tuple[int, Json]:
    chain_id = int(str(rpc("eth_chainId", [])), 16)
    require(chain_id in TESTNETS, "MAINNET_REFUSED", f"Chain {chain_id} is not an allowed testnet")
    return chain_id, TESTNETS[chain_id]


def anchor(
    store: Store,
    ctx: AuthContext,
    rpc: Rpc,
    private_key: str,
    wait: Callable[[str], Json | None] | None = None,
) -> Json:
    """Sign and send a zero-value self-transaction whose data is the current chain head."""
    from eth_account import Account  # optional dependency: requirements-onchain.txt

    with store.connect() as db:
        store.authorize(db, ctx, ANCHOR_ROLES)
    head = chain_prefix(store, ctx)
    require(head["valid"], "AUDIT_BROKEN", "Refusing to anchor a broken audit chain")
    chain_id, net = testnet(rpc)
    account = Account.from_key(private_key)
    data = encode(ctx.tenant_id, head["count"], head["head_hash"])
    nonce = int(str(rpc("eth_getTransactionCount", [account.address, "pending"])), 16)
    block = rpc("eth_getBlockByNumber", ["latest", False])
    base_fee = int(str(block["baseFeePerGas"]), 16) if isinstance(block, dict) else 0
    tip = int(str(rpc("eth_maxPriorityFeePerGas", [])), 16)
    tx = {
        "chainId": chain_id,
        "nonce": nonce,
        "to": account.address,
        "value": 0,
        "data": data,
        "maxPriorityFeePerGas": tip,
        "maxFeePerGas": 2 * base_fee + tip,
    }
    tx["gas"] = int(str(rpc("eth_estimateGas", [{**tx, "from": account.address}])), 16)
    signed = Account.sign_transaction(tx, private_key)
    tx_hash = str(rpc("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()]))
    receipt = (wait or (lambda h: None))(tx_hash)
    require(
        receipt is None or int(str(receipt["status"]), 16) == 1,
        "ANCHOR_FAILED",
        "Anchor transaction reverted",
    )
    record = {
        "tx_hash": tx_hash,
        "chain_id": chain_id,
        "network": net["name"],
        "explorer_url": net["explorer"] + tx_hash,
        "from": account.address,
        "audit_count": head["count"],
        "head_hash": head["head_hash"],
        "block": int(str(receipt["blockNumber"]), 16) if receipt else None,
        "status": "CONFIRMED" if receipt else "SUBMITTED",
        "anchored_at": now(),
    }
    with store.connect() as db:
        store.put_object(db, ctx.tenant_id, "audit_anchor", tx_hash, record)
        store.audit(db, ctx, "audit.anchored", {k: record[k] for k in ("tx_hash", "chain_id")})
    return record


def receipt_waiter(
    rpc: Rpc, attempts: int = 60, delay: float = 5.0
) -> Callable[[str], Json | None]:
    import time

    def wait(tx_hash: str) -> Json | None:
        for _ in range(attempts):
            receipt = rpc("eth_getTransactionReceipt", [tx_hash])
            if isinstance(receipt, dict):
                return receipt
            time.sleep(delay)
        return None

    return wait


def verify(store: Store, ctx: AuthContext, rpc: Rpc, tx_hash: str) -> Json:
    """Read the transaction from the chain and check it against the local audit log."""
    with store.connect() as db:
        store.authorize(db, ctx)
    chain_id, net = testnet(rpc)
    tx = rpc("eth_getTransactionByHash", [tx_hash])
    if not isinstance(tx, dict):
        raise FinanceError("NOT_FOUND", "Transaction not found on this network")
    on_chain = decode(str(tx["input"]))
    local = chain_prefix(store, ctx, on_chain["count"])
    checks = {
        "same_tenant": on_chain["tenant_tag"] == tenant_tag(ctx.tenant_id).hex(),
        "local_chain_valid": bool(local["valid"]),
        "enough_local_records": local.get("count") == on_chain["count"],
        "head_matches": local.get("head_hash") == on_chain["head_hash"],
        "mined": tx.get("blockNumber") is not None,
    }
    return {
        "tx_hash": tx_hash,
        "network": net["name"],
        "chain_id": chain_id,
        "explorer_url": net["explorer"] + tx_hash,
        "anchored_count": on_chain["count"],
        "anchored_head": on_chain["head_hash"],
        "checks": checks,
        "valid": all(checks.values()),
    }


def latest(store: Store, ctx: AuthContext) -> Json | None:
    with store.connect() as db:
        store.authorize(db, ctx)
        row = db.execute(
            "SELECT payload FROM objects WHERE tenant_id=? AND kind='audit_anchor' "
            "ORDER BY created_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None
