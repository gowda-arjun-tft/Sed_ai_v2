"""Numbered workflow, frozen handoff and recovery with all provider boundaries offline."""

import asyncio
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research import workflow
from ML.deep_research.domain_decider.backend.fs import load_json, write_json
from ML.deep_research.workflow_storage import allocate
from tests.layer2_fixtures import FakeStages


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    def inputs(self, root):
        """Make a tiny, complete public input set without using project research material."""
        values = {"fact.md": "A public hospital; proposed annex, not installed.",
                  "plugin.md": "# Operations\nResearch its obligations.", "requirements.md": "Preserve conditions.",
                  "source.md": "Use municipal sources.", "objective.md": "Technical investigation only."}
        for name, content in values.items():
            (root / name).write_text(content, encoding="utf-8")
        write_json(root / "config.json", {"maximum_calls": 8, "wrap_up_after": 3, "finalize_after": 5})
        return {"domain_plugin": root / "plugin.md", "requirements": root / "requirements.md",
                "source_suggestion": root / "source.md", "research_instruction": root / "objective.md",
                "research_config": root / "config.json", "runs_dir": root / "runs", "public_input_confirmed": True}

    async def test_full_handoff_and_completed_resume_never_redispatch(self):
        """Pass the exact completed child once; downstream inputs are frozen before domain work."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.inputs(root)
            with patch.object(workflow, "checkpoint_root"), patch.object(workflow, "load_dotenv_key"), patch.dict(
                "os.environ", {"OPENAI_API_KEY": "offline"}), patch("socket.socket.connect", side_effect=AssertionError("network")):
                run = workflow.create_run(root / "fact.md", **args)
                (root / "source.md").write_text("CHANGED AFTER FREEZE")
                fake = FakeStages()

                async def finish(path, **kwargs):
                    """Publish a fake completed researcher without discovering or uploading."""
                    saved = load_json(path / "run.json")
                    self.assertEqual(Path(saved["source_l2"]["path"]), run / "domain_decider")
                    self.assertEqual((path / "_internal/inputs/source_suggestion.md").read_text(), "Use municipal sources.")
                    saved.update(status="complete", discovery_status="complete")
                    saved["research"]["status"] = "complete"
                    write_json(path / "run.json", saved)

                with patch.object(workflow.domain_decider, "run_all", side_effect=fake.run) as domain, patch.object(
                    workflow.research_module, "run_all", new_callable=AsyncMock, side_effect=finish) as research:
                    await workflow.run_all(run)
                    await workflow.run_all(run)
                    self.assertEqual(domain.call_count, 1)
                    self.assertEqual(research.await_count, 1)
                self.assertEqual(run.name, "run_001")
                self.assertEqual(load_json(run / "run.json")["status"], "complete")
                self.assertTrue(load_json(run / "domain_decider/run.json")["run_id"].startswith("L2_"))
                self.assertTrue(load_json(run / "research_module/run.json")["run_id"].startswith("L3_"))
                self.assertFalse((run / "domain_decider/run.log").exists())
                self.assertIn("stage_started", (run / "run.log").read_text())
                self.assertTrue((run / "_internal/trace/events.jsonl").exists())

    async def test_failure_stops_handoff_and_phase_crash_reuses_completed_domain(self):
        """Recover the saved phase identity rather than repeating completed model work."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.inputs(root)
            with patch.object(workflow, "checkpoint_root"), patch.object(workflow, "load_dotenv_key"), patch.dict(
                "os.environ", {"OPENAI_API_KEY": "offline"}):
                run = workflow.create_run(root / "fact.md", **args)
                def fail(path):
                    """Persist an ordinary partial domain outcome."""
                    value = load_json(path / "run.json")
                    value["status"] = "partial"
                    write_json(path / "run.json", value)
                with patch.object(workflow.domain_decider, "run_all", side_effect=fail), patch.object(
                    workflow.research_module, "create_run") as create:
                    await workflow.run_all(run)
                    create.assert_not_called()
                with patch.object(workflow.domain_decider, "run_all", side_effect=FakeStages().run), patch.object(
                    workflow.research_module, "create_run", side_effect=OSError("fixture crash")):
                    with self.assertRaises(OSError):
                        await workflow.run_all(run)
                domain_bytes = (run / "domain_decider/run.json").read_bytes()
                with patch.object(workflow.domain_decider, "run_all", side_effect=AssertionError("duplicate domain")), patch.object(
                    workflow.research_module, "run_all", new_callable=AsyncMock) as research:
                    await workflow.run_all(run)
                    research.assert_awaited_once()
                self.assertEqual((run / "domain_decider/run.json").read_bytes(), domain_bytes)

    def test_counter_concurrency_identity_changes_and_abandoned_reservations(self):
        """Same path keeps its group, identical names at different paths are disambiguated."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "a/fact.md", root / "b/fact.md"
            for source in (a, b):
                source.parent.mkdir()
                source.write_text("same")
            with ThreadPoolExecutor(max_workers=5) as pool:
                first = list(pool.map(lambda _: allocate(root / "runs", a), range(8)))
            self.assertEqual(sorted(item[2] for item in first), list(range(1, 9)))
            a.write_text("changed")
            self.assertEqual(allocate(root / "runs", a)[2], 9)
            other, _, number = allocate(root / "runs", b)
            self.assertEqual(number, 1)
            self.assertEqual(other.parent.name, "fact_2")

    async def test_cancel_keeps_lock_until_sync_phase_exits_and_never_hands_off(self):
        """Notebook cancellation cannot detach a live thread that still owns phase files."""
        import threading
        from ML.deep_research.research_module.backend.document_uploads import run_writer
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.inputs(root)
            entered, release = threading.Event(), threading.Event()
            def running(path):
                """Hold a disposable worker at its safe phase boundary."""
                entered.set()
                release.wait(5)
            with patch.object(workflow, "checkpoint_root"), patch.object(workflow, "load_dotenv_key"), patch.dict(
                "os.environ", {"OPENAI_API_KEY": "offline"}), patch.object(workflow.domain_decider, "run_all", running), patch.object(
                workflow.research_module, "create_run") as research:
                run = workflow.create_run(root / "fact.md", **args)
                task = asyncio.create_task(workflow.run_all(run))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                    task.cancel()
                    await asyncio.sleep(0.02)
                    self.assertFalse(task.done())
                    with self.assertRaises(RuntimeError):
                        with run_writer(run):
                            pass
                finally:
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                research.assert_not_called()
                self.assertEqual(load_json(run / "run.json")["status"], "interrupted")

    def test_invalid_preflight_creates_nothing(self):
        """Consent, configuration and checkpoint failures precede number reservation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.inputs(root)
            with patch.object(workflow, "load_dotenv_key"), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
                with self.assertRaises(ValueError):
                    workflow.create_run(root / "fact.md", **(args | {"public_input_confirmed": False}))
                write_json(root / "config.json", {"maximum_calls": True})
                with self.assertRaises(ValueError):
                    workflow.create_run(root / "fact.md", **args)
                self.assertFalse((root / "runs").exists())
