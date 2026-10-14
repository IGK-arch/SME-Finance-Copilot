import tempfile
import unittest
from pathlib import Path

from finance.domain import FinanceError
from finance.gateway import ChatGateway, GatewayConfig
from finance.workflows import WorkflowEngine
from finance.worker import work_once
from finance.ingestion import snapshot
from scripts.runtime import Runtime


class WorkflowTests(unittest.TestCase):
    def test_model_cannot_compute_with_unread_or_invented_snapshot(self) -> None:
        for first_read in (False, True):
            with (
                self.subTest(first_read=first_read),
                tempfile.TemporaryDirectory() as folder,
                Runtime(Path(folder)) as runtime,
            ):
                actual = snapshot(runtime.store, runtime.ctx)["snapshot_id"]
                calls = []
                if first_read:
                    calls.append(
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {"function": {"name": "get_financial_snapshot", "arguments": {}}}
                            ],
                        }
                    )
                calls.extend(
                    [
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "forecast_cashflow",
                                        "arguments": {
                                            "snapshot_id": "invented" if first_read else actual
                                        },
                                    }
                                }
                            ],
                        },
                        {"role": "assistant", "content": "Computation was rejected."},
                    ]
                )
                run = WorkflowEngine(runtime.service, ChatGateway(scripted=calls)).run(
                    runtime.ctx, task="Forecast"
                )
                output = run["state"]["outputs"][-1]["output"]
                self.assertEqual(output["status"], "ERROR")
                self.assertEqual(output["error"]["code"], "MODEL_TOOL_PREREQUISITE")
                self.assertIsNone(output["result"])
                with runtime.store.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)

    def test_resume_rejects_changed_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            engine = WorkflowEngine(runtime.service, ChatGateway(GatewayConfig(model="fixture-a")))
            run = engine.run(runtime.ctx, task="Plan payments")
            changed = WorkflowEngine(runtime.service, ChatGateway(GatewayConfig(model="fixture-b")))
            with self.assertRaises(FinanceError) as failed:
                changed.run(runtime.ctx, run_id=run["workflow_id"], answer={"text": "continue"})
            self.assertEqual(failed.exception.code, "MODEL_CHANGED")
            with runtime.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)

    def test_stale_pending_approval_refresh_requires_new_exact_approval(self) -> None:
        import tempfile
        from pathlib import Path
        from scripts.runtime import Runtime
        from finance.domain import FinanceError

        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as runtime:
            engine = WorkflowEngine(runtime.service)
            run = engine.run(runtime.ctx, task="Plan payments")
            runtime.advance(1)
            run = engine.run(runtime.ctx, run_id=run["workflow_id"], answer={"text": "ready"})
            original = run["state"]["pending"][0]["command"]
            runtime.advance(2)
            with self.assertRaises(FinanceError):
                runtime.service.approve(runtime.ctx, original)
            refreshed = engine.run(
                runtime.ctx, run_id=run["workflow_id"], answer={"refresh_command": True}
            )
            replacement = refreshed["state"]["pending"][0]["command"]
            self.assertNotEqual(original["snapshot_id"], replacement["snapshot_id"])
            self.assertEqual(original["idempotency_key"], replacement["idempotency_key"])
            with runtime.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 0)
            runtime.service.approve(runtime.ctx, replacement)

    def test_T086_graph_resume_exact_approval_worker_and_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with Runtime(directory) as r:
                run = WorkflowEngine(r.service).run(r.ctx, "Preserve payroll and propose a plan")
                self.assertEqual(run["phase"], "PAUSED")
                self.assertEqual(run["state"]["pending"][0]["kind"], "WAITING_EVENT")
                run_id = run["workflow_id"]
            with Runtime(directory, resume=True) as r:
                engine = WorkflowEngine(r.service)
                r.advance(1)
                run = engine.run(r.ctx, run_id=run_id, answer={"text": "continue"})
                pending = run["state"]["pending"][0]
                self.assertEqual(pending["kind"], "EXACT_APPROVAL")
                command = pending["command"]
                r.service.approve(r.ctx, command)
                run = engine.run(
                    r.ctx, run_id=run_id, answer={"payload_hash": pending["payload_hash"]}
                )
                self.assertEqual(run["state"]["pending"][0]["kind"], "OBSERVATION")
                work_once(r.service, r.tenant, "graph-test")
                r.settle()
                run = WorkflowEngine(r.service).run(
                    r.ctx, run_id=run_id, answer={"text": "observed"}
                )
                self.assertEqual(r.service.action(r.ctx, command["action_id"])["status"], "SETTLED")
                self.assertEqual(len(r.adapter.observation()["movements"]), 1)
                self.assertIn("reconciliation", [e["node"] for e in run["events"]])

    def test_meaningful_clarification_persists_and_resumes(self) -> None:
        sequence = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "ask_user",
                            "arguments": {
                                "question": "Do you want a no-debt plan or minimum financing cost?"
                            },
                        }
                    }
                ],
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "optimize_plan",
                            "arguments": {"objective": "NO_NEW_DEBT"},
                        }
                    }
                ],
            },
            {"role": "assistant", "content": "Review the tool result."},
        ]
        with tempfile.TemporaryDirectory() as folder, Runtime(Path(folder)) as r:
            engine = WorkflowEngine(r.service, ChatGateway(scripted=sequence))
            run = engine.run(r.ctx, "Help me decide")
            self.assertEqual(run["state"]["pending"][0]["kind"], "CLARIFICATION")
            engine = WorkflowEngine(r.service, ChatGateway(scripted=sequence))
            final = engine.run(r.ctx, run_id=run["workflow_id"], answer={"text": "No new debt"})
            self.assertEqual(final["phase"], "COMPLETE")
            self.assertEqual(
                final["state"]["outputs"][0]["output"]["result"]["solver_status"], "INFEASIBLE"
            )

    def test_live_disabled_has_no_mock_fallback(self) -> None:
        gateway = ChatGateway(GatewayConfig(provider="ollama", model="", enabled=False))
        with self.assertRaises(FinanceError) as e:
            gateway.chat([], [], {})
        self.assertEqual(e.exception.code, "MODEL_DISABLED")

    def test_T065_step_token_and_context_budgets(self) -> None:
        gateway = ChatGateway(GatewayConfig(max_steps=1, max_tokens=2000))
        with self.assertRaises(FinanceError):
            gateway.chat([], [], {"calls": 1})
        with self.assertRaises(FinanceError):
            gateway.chat([{"role": "user", "content": "x" * 1500}], [], {})
