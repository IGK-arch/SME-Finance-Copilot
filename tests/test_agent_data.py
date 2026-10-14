"""Actual domain/graph checks; scripted model messages are explicitly offline fixtures."""

import json
import tempfile
import unittest
from pathlib import Path

from finance.agent_data import DATASETS, list_records, read_record
from finance.agents import ToolRegistry
from finance.domain import AuthContext, FinanceError, canonical
from finance.gateway import ChatGateway
from finance.ingestion import import_csv, snapshot
from finance.workflows import WorkflowEngine, available_tools, call_model_tool, model_result
from finance.workspace import add_document
from finance.worker import work_once
from scripts.runtime import Runtime, csv_bytes, golden_rows


class AgentDataTests(unittest.TestCase):
    def test_review_flags_allow_diagnosis_but_not_an_executable_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            bad = golden_rows()[1] | {"external_id": "rejected", "amount_minor": "not-money"}
            import_csv(
                r.store, r.ctx, csv_bytes([bad]), "review_fixture", r.store.company(r.ctx)["clock"]
            )
            self.assertIn("REVIEW_REQUIRED", snapshot(r.store, r.ctx)["quality_flags"])
            sequence = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "list_business_records",
                                "arguments": {"dataset": "reviews", "query": "", "offset": 0},
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "content": "Rejected amount needs human correction; no action performed.",
                },
            ]
            run = WorkflowEngine(r.service, ChatGateway(scripted=sequence)).run(
                r.ctx, task="Explain the rejected import"
            )
            self.assertEqual(run["phase"], "COMPLETE")
            self.assertEqual(run["state"]["outputs"][0]["output"]["result"]["total_matches"], 1)
            self.assertIsNone(r.service.make_plan(r.ctx)["plan"])
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)

    def test_detail_tools_require_visible_matching_dataset_record_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            initial = [s["function"]["name"] for s in available_tools([])]
            self.assertNotIn("read_business_record", initial)
            self.assertNotIn("get_plan_details", initial)
            page = registry.call(
                "list_business_records",
                {
                    "dataset": "obligations",
                    "query": "supplier",
                    "offset": 0,
                },
            )
            outputs = [{"name": "list_business_records", "output": page}]
            identifier = page["result"]["records"][0]["record_id"]
            args = {"dataset": "obligations", "record_id": identifier, "offset": 0}
            self.assertEqual(
                call_model_tool(registry, "read_business_record", args, outputs)["status"], "OK"
            )
            for bad in (
                args | {"record_id": "invented"},
                args | {"dataset": "invoices"},
                args | {"dataset": []},
            ):
                self.assertEqual(
                    call_model_tool(registry, "read_business_record", bad, outputs)["error"][
                        "code"
                    ],
                    "MODEL_TOOL_PREREQUISITE",
                )
            self.assertEqual(
                call_model_tool(registry, "read_business_record", args, [])["status"], "ERROR"
            )

    def test_all_datasets_scoped_and_paginated_no_secret_or_future(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            secret_doc = add_document(r.store, r.ctx, "PRIVATE_MARKER", "PRIVATE_BODY", ["OWNER"])
            reader = r.store.authenticate(r.tokens["ACCOUNTANT"])
            rows = [
                golden_rows()[1] | {"external_id": f"invoice_{i}", "amount_minor": 10000 + i}
                for i in range(7)
            ]
            import_csv(
                r.store, r.ctx, csv_bytes(rows), "page_test", r.store.company(r.ctx)["clock"]
            )
            future = rows[0] | {
                "external_id": "FUTURE_SECRET",
                "observed_time": "2026-12-01T00:00:00Z",
            }
            import_csv(
                r.store, r.ctx, csv_bytes([future]), "future_test", r.store.company(r.ctx)["clock"]
            )
            for dataset in DATASETS:
                result = list_records(r.service, reader, dataset, "", 0)
                serialized = canonical(result)
                self.assertLessEqual(len(result["records"]), 5, dataset)
                self.assertNotIn("token_hash", serialized, dataset)
                self.assertNotIn("PRIVATE_MARKER", serialized, dataset)
                self.assertNotIn(secret_doc["source_id"], serialized, dataset)
                if dataset in {"facts", "invoices"}:
                    self.assertNotIn("FUTURE_SECRET", serialized)
            page = list_records(r.service, reader, "invoices", "page_test", 0)
            more = list_records(r.service, reader, "invoices", "page_test", page["next_offset"])
            self.assertEqual(page["total_matches"], 7)
            self.assertEqual(len(page["records"]) + len(more["records"]), 7)
            self.assertEqual(page["collection_hash"], more["collection_hash"])
            self.assertIsNone(more["next_offset"])
            self.assertEqual(page["field_totals"]["amount_minor"], sum(10000 + i for i in range(7)))
            for dataset, identifier in [
                ("sources", secret_doc["source_id"]),
                ("documents", secret_doc["document_id"] + ":1"),
            ]:
                with self.assertRaises(FinanceError):
                    read_record(r.service, reader, dataset, identifier, 0)
            with self.assertRaises(FinanceError):
                list_records(
                    r.service, AuthContext("foreign", reader.user_id, reader.role), "company", "", 0
                )

    def test_complete_long_document_and_literal_query_and_argument_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            text = "Long synthetic content. " * 400 + "FINAL_CLAUSE_789"
            doc = add_document(r.store, r.ctx, "Long document", text)
            key = doc["document_id"] + ":1"
            parts, hashes, offset = [], set(), 0
            while offset is not None:
                page = read_record(r.service, r.ctx, "documents", key, offset)
                parts.append(page["json_fragment"])
                hashes.add(page["content_hash"])
                offset = page["next_offset"]
            self.assertEqual(len(hashes), 1)
            self.assertEqual(json.loads("".join(parts))["text"], text)
            self.assertEqual(
                list_records(r.service, r.ctx, "documents", "' OR 1=1 --", 0)["total_matches"], 0
            )
            registry = ToolRegistry(r.service, r.ctx)
            for bad in (-1, True, 10000001, "0"):
                self.assertEqual(
                    registry.call(
                        "list_business_records", {"dataset": "facts", "query": "", "offset": bad}
                    )["status"],
                    "ERROR",
                )
            self.assertEqual(
                registry.call(
                    "list_business_records",
                    {"dataset": "schema_migrations", "query": "", "offset": 0},
                )["status"],
                "ERROR",
            )

    def test_details_and_computations_preserve_facts_and_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            before = snapshot(r.store, r.ctx)
            what = registry.call(
                "what_if_cashflow",
                {"snapshot_id": before["snapshot_id"], "delay_days": 7, "receipt_bps": 5000},
            )
            self.assertEqual(what["status"], "OK")
            self.assertEqual(what["result"]["forecast"]["scenarios"][0]["receipt_bps"], 5000)
            self.assertEqual(snapshot(r.store, r.ctx), before)
            calc = read_record(r.service, r.ctx, "calculations", what["result_id"], 0)
            self.assertEqual(calc["record_id"], what["result_id"])
            metrics = model_result(
                registry.call("calculate_business_metrics", {"snapshot_id": before["snapshot_id"]})
            )
            self.assertEqual(
                metrics["result"]["metrics"]["confirmed_cash_minor"]["display_cny"],
                "120,000.00 CNY",
            )
            invoice = list_records(r.service, r.ctx, "invoices", "invoice_customer", 0)["records"][
                0
            ]
            detail = read_record(r.service, r.ctx, "invoices", invoice["record_id"], 0)["record"]
            self.assertEqual(detail["kind"], "INVOICE")
            self.assertIn(detail["source_id"], before["evidence_refs"])
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM objects WHERE kind='plan'").fetchone()[0], 0
                )

    def test_plan_action_ids_pairing_and_proposal_never_approve(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            plan = registry.call("optimize_plan", {"objective": "MIN_COST"})
            data = model_result(plan)["result"]["plan"]
            self.assertTrue(data["actions"])
            self.assertTrue(data["quote"])
            self.assertTrue(
                any(a.get("quote_id") == data["quote"]["quote_id"] for a in data["actions"])
            )
            self.assertTrue(all("quote" not in a for a in data["actions"]))
            self.assertEqual(data["full_record"]["record_id"], data["plan_id"])
            args = {"plan_id": data["plan_id"], "action_id": data["actions"][0]["action_id"]}
            self.assertNotIn("prepare_action", [s["function"]["name"] for s in available_tools([])])
            self.assertEqual(
                call_model_tool(registry, "prepare_action", args, [])["error"]["code"],
                "MODEL_TOOL_PREREQUISITE",
            )
            outputs = [{"name": "optimize_plan", "output": plan}]
            proposal = call_model_tool(registry, "prepare_action", args, outputs)
            self.assertEqual(proposal["result"]["readiness"], "WAITING_PRECONDITIONS")
            self.assertFalse(proposal["result"]["executed"])
            for bad in (
                args | {"action_id": "invented"},
                args | {"plan_id": "foreign"},
                args | {"plan_id": []},
            ):
                self.assertEqual(
                    call_model_tool(registry, "prepare_action", bad, outputs)["status"], "ERROR"
                )
            r.advance(1)
            ready = call_model_tool(registry, "prepare_action", args, outputs)
            self.assertEqual(ready["result"]["readiness"], "EXACT_APPROVAL_REQUIRED")
            with self.assertRaises(FinanceError):
                r.service.prepare(r.ctx, ready["result"]["command"])
            with r.store.connect() as db:
                for table in ("actions", "approvals", "execution_jobs"):
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)

    def test_existing_plan_selected_action_pauses_without_auto_executing_other_actions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            plan = r.service.make_plan(r.ctx)["plan"]
            selected = next(a for a in plan["actions"] if a.get("obligation_id") == "supplier")
            sequence = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "list_business_records",
                                "arguments": {"dataset": "plans", "query": "", "offset": 0},
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_plan_details",
                                "arguments": {"plan_id": plan["plan_id"], "offset": 0},
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "prepare_action",
                                "arguments": {
                                    "plan_id": plan["plan_id"],
                                    "action_id": selected["action_id"],
                                },
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "content": "Proposal only; wait for dependencies and exact approval.",
                },
            ]
            run = WorkflowEngine(r.service, ChatGateway(scripted=sequence)).run(
                r.ctx, task="Prepare only the supplier action in my saved plan"
            )
            self.assertEqual(run["phase"], "PAUSED")
            self.assertEqual(run["state"]["pending"][0]["action_id"], selected["action_id"])
            self.assertEqual(run["state"]["selected_action_id"], selected["action_id"])
            self.assertFalse(run["state"]["errors"])
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
            r.advance(1)
            replanned = WorkflowEngine(r.service, ChatGateway(scripted=sequence)).run(
                r.ctx, run_id=run["workflow_id"], answer={"replan": True}
            )
            new_plan = r.store.get_object(r.ctx, "plan", replanned["state"]["plan_id"])
            chosen = next(
                a
                for a in new_plan["actions"]
                if a["action_id"] == replanned["state"]["selected_action_id"]
            )
            self.assertEqual(chosen["obligation_id"], "supplier")
            self.assertEqual(replanned["state"]["pending"][0]["action_id"], chosen["action_id"])

    def test_T061_old_workflow_evidence_is_denied_after_role_change(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            add_document(r.store, r.ctx, "PRIVATE-TERMS", "PRIVATE-TERMS owner only", ["OWNER"])
            sequence = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_documents",
                                "arguments": {"query": "PRIVATE-TERMS"},
                            }
                        }
                    ],
                },
                {"role": "assistant", "content": "Read owner document."},
            ]
            engine = WorkflowEngine(r.service, ChatGateway(scripted=sequence))
            run = engine.run(r.ctx, task="Read private terms")
            with r.store.transaction() as db:
                db.execute(
                    "UPDATE memberships SET role='ACCOUNTANT' WHERE tenant_id=? AND user_id=?",
                    (r.ctx.tenant_id, r.ctx.user_id),
                )
            changed = r.store.authenticate(r.tokens["OWNER"])
            with self.assertRaises(FinanceError):
                engine.read(changed, run["workflow_id"])
            self.assertEqual(
                list_records(r.service, changed, "workflows", "", 0)["total_matches"], 0
            )

    def test_extension_is_pending_and_protected_obligation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            before = snapshot(r.store, r.ctx)
            for reference, expected in (("salary", "ERROR"), ("supplier", "OK")):
                fact = next(o for o in before["obligations"] if o["external_id"] == reference)
                result = registry.call(
                    "propose_supplier_extension",
                    {"fact_id": fact["fact_id"], "due_at": "2026-10-15T00:00:00Z"},
                )
                self.assertEqual(result["status"], expected)
            self.assertFalse(result["result"]["executable"])
            self.assertEqual(snapshot(r.store, r.ctx), before)

    def test_T066_T086_selected_due_action_requires_exact_approval_and_reconciles_once(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            plan = r.service.make_plan(r.ctx)["plan"]
            selected = plan["actions"][0]
            r.advance(1)
            sequence = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "list_business_records",
                                "arguments": {"dataset": "plans", "query": "", "offset": 0},
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_plan_details",
                                "arguments": {"plan_id": plan["plan_id"], "offset": 0},
                            }
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "prepare_action",
                                "arguments": {
                                    "plan_id": plan["plan_id"],
                                    "action_id": selected["action_id"],
                                },
                            }
                        }
                    ],
                },
                {"role": "assistant", "content": "Exact owner approval required."},
            ]
            engine = WorkflowEngine(r.service, ChatGateway(scripted=sequence))
            run = engine.run(r.ctx, task="Prepare just the selected draw")
            pending = run["state"]["pending"][0]
            self.assertEqual(pending["kind"], "EXACT_APPROVAL")
            with self.assertRaises(FinanceError):
                engine.run(
                    r.ctx,
                    run_id=run["workflow_id"],
                    answer={"payload_hash": pending["payload_hash"]},
                )
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)
            # Explicit test harness owner approval, never produced by the model.
            r.service.approve(r.ctx, pending["command"])
            engine.run(
                r.ctx, run_id=run["workflow_id"], answer={"payload_hash": pending["payload_hash"]}
            )
            work_once(r.service, r.tenant, "selected-action-test")
            r.settle()
            done = engine.run(r.ctx, run_id=run["workflow_id"], answer={"text": "observe"})
            self.assertEqual(done["phase"], "COMPLETE")
            self.assertEqual(r.service.action(r.ctx, selected["action_id"])["status"], "SETTLED")
            with r.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 1)
            self.assertEqual(len(r.adapter.observation()["movements"]), 1)

    def test_role_revocation_rechecked_on_reader_and_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            registry = ToolRegistry(r.service, r.ctx)
            self.assertEqual(
                registry.call(
                    "list_business_records", {"dataset": "company", "query": "", "offset": 0}
                )["status"],
                "OK",
            )
            with r.store.transaction() as db:
                db.execute(
                    "UPDATE memberships SET active=0 WHERE tenant_id=? AND user_id=?",
                    (r.ctx.tenant_id, r.ctx.user_id),
                )
            self.assertEqual(
                registry.call(
                    "list_business_records", {"dataset": "company", "query": "", "offset": 0}
                )["status"],
                "ERROR",
            )


if __name__ == "__main__":
    unittest.main()
