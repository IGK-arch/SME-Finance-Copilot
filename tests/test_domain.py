from __future__ import annotations

import copy
import random
import tempfile
import unittest
from pathlib import Path

from finance.compute import (
    catalog,
    eligibility,
    factoring_flows,
    financing,
    forecast,
    merchant_bridge,
    metrics,
    optimize,
    scenarios,
    trajectory,
)
from finance.domain import FinanceError, Money, canonical, rate_charge
from finance.ingestion import allocate, import_csv, snapshot
from finance.store import Store
from finance.validation import validate_plan
from scripts.runtime import ORIGIN, PROFILE, csv_bytes, golden_rows


class DomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temporary.name) / "finance.db")
        self.tokens = self.store.create_company("a", PROFILE, ORIGIN)
        self.ctx = self.store.authenticate(self.tokens["OWNER"])
        self.rows = golden_rows()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def load(
        self,
        rows: list | None = None,
        provider: str = "csv",
        received: str = ORIGIN,
        closing: int | None = None,
    ) -> dict:
        return import_csv(
            self.store,
            self.ctx,
            csv_bytes(self.rows if rows is None else rows),
            provider,
            received,
            closing,
        )

    def snap(self, at: str = ORIGIN, cutoff: str = ORIGIN) -> dict:
        return snapshot(self.store, self.ctx, at, cutoff)

    def tx(
        self, amount: int = 3000000, reference: str = "customer_invoice", identifier: str = "tx"
    ) -> dict:
        return dict(
            self.rows[0],
            kind="TRANSACTION",
            external_id=identifier,
            amount_minor=amount,
            status="SETTLED",
            reference=reference,
            counterparty="customer",
        )

    def test_T001_balanced_import(self) -> None:
        self.rows.append(self.tx())
        result = self.load(closing=15000000)
        self.assertEqual(result["status"], "IMPORTED")
        self.assertEqual(self.snap()["confirmed_cash_minor"], 15000000)

    def test_T002_file_repeat(self) -> None:
        self.load()
        version = self.snap()["data_version"]
        self.assertTrue(self.load()["duplicate"])
        self.assertEqual(self.snap()["data_version"], version)
        self.assertEqual(len(self.snap()["obligations"]), 4)

    def test_T003_provider_namespaces(self) -> None:
        self.load([self.tx(500, "", "same")], "provider_a")
        self.load([self.tx(600, "", "same")], "provider_b")
        self.assertEqual(len(self.snap()["facts"]), 2)
        self.assertEqual(self.snap()["confirmed_cash_minor"], 1100)

    def test_T004_tenant_namespaces(self) -> None:
        tokens = self.store.create_company("b", PROFILE, ORIGIN)
        other = self.store.authenticate(tokens["OWNER"])
        self.load()
        import_csv(self.store, other, csv_bytes([self.tx(500)]), "csv", ORIGIN)
        self.assertEqual(snapshot(self.store, other)["confirmed_cash_minor"], 500)
        source = self.snap()["evidence_refs"][0]
        with self.assertRaises(FinanceError):
            self.store.evidence(other, source)

    def test_T005_quarantine(self) -> None:
        bad = dict(self.rows[2], amount_minor="not-an-int")
        result = self.load(self.rows + [bad])
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["accepted"], 6)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT row_number,code FROM quarantine").fetchone()[0], 8)
        self.assertIn("REVIEW_REQUIRED", self.snap()["quality_flags"])

    def test_T006_unsupported_schema(self) -> None:
        with self.assertRaises(FinanceError) as raised:
            import_csv(self.store, self.ctx, b"amount,date\n1,today\n", "csv", ORIGIN)
        self.assertEqual(raised.exception.code, "UNSUPPORTED_SCHEMA")

    def matching_facts(self) -> tuple[str, str]:
        snap = self.snap()
        tx = next(f["fact_id"] for f in snap["facts"] if f["kind"] == "TRANSACTION")
        obligation = next(o["fact_id"] for o in snap["obligations"] if o["kind"] == "RECEIVABLE")
        return tx, obligation

    def test_T007_partial_allocation(self) -> None:
        self.load(self.rows + [self.tx()])
        tx, o = self.matching_facts()
        allocate(self.store, self.ctx, tx, o, 3000000, ORIGIN)
        self.assertEqual(
            next(
                o["outstanding_minor"]
                for o in self.snap()["obligations"]
                if o["kind"] == "RECEIVABLE"
            ),
            7000000,
        )

    def test_T008_one_payment_many(self) -> None:
        extra = dict(self.rows[2], external_id="invoice_2", amount_minor=2000000)
        self.load(self.rows + [extra, self.tx(12000000)])
        tx, _ = self.matching_facts()
        for o in self.snap()["obligations"]:
            if o["kind"] == "RECEIVABLE":
                allocate(self.store, self.ctx, tx, o["fact_id"], o["amount_minor"], ORIGIN)
        self.assertEqual(
            sum(
                o["outstanding_minor"]
                for o in self.snap()["obligations"]
                if o["kind"] == "RECEIVABLE"
            ),
            0,
        )

    def test_T009_overallocation(self) -> None:
        self.load(self.rows + [self.tx(100)])
        tx, o = self.matching_facts()
        with self.assertRaises(FinanceError) as raised:
            allocate(self.store, self.ctx, tx, o, 101, ORIGIN)
        self.assertEqual(raised.exception.code, "OVER_ALLOCATION")

    def test_T010_overpayment_preserved(self) -> None:
        self.load(self.rows + [self.tx(11000000)])
        tx, o = self.matching_facts()
        allocate(self.store, self.ctx, tx, o, 10000000, ORIGIN)
        self.assertEqual(self.snap()["confirmed_cash_minor"], 23000000)
        with self.store.connect() as db:
            allocated = db.execute("SELECT SUM(amount_minor) FROM allocations").fetchone()[0]
        self.assertEqual(11000000 - allocated, 1000000)

    def test_T011_unmatched_cash(self) -> None:
        self.load(self.rows + [self.tx(111, "unknown")])
        self.assertEqual(self.snap()["confirmed_cash_minor"], 12000111)
        self.assertEqual(self.snap()["obligations"][0]["outstanding_minor"], 8000000)

    def test_T012_red_invoice_link(self) -> None:
        correction = dict(
            self.rows[1],
            external_id="red_1",
            amount_minor=-500,
            reference="invoice_customer",
            status="CORRECTED",
        )
        self.load(self.rows + [correction])
        invoices = [f["value"] for f in self.snap()["facts"] if f["kind"] == "INVOICE"]
        self.assertEqual(len(invoices), 2)
        self.assertEqual(
            next(i["reference"] for i in invoices if i["external_id"] == "red_1"),
            "invoice_customer",
        )
        self.assertEqual(self.snap()["confirmed_cash_minor"], 12000000)

    def test_T013_merchant_bridge(self) -> None:
        bridge = merchant_bridge(1000000, 50000, 3000, 947000)
        self.assertEqual(bridge["bridge_difference_minor"], 0)
        self.assertEqual(bridge["revenue_minor"], 950000)
        self.assertFalse(bridge["settlement_is_sale"])

    def test_T014_currency_and_integer(self) -> None:
        for invalid in (1.1, True, "1"):
            with self.assertRaises(FinanceError):
                Money(invalid)
        with self.assertRaises(FinanceError):
            Money(100, "USD")
        with self.assertRaises(FinanceError):
            Money(2**63 - 1) + Money(1)
        result = self.load([dict(self.rows[0], currency="USD")])
        self.assertEqual(result["rejected"], 1)

    def test_T015_rounding(self) -> None:
        self.assertEqual(rate_charge(36500, "0.005", 1), 1)
        self.assertEqual(rate_charge(36500, "0.0049", 1), 0)
        for _ in range(100):
            self.assertEqual(rate_charge(1234567, "0.06", 29), 5885)

    def test_T016_late_observation(self) -> None:
        from finance.compute import shift

        late = shift(ORIGIN, 2)
        self.load([self.tx()], received=late)
        self.assertEqual(self.snap()["confirmed_cash_minor"], 0)
        self.assertEqual(self.snap(late, late)["confirmed_cash_minor"], 3000000)

    def test_T017_version_preserved(self) -> None:
        from finance.compute import shift

        self.load()
        past = self.snap()
        self.load([dict(self.rows[4], version=2, amount_minor=2500000)], received=shift(ORIGIN, 1))
        self.assertEqual(self.store.get_object(self.ctx, "snapshot", past["snapshot_id"]), past)
        current = self.snap(shift(ORIGIN, 1), shift(ORIGIN, 1))
        self.assertEqual(
            next(o["amount_minor"] for o in current["obligations"] if o["external_id"] == "rent"),
            2500000,
        )
        with self.store.connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM facts WHERE external_id='rent'").fetchone()[0], 2
            )

    def test_historical_quality_and_version_no_future(self) -> None:
        from finance.compute import shift

        self.load()
        before = self.snap()
        late = shift(ORIGIN, 2)
        self.load([dict(self.rows[4], version=2, amount_minor=1)], received=late)
        self.load([dict(self.rows[3], amount_minor="bad")], received=late)
        past = self.snap()
        self.assertEqual(past["data_version"], before["data_version"])
        self.assertEqual(past["quality_flags"], [])
        self.assertEqual(past["content_hash"], before["content_hash"])

    def test_T018_incomplete_statement(self) -> None:
        result = self.load(closing=100)
        self.assertEqual(result["status"], "INCOMPLETE_STATEMENT")
        self.assertEqual(self.snap()["confirmed_cash_minor"], 12000000)
        self.assertEqual(optimize(self.snap())["solver_status"], "INFEASIBLE")

    def test_T019_conflict_review(self) -> None:
        self.load()
        conflict = dict(self.rows[5], amount_minor=1, beneficiary_version="attacker_v1")
        result = self.load([conflict])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        o = next(o for o in self.snap()["obligations"] if o["external_id"] == "supplier")
        self.assertEqual(o["amount_minor"], 9000000)
        self.assertEqual(o["beneficiary_version"], "supplier_v1")

    def test_T020_order_independence(self) -> None:
        shuffled = copy.deepcopy(self.rows)
        random.Random(42).shuffle(shuffled)
        self.load(shuffled)
        a = self.snap()
        second = Store(Path(self.temporary.name) / "other.db")
        token = second.create_company("a", PROFILE, ORIGIN)["OWNER"]
        ctx = second.authenticate(token)
        import_csv(second, ctx, csv_bytes(self.rows), "csv", ORIGIN)
        b = snapshot(second, ctx)
        self.assertEqual(a["confirmed_cash_minor"], b["confirmed_cash_minor"])
        self.assertEqual(
            [(o["external_id"], o["outstanding_minor"]) for o in a["obligations"]],
            [(o["external_id"], o["outstanding_minor"]) for o in b["obligations"]],
        )

    def test_T021_invoice_not_cash(self) -> None:
        self.load([self.rows[1]])
        self.assertEqual(self.snap()["confirmed_cash_minor"], 0)

    def test_T022_residual_deduplication(self) -> None:
        self.load()
        snap = self.snap()
        base = forecast(snap)["scenarios"][0]
        repeated = {"reference": "rent", "amount_minor": -2000000, "at": self.rows[4]["due_at"]}
        expanded = forecast(snap, residual_flows=[repeated])["scenarios"][0]
        self.assertEqual(base["final_balance_minor"], expanded["final_balance_minor"])

    def test_T024_overdue_conditional_fallback(self) -> None:
        from finance.compute import shift

        self.load()
        snap = self.snap(shift(ORIGIN, 20), shift(ORIGIN, 20))
        receipt = next(
            p for p in forecast(snap)["scenarios"][0]["points"] if p["kind"] == "EXPECTED_RECEIPT"
        )
        self.assertGreater(receipt["at"], snap["as_of"])
        self.assertEqual(receipt["amount_minor"], 10000000)

    def test_T025_partial_forecast(self) -> None:
        self.test_T007_partial_allocation()
        receipt = next(
            p
            for p in forecast(self.snap())["scenarios"][0]["points"]
            if p["kind"] == "EXPECTED_RECEIPT"
        )
        self.assertEqual(receipt["amount_minor"], 7000000)

    def test_T026_shared_customer_shock(self) -> None:
        self.load(self.rows + [dict(self.rows[2], external_id="second")])
        delayed = forecast(self.snap())["scenarios"][1]
        times = [p["at"] for p in delayed["points"] if p["kind"] == "EXPECTED_RECEIPT"]
        self.assertEqual(len(times), 2)
        self.assertEqual(times[0], times[1])

    def test_T027_intraday_ordering(self) -> None:
        result = trajectory(
            0,
            [
                {"at": "2026-10-01T08:00:00+00:00", "amount_minor": -100, "reference": "morning"},
                {"at": "2026-10-01T18:00:00+00:00", "amount_minor": 100, "reference": "evening"},
            ],
            0,
        )
        self.assertEqual(result["minimum_balance_minor"], -100)

    def test_T028_repayment_tail(self) -> None:
        from finance.compute import shift

        self.load()
        snap = self.snap()
        flows = [{"at": shift(ORIGIN, 45), "amount_minor": -20000000, "reference": "debt_tail"}]
        result = forecast(snap, additional_flows=flows)
        self.assertEqual(result["computed_through"], shift(ORIGIN, 45))
        self.assertEqual(result["scenarios"][0]["final_balance_minor"], -17000000)

    def test_T029_sparse_label(self) -> None:
        self.load()
        result = forecast(self.snap())
        self.assertIn("Sparse history: calendar fallback", result["assumptions"])
        self.assertEqual(result["scenarios"][0]["calibration_status"], "UNCALIBRATED")

    def test_T030_probability_label(self) -> None:
        self.load()
        self.assertIn("not bankruptcy probabilities", forecast(self.snap())["label"])

    def test_T033_snapshot_cache_key(self) -> None:
        from finance.compute import shift

        self.load()
        a = forecast(self.snap())
        self.load([self.tx()], received=shift(ORIGIN, 1))
        b = forecast(self.snap(shift(ORIGIN, 1), shift(ORIGIN, 1)))
        self.assertNotEqual(a["forecast_id"], b["forecast_id"])

    def test_T034_pnl_blocked(self) -> None:
        self.load()
        self.assertEqual(metrics(self.snap())["pnl"]["status"], "INSUFFICIENT_DATA")

    def test_T035_metric_evidence(self) -> None:
        self.load()
        snap = self.snap()
        result = metrics(snap)["metrics"]["confirmed_cash_minor"]
        self.assertEqual(result["snapshot_id"], snap["snapshot_id"])
        self.assertEqual(result["value"], snap["confirmed_cash_minor"])
        self.assertEqual(result["evidence_refs"], snap["evidence_refs"])
        self.assertTrue(result["metric_id"])

    def test_T036_eligibility_unknown(self) -> None:
        result = eligibility({}, catalog(ORIGIN)[0])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("legal_form", result["missing_fields"])

    def test_T037_eligibility_fail(self) -> None:
        result = eligibility(PROFILE | {"jurisdiction": "US"}, catalog(ORIGIN)[0])
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["conditions"][0]["source"])

    def test_T038_late_finance(self) -> None:
        self.load()
        result = optimize(self.snap(), items=[catalog(ORIGIN)[1]])
        self.assertEqual(result["solver_status"], "INFEASIBLE")
        self.assertIsNone(result["plan"])

    def test_T039_net_proceeds(self) -> None:
        result = financing(catalog(ORIGIN)[0], 9100000)
        self.assertEqual(result["net_minor"], 9000000)

    def test_T040_debt_schedule(self) -> None:
        item = catalog(ORIGIN)[0] | {"rate": "0.06"}
        result = financing(item, 9100000)
        self.assertEqual(
            result["repayment_minor"],
            9100000 + result["interest_minor"] + item["repayment_fee_minor"],
        )
        self.assertTrue(result["within_cost_cap"])
        self.assertEqual(result["residual_principal_minor"], 0)

    def test_T041_factoring(self) -> None:
        self.load()
        snap = self.snap()
        receipt = next(o for o in snap["obligations"] if o["kind"] == "RECEIVABLE")
        assignment = factoring_flows(receipt, 8000000, 100000, ORIGIN)
        from finance.compute import obligation_flows

        flows = (
            obligation_flows(snap, scenarios()[0], False, assignment["assigned_receivables"])
            + assignment["flows"]
        )
        self.assertEqual(sum(f["amount_minor"] for f in flows), 9900000)

    def test_T043_extension_request_not_fact(self) -> None:
        self.load()
        before = self.snap()
        with self.store.transaction() as db:
            self.store.put_object(
                db,
                self.ctx.tenant_id,
                "extension_request",
                "request1",
                {"obligation": "supplier", "requested_due_at": "2026-11-01", "status": "REQUESTED"},
            )
        self.assertEqual(self.snap()["obligations"], before["obligations"])

    def test_T044_application_not_cash(self) -> None:
        self.load()
        with self.store.transaction() as db:
            self.store.put_object(
                db,
                self.ctx.tenant_id,
                "application",
                "app1",
                {"status": "SUBMITTED", "amount_minor": 10000000},
            )
        self.assertEqual(self.snap()["confirmed_cash_minor"], 12000000)

    def test_T045_protected_salary(self) -> None:
        self.load()
        plan = optimize(self.snap())["plan"]
        action = next(a for a in plan["actions"] if a["obligation_id"] == "salary")
        self.assertEqual(action["at"], self.rows[3]["due_at"])
        self.assertEqual(action["amount_minor"], 8000000)

    def test_T046_hard_reserve(self) -> None:
        self.load()
        result = optimize(self.snap(), "NO_NEW_DEBT")
        self.assertEqual(result["solver_status"], "INFEASIBLE")
        plan = optimize(self.snap())["plan"]
        self.assertEqual(plan["paths"][0]["minimum_balance_minor"], 2000000)

    def test_T047_feasible_status(self) -> None:
        self.load()
        result = optimize(self.snap(), search_budget=92)
        self.assertEqual(result["solver_status"], "FEASIBLE")
        self.assertEqual(result["plan"]["solver_status"], "FEASIBLE")

    def test_T048_unknown_status(self) -> None:
        self.load()
        result = optimize(self.snap(), search_budget=0)
        self.assertEqual(result["solver_status"], "UNKNOWN")
        self.assertIsNone(result["plan"])

    def test_T049_independent_corruption(self) -> None:
        self.load()
        snap = self.snap()
        plan = copy.deepcopy(optimize(snap)["plan"])
        payment = next(a for a in plan["actions"] if a["kind"] == "PAY_OBLIGATION")
        payment["amount_minor"] -= 1
        self.assertFalse(validate_plan(snap, plan, [scenarios()[0]])["valid"])

    def test_quote_arithmetic_corruption(self) -> None:
        self.load()
        snap = self.snap()
        plan = copy.deepcopy(optimize(snap)["plan"])
        plan["quote"]["repayment_minor"] -= 1000
        repayment = next(a for a in plan["actions"] if a["kind"] == "REPAY_LOAN")
        repayment["amount_minor"] -= 1000
        repayment["cash_delta_minor"] += 1000
        self.assertIn("REPAYMENT_ARITHMETIC", validate_plan(snap, plan, [scenarios()[0]])["errors"])

    def test_T050_no_plan_explained(self) -> None:
        self.load()
        result = optimize(self.snap(), items=[])
        self.assertIsNone(result["plan"])
        self.assertTrue(result["reason"])

    def test_T052_nonanticipative(self) -> None:
        self.load()
        snap = self.snap()
        self.assertEqual(
            optimize(snap)["plan"]["plan_id"], optimize(copy.deepcopy(snap))["plan"]["plan_id"]
        )
        self.assertNotIn("private_schedule", canonical(snap))

    def test_T053_dag(self) -> None:
        self.load()
        from finance.compute import dag_valid

        plan = optimize(self.snap())["plan"]
        self.assertTrue(dag_valid(plan["actions"]))
        self.assertTrue(
            all(a["completion_predicate"] == "SETTLED_AND_RECONCILED" for a in plan["actions"])
        )
        plan["actions"][0]["dependencies"] = [plan["actions"][0]["action_id"]]
        self.assertFalse(dag_valid(plan["actions"]))

    def test_T054_no_debt_not_invented(self) -> None:
        self.load()
        self.assertIsNone(optimize(self.snap(), "NO_NEW_DEBT")["plan"])

    def test_money_property(self) -> None:
        randomizer = random.Random(20)
        for _ in range(500):
            cash = randomizer.randint(0, 10000000)
            amounts = [randomizer.randint(-10000, 10000) for _ in range(15)]
            flows = [
                {"at": f"2026-10-{day:02}T00:00:00+00:00", "amount_minor": a, "reference": str(day)}
                for day, a in enumerate(amounts, 1)
            ]
            result = trajectory(cash, flows, 0)
            self.assertEqual(result["final_balance_minor"], cash + sum(amounts))
