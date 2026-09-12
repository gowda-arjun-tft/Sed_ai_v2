"""Persistent research runs, native tool turns and operational recovery without paid calls."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer3 import run_all
from ML.deep_research.layer3.pipeline.run_checks import run_checks
from ML.deep_research.layer3.research_run import checkpoint_root, create_research_run
from tests.layer3_fixtures import new_run, snapshot
from tests.research_fixtures import ResearchModel, linked_run


class DomainResearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_linked_native_graph_tools_reports_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, run = await linked_run(root)
            original = snapshot(parent)
            model = ResearchModel()
            with model.offline(root / "checkpoints"), patch(
                "ML.deep_research.layer3.cli.run_research", side_effect=AssertionError("No discovery")
            ), patch("ML.deep_research.layer3.cli._run_uploads", side_effect=AssertionError("No upload phase")):
                await run_all(run)
                record = load_json(run / "run.json")
                self.assertEqual(record["research"]["status"], "complete", (run / "run.log").read_text())
                self.assertEqual(len(model.calls), 6)
                self.assertEqual(model.peak, 1)
                self.assertEqual(len(list((run / "research").glob("*.md"))), 2)
                for job in record["research"]["jobs"].values():
                    raw = (run / job["root"] / "response.md").read_bytes()
                    self.assertEqual((run / job["output_path"]).read_bytes(), raw)
                    state = load_json(run / job["root"] / "working_state.json")
                    self.assertTrue(state["todos"])
                    self.assertTrue(state["files"])
                    self.assertTrue(Path(job["checkpoint_path"]).exists())
                allowed = {"search_web", "read_source", "read_document", "write_todos", "ls", "glob", "grep", "read_file", "write_file", "edit_file"}
                self.assertTrue(all(s == allowed for s in model.surfaces), model.surfaces)
                calls = len(model.calls)
                await run_all(run)
                self.assertEqual(len(model.calls), calls)
                self.assertEqual(snapshot(parent), original)
                before = snapshot(run)
                run_checks(run)
                self.assertEqual(snapshot(run), before)
                self.assertNotIn("PRIVATE_EVIDENCE", (run / "run.log").read_text())

    async def test_new_full_run_prepares_then_researches_and_missing_storage_precedes_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = new_run(root)
            with patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), patch(
                "ML.deep_research.layer3.cli.run_research", new_callable=AsyncMock
            ) as discovery, patch("ML.deep_research.layer3.cli.checkpoint_root", side_effect=RuntimeError("dedicated volume required")):
                with self.assertRaisesRegex(RuntimeError, "volume"):
                    await run_all(run)
                discovery.assert_not_awaited()
            model = ResearchModel()
            from tests.layer3_fixtures import FakeFinder
            events = []

            async def discover(path, **kwargs):
                """Save preparation through the real runner before entering research."""
                events.append("discovery")
                await FakeFinder().run(path)

            async def uploads(path, **kwargs):
                """Represent warning-only upload failures without a network request."""
                events.append("uploads")
                record = load_json(path / "run.json")
                record["document_uploads"]["status"] = "partial"
                write_json(path / "run.json", record)

            with model.offline(root / "checkpoints"), patch("ML.deep_research.layer3.cli.run_research", discover), patch(
                "ML.deep_research.layer3.cli._run_uploads", uploads):
                await run_all(run)
            self.assertEqual(events, ["discovery", "uploads"])
            self.assertEqual(load_json(run / "run.json")["status"], "complete")

    async def test_failed_sibling_and_same_thread_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root)
            model = ResearchModel()
            model.fail_domain = "source_finder/000001"
            with model.offline(root / "checkpoints"):
                await run_all(run)
                first = load_json(run / "run.json")
                self.assertEqual(first["status"], "partial")
                self.assertEqual(len(list((run / "research").glob("*.md"))), 1)
                model.fail_domain = None
                await run_all(run, retry_failed=True)
                second = load_json(run / "run.json")
                self.assertEqual(second["status"], "complete")
                for key, job in first["research"]["jobs"].items():
                    self.assertEqual(second["research"]["jobs"][key]["thread_id"], job["thread_id"])

    async def test_cancellation_joins_workers_and_resumes_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root)
            model = ResearchModel()
            model.gate = asyncio.Event()
            with model.offline(root / "checkpoints"):
                task = asyncio.create_task(run_all(run))
                while not model.active:
                    await asyncio.sleep(0.01)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertEqual(model.active, 0)
                record = load_json(run / "run.json")
                self.assertEqual(record["status"], "interrupted")
                model.gate = None
                await run_all(run)
                self.assertEqual(load_json(run / "run.json")["status"], "complete")

    async def test_final_receipt_recovers_publication_failure_without_another_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            model = ResearchModel()
            with model.offline(root / "checkpoints"):
                with patch("ML.deep_research.layer3.domain_research._view", side_effect=OSError("offline publication failure")):
                    await run_all(run)
                first = load_json(run / "run.json")
                self.assertEqual(first["status"], "partial")
                calls = len(model.calls)
                await run_all(run)
                self.assertEqual(len(model.calls), calls)
                self.assertEqual(load_json(run / "run.json")["status"], "complete")


if __name__ == "__main__":
    unittest.main()
