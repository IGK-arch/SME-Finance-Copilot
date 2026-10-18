"""On-chain anchoring of the audit chain: payload, testnet-only guard, verification."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from finance import anchor
from finance.domain import FinanceError, canonical, digest
from scripts.runtime import Runtime

KEY = "0x" + "11" * 32
SEPOLIA = hex(11155111)


class FakeChain:
    """Minimal JSON-RPC double: records the sent transaction and serves it back."""

    def __init__(self, chain_id: str = SEPOLIA) -> None:
        self.chain_id = chain_id
        self.sent: dict = {}
        self.raw = ""

    def __call__(self, method: str, params: list) -> object:
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getTransactionCount":
            return "0x0"
        if method == "eth_getBlockByNumber":
            return {"baseFeePerGas": hex(10**9)}
        if method == "eth_maxPriorityFeePerGas":
            return hex(10**8)
        if method == "eth_estimateGas":
            self.sent = params[0]
            return hex(30000)
        if method == "eth_sendRawTransaction":
            self.raw = params[0]
            return "0x" + "ab" * 32
        if method == "eth_getTransactionByHash":
            return {"input": self.sent["data"], "blockNumber": "0x10"}
        raise AssertionError(method)


def rewrite_history(runtime: Runtime) -> None:
    with closing(sqlite3.connect(runtime.store.path)) as db, db:
        db.execute("DROP TRIGGER immutable_audit_update")
        rows = db.execute(
            "SELECT audit_id,occurred_at,event_type,payload FROM audit WHERE tenant_id=? "
            "ORDER BY audit_id",
            (runtime.ctx.tenant_id,),
        ).fetchall()
        previous = "0" * 64
        for n, (audit_id, at, kind, payload) in enumerate(rows):
            value = json.loads(payload) | ({"forged": True} if n == 1 else {})
            event_hash = digest([previous, at, kind, value])
            db.execute(
                "UPDATE audit SET payload=?,previous_hash=?,event_hash=? WHERE audit_id=?",
                (canonical(value), previous, event_hash, audit_id),
            )
            previous = event_hash


class AnchorTests(unittest.TestCase):
    def test_payload_round_trip_holds_only_hashes(self) -> None:
        data = anchor.encode("demo_company", 23, "ab" * 32)
        self.assertEqual(len(bytes.fromhex(data[2:])), anchor.PAYLOAD_BYTES)
        self.assertNotIn(b"demo_company", bytes.fromhex(data[2:]))
        self.assertEqual(
            anchor.decode(data),
            {
                "tenant_tag": anchor.tenant_tag("demo_company").hex(),
                "count": 23,
                "head_hash": "ab" * 32,
            },
        )
        with self.assertRaises(FinanceError):
            anchor.decode("0x" + "00" * anchor.PAYLOAD_BYTES)

    def test_mainnet_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            with self.assertRaises(FinanceError) as raised:
                anchor.anchor(runtime.store, runtime.ctx, FakeChain("0x1"), KEY)
            self.assertEqual(raised.exception.code, "MAINNET_REFUSED")

    def test_anchor_then_verify_and_detect_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            chain = FakeChain()
            head = anchor.chain_prefix(runtime.store, runtime.ctx)
            record = anchor.anchor(
                runtime.store,
                runtime.ctx,
                chain,
                KEY,
                lambda h: {"status": "0x1", "blockNumber": "0x10"},
            )
            self.assertEqual(record["status"], "CONFIRMED")
            self.assertEqual(record["audit_count"], head["count"])
            self.assertTrue(record["explorer_url"].startswith("https://sepolia.etherscan.io/tx/"))
            self.assertEqual(chain.sent["value"], 0)
            self.assertEqual(chain.sent["to"], chain.sent["from"])
            self.assertTrue(chain.raw.startswith("0x02"))  # signed EIP-1559 transaction
            self.assertEqual(
                anchor.latest(runtime.store, runtime.ctx)["tx_hash"], record["tx_hash"]
            )
            # The anchor itself is audited; later records do not invalidate an older anchor.
            result = anchor.verify(runtime.store, runtime.ctx, chain, record["tx_hash"])
            self.assertTrue(result["valid"], result["checks"])
            # An administrator with file access rewrites history AND recomputes every hash.
            # The local chain check passes again; only the public anchor exposes the rewrite.
            rewrite_history(runtime)
            self.assertTrue(runtime.store.verify_audit(runtime.ctx)["valid"])
            forged = anchor.verify(runtime.store, runtime.ctx, chain, record["tx_hash"])
            self.assertFalse(forged["valid"])
            self.assertTrue(forged["checks"]["local_chain_valid"])
            self.assertFalse(forged["checks"]["head_matches"])

    def test_auditor_cannot_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            auditor = runtime.store.authenticate(runtime.tokens["AUDITOR"])
            with self.assertRaises(FinanceError):
                anchor.anchor(runtime.store, auditor, FakeChain(), KEY)


if __name__ == "__main__":
    unittest.main()
