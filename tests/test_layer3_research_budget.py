"""Atomic accounting, native finalization and resumable exhaustion without real network calls."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, ToolMessage

from ML.deep_research.domain_decider.backend.fs import load_json, write_json
from ML.deep_research.research_module import run_all
from ML.deep_research.research_module.backend.research_runner import prepare_domain
from ML.deep_research.research_module.backend.research_budget import BudgetExhausted, CallBudget, CallUnavailable
from ML.deep_research.research_module.backend.research_run import research_policy
from tests.research_fixtures import ResearchModel, linked_run


def new_budget(root, used=0, limits=None):
    """Seed disposable observed reservations to test exact production thresholds cheaply."""
    entry = {"fingerprint": "offline", "thread_id": "thread"}
    write_json(root / "calls.json", {"fingerprint": "offline", "calls": [
        {"number": i, "kind": "main", "outcome": "returned"} for i in range(1, used + 1)]})
    return CallBudget(root, research_policy(call_limits=limits), entry, Mock(), Mock())


def seed_domain(run, checkpoint, used):
    """Initialize fixture work exactly once, with durable historical call reservations."""
    record = load_json(run / "run.json")
    root, job, _, _ = prepare_domain(run, record, record["domains"][0], checkpoint)
    write_json(root / "calls.json", {"fingerprint": job["fingerprint"], "calls": [
        {"number": i, "kind": "main", "outcome": "returned"} for i in range(1, used + 1)]})
    return root, job


class ResearchBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_thresholds_and_unlimited_reservations_survive_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget = new_budget(root / "bounded", limits={"maximum_calls": 8, "wrap_up_after": 3, "finalize_after": 5})
            for number in range(1, 9):
                phase = "research" if number <= 3 else "wrap_up" if number <= 5 else "finalization"
                self.assertEqual(budget.phase, phase)
                if number >= 6:
                    with self.assertRaises(CallUnavailable):
                        await budget.call("search", lambda n, f: n, AsyncMock())
                if number == 8:
                    with self.assertRaises(CallUnavailable):
                        await budget.call("summary", lambda n, f: n, AsyncMock())
                prepare = Mock(return_value="input")
                await budget.call("main", prepare, AsyncMock())
                self.assertIn(f"logical call {number} of 8", prepare.call_args.args[0])
                self.assertEqual(prepare.call_args.args[1], number == 8)
            with self.assertRaises(BudgetExhausted):
                await budget.call("main", Mock(), AsyncMock())
            unlimited = new_budget(root / "unlimited", limits=dict.fromkeys(
                ("maximum_calls", "wrap_up_after", "finalize_after")))
            for number in range(84):
                kind = ("main", "search", "document", "summary")[number % 4]
                await unlimited.call(kind, lambda note, final: (note, final), AsyncMock())
            resumed = CallBudget(root / "unlimited", unlimited.policy, unlimited.entry, Mock(), Mock())
            self.assertEqual(resumed.used, 84)
            self.assertEqual(resumed.phase, "research")
            self.assertIsNone(resumed.entry["budget"]["remaining"])
            resumed.require_research()
            failed = AsyncMock(side_effect=TimeoutError("PRIVATE_PAYLOAD"))
            with self.assertRaises(TimeoutError):
                await resumed.call("search", lambda n, f: n, failed)
            self.assertEqual(resumed.used, 85)
            self.assertIn("no application call limit", failed.call_args.args[0])
            with self.assertRaises(asyncio.CancelledError):
                await resumed.call("document", lambda n, f: n, AsyncMock(side_effect=asyncio.CancelledError()))
            resumed = CallBudget(root / "unlimited", unlimited.policy, unlimited.entry, Mock(), Mock())
            self.assertEqual(resumed.used, 86)
            self.assertEqual(resumed.state["calls"][-1]["outcome"], "interrupted")

    async def test_unlimited_native_graph_compacts_after_eighty_and_keeps_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "unlimited.json"
            write_json(config, dict.fromkeys(("maximum_calls", "wrap_up_after", "finalize_after")))
            _, run = await linked_run(root, ["energy"], research_config=config)
            record = load_json(run / "run.json")
            record["research"].update(summary_trigger_tokens=1, summary_keep_tokens=100)
            write_json(run / "run.json", record)
            model = ResearchModel()

            async def replies(domain, messages, options):
                """Keep native tools available through compaction and the former hard ceiling."""
                self.assertIn("search_web", model.surfaces[-1])
                self.assertIn("read_document", model.surfaces[-1])
                self.assertIn("write_file", model.surfaces[-1])
                self.assertIn("no application call limit", messages[0].text)
                self.assertEqual(messages[0].text.count("Runtime call allowance:"), 1)
                if len(model.calls) > 82:
                    return AIMessage(content="# Done\n医院 — retained qualification.\n")
                return AIMessage(content="Read context", tool_calls=[{"name": "read_file",
                    "args": {"file_path": "/inputs/context.md"}, "id": f"read-{len(model.calls)}"}])

            model.custom = replies
            with model.offline(root / "checkpoints"):
                await run_all(run)
                used = len(model.calls)
                await run_all(run)
                self.assertEqual(len(model.calls), used)
            record = load_json(run / "run.json")
            self.assertEqual(record["status"], "complete", (run / "run.log").read_text())
            job = next(iter(record["research"]["jobs"].values()))
            self.assertEqual(job["budget"], {"used": used, "remaining": None, "phase": "research"})
            ledger = load_json(run / job["root"] / "calls.json")["calls"]
            self.assertTrue(any(c["number"] > 80 and c["kind"] == "summary" for c in ledger))
            self.assertEqual((run / job["output_path"]).read_bytes(), (run / job["root"] / "response.md").read_bytes())
            self.assertIn("unlimited allowance", (run / "README.md").read_text())
            self.assertIn("remaining=unlimited", (run / "run.log").read_text())

    async def test_atomic_reservations_all_paths_failures_and_no_eighty_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget = new_budget(Path(tmp), 68)
            payloads = []

            def prepare(note, final):
                """Capture exactly what each undispatched call would receive."""
                payloads.append((note, final))
                return note

            async def uncertain(payload):
                """Simulate a dispatched request whose provider acceptance is unknown."""
                await asyncio.sleep(0)
                raise TimeoutError("PRIVATE_PAYLOAD")

            results = await asyncio.gather(*[budget.call("search", prepare, uncertain) for _ in range(5)], return_exceptions=True)
            self.assertEqual(budget.used, 70)
            self.assertEqual(sum(isinstance(r, TimeoutError) for r in results), 2)
            self.assertEqual(sum(isinstance(r, CallUnavailable) for r in results), 3)
            self.assertEqual(len(payloads), 2)
            budget = CallBudget(Path(tmp), budget.policy, budget.entry, Mock(), Mock())
            self.assertEqual(budget.phase, "finalization")
            with self.assertRaises(CallUnavailable):
                await budget.call("document", prepare, AsyncMock())
            for _ in range(9):
                await budget.call("summary", prepare, AsyncMock(return_value="navigation"))
            with self.assertRaises(CallUnavailable):
                await budget.call("summary", prepare, AsyncMock())
            await budget.call("main", prepare, AsyncMock(return_value="# Final"))
            self.assertTrue(payloads[-1][1])
            for kind in ("main", "search", "document", "summary"):
                with self.assertRaises(BudgetExhausted):
                    await budget.call(kind, prepare, AsyncMock())
            self.assertEqual(budget.used, 80)
            self.assertNotIn("PRIVATE_PAYLOAD", (Path(tmp) / "calls.json").read_text())

    async def test_annotation_input_failure_and_cancellation_survive_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget = new_budget(root, 59)

            def unfit(note, final):
                """A request that fails preflight was never dispatched and costs no slot."""
                raise ValueError("unfit annotated input")

            with self.assertRaises(ValueError):
                await budget.call("main", unfit, AsyncMock())
            self.assertEqual(budget.used, 59)
            entered = asyncio.Event()

            async def waiting(payload):
                """Wait inside the fake provider so cancellation consumes the reservation."""
                entered.set()
                await asyncio.Event().wait()

            task = asyncio.create_task(budget.call("document", lambda n, f: n, waiting))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            resumed = CallBudget(root, budget.policy, budget.entry, Mock(), Mock())
            self.assertEqual(resumed.used, 60)
            self.assertEqual(resumed.phase, "wrap_up")
            self.assertEqual(resumed.state["calls"][-1]["outcome"], "interrupted")
            (root / "calls.json").unlink()
            resumed.entry["checkpoint_started"] = True
            with self.assertRaisesRegex(RuntimeError, "ledger missing"):
                CallBudget(root, resumed.policy, resumed.entry, Mock(), Mock())

    async def test_eighty_native_calls_readonly_finalization_and_tool_free_last_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            model = ResearchModel()

            async def replies(domain, messages, options):
                """Continue requesting saved context until the final tool-free invocation."""
                number = len(model.calls)
                annotation = messages[0].text
                self.assertEqual(annotation.count("Runtime call allowance:"), 1)
                self.assertIn(f"logical call {number} of 80", annotation)
                if number == 80:
                    self.assertFalse(options.get("tools"))
                    return AIMessage(content="# Final\nSupported finding — gap disclosed.\n")
                if number >= 71:
                    self.assertEqual(model.surfaces[-1], {"ls", "glob", "grep", "read_file"})
                if number == 71:
                    denied = [m for m in messages if isinstance(m, ToolMessage) and m.tool_call_id == "denied-70"]
                    self.assertEqual(len(denied), 1)
                    self.assertIn("finalization", denied[0].text)
                calls = [{"name": "read_file", "args": {"file_path": "/inputs/context.md"}, "id": f"read-{number}"}]
                if number == 70:
                    calls.append({"name": "search_web", "args": {"query": "must not dispatch"}, "id": "denied-70"})
                return AIMessage(content="Read retained evidence", tool_calls=calls)

            model.custom = replies
            with model.offline(root / "checkpoints"):
                await run_all(run)
                record = load_json(run / "run.json")
                self.assertEqual(record["status"], "complete", (run / "run.log").read_text())
                job = next(iter(record["research"]["jobs"].values()))
                self.assertEqual(job["budget"]["used"], 80)
                self.assertEqual((run / job["output_path"]).read_bytes(), (run / job["root"] / "response.md").read_bytes())
                await run_all(run)
                self.assertEqual(len(model.calls), 80)

    async def test_final_slot_failure_is_exhausted_but_sibling_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root)
            seed_domain(run, root / "checkpoints", 79)
            model = ResearchModel()
            model.fail_domain = "source_finder/000001"
            with model.offline(root / "checkpoints"):
                await run_all(run)
                record = load_json(run / "run.json")
                self.assertEqual(record["research"]["jobs"][model.fail_domain]["status"], "budget_exhausted")
                self.assertEqual(record["status"], "partial")
                self.assertEqual(len(list((run / "research").glob("*.md"))), 1)
                used = len(model.calls)
                await run_all(run, retry_failed=True)
                self.assertEqual(len(model.calls), used)

    async def test_final_slot_skips_summarization_without_discarding_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            record = load_json(run / "run.json")
            record["research"].update(summary_trigger_tokens=1, summary_keep_tokens=1)
            write_json(run / "run.json", record)
            seed_domain(run, root / "checkpoints", 79)
            model = ResearchModel()

            async def final(domain, messages, options):
                """Even forced compaction cannot consume the final report reservation."""
                self.assertFalse(options.get("tools"))
                self.assertTrue(any("<asset_metadata>" in m.text for m in messages))
                return AIMessage(content="")

            model.custom = final
            with model.offline(root / "checkpoints"):
                await run_all(run)
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
