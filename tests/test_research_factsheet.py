"""Frozen original source access through the unchanged native research filesystem."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from ML.deep_research.domain_decider.backend.fs import load_json, sha256, write_json
from ML.deep_research.research_module import create_run, create_research_run, run_all
from ML.deep_research.research_module.backend.create_run import factsheet_snapshot, verify_inputs
from ML.deep_research.research_module.backend.research_runner import prepare_domain
from tests.layer3_fixtures import FakeFinder, layer2_input, snapshot
from tests.research_fixtures import ResearchModel
from tests.test_layer3_research_budget import seed_domain

RELATIVE = "_internal/inputs/fact_sheet.md"
SOURCE = b"\xef\xbb\xbf" + ("# Original\r\n" + "Background.\r\n" * 500 +
    "SPECIAL_RULE: 医院 pays 100 net except approved closure; 2030 deadline.\r\n").encode()


def prepared(root, **kwargs):
    """Freeze a real manifest-backed original without including it in derived domain text."""
    l2 = layer2_input(root, ["energy"])
    path = l2 / RELATIVE
    path.parent.mkdir(parents=True)
    path.write_bytes(SOURCE)
    record = load_json(l2 / "run.json")
    record["inputs"] = {"fact_sheet.md": {"sha256": sha256(path), "bytes": len(SOURCE)}}
    write_json(l2 / "run.json", record)
    run = create_run(l2, root / "runs", public_input_confirmed=True, **kwargs)
    return l2, run


class FactsheetTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_access_linking_compaction_and_resume(self):
        """Disabling access removes the file, not just its notice, through the native graph."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l2, parent = prepared(root)
            await FakeFinder().run(parent)
            before = snapshot(parent)
            disabled = create_research_run(parent, root / "runs", public_input_confirmed=True,
                                           research_factsheet_access=False)
            direct = create_run(l2, root / "runs", public_input_confirmed=True, research_factsheet_access=False)
            for run in (disabled, direct):
                record = load_json(run / "run.json")
                self.assertFalse(record["research"]["research_factsheet_access"])
                self.assertEqual(record["research"]["factsheet"]["status"], "disabled")
                self.assertNotIn(RELATIVE, record["inputs"])
                self.assertFalse((run / RELATIVE).exists())
                if run == direct:
                    work, _, _, _ = prepare_domain(run, record, record["domains"][0], root / "checkpoints")
                    self.assertFalse((work / "inputs/fact_sheet.md").exists())
            self.assertEqual(snapshot(parent), before)
            self.assertIn("access disabled", (disabled / "README.md").read_text())
            # A newly linked run can explicitly enable the recorded original again.
            record = load_json(disabled / "run.json")
            record["status"] = "partial"
            write_json(disabled / "run.json", record)
            enabled = create_research_run(disabled, root / "runs", public_input_confirmed=True)
            self.assertEqual((enabled / RELATIVE).read_bytes(), SOURCE)
            record["research"].update(summary_trigger_tokens=1, summary_keep_tokens=100)
            write_json(disabled / "run.json", record)
            model, step = ResearchModel(), 0

            async def answer(domain, messages, options):
                """Try native search/read, interrupt, then finish from the same saved policy."""
                nonlocal step
                step += 1
                self.assertIn("Original factsheet access is disabled", messages[0].text)
                self.assertFalse(any("SPECIAL_RULE" in m.text for m in messages))
                if step == 1:
                    return AIMessage(content="Locate", tool_calls=[{"name": "grep", "id": "find",
                        "args": {"pattern": "SPECIAL_RULE", "path": "/inputs/", "output_mode": "content"}}])
                if step == 2:
                    return AIMessage(content="Read", tool_calls=[{"name": "read_file", "id": "read",
                        "args": {"file_path": "/inputs/fact_sheet.md"}}])
                if step == 3:
                    self.assertTrue(any("not found" in m.text.lower() or "error" in m.text.lower()
                                        for m in messages if isinstance(m, ToolMessage)))
                    raise TimeoutError("offline interruption")
                return AIMessage(content="Prepared evidence only.")

            model.custom = answer
            with model.offline(root / "checkpoints"):
                await run_all(disabled)
                job = next(iter(load_json(disabled / "run.json")["research"]["jobs"].values()))
                self.assertEqual(job["status"], "failed")
                await run_all(disabled, retry_failed=True)
                final = load_json(disabled / "run.json")
                self.assertEqual(final["status"], "complete", (disabled / "run.log").read_text())
                self.assertEqual(next(iter(final["research"]["jobs"].values()))["thread_id"], job["thread_id"])
            self.assertIn("compaction_finished", (disabled / "run.log").read_text())
            self.assertEqual(final["research"]["factsheet"]["status"], "disabled")

    async def test_freeze_link_fallback_and_corruption_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l2, run = prepared(root)
            record = load_json(run / "run.json")
            self.assertEqual(record["research"]["version"], 5)
            self.assertEqual((run / RELATIVE).read_bytes(), SOURCE)
            self.assertEqual(record["inputs"][RELATIVE]["sha256"], sha256(l2 / RELATIVE))
            await FakeFinder().run(run)
            old = snapshot(run)
            linked = create_research_run(run, root / "runs", public_input_confirmed=True)
            self.assertEqual((linked / RELATIVE).read_bytes(), SOURCE)
            self.assertEqual(snapshot(run), old)
            # Prefer parent's own snapshot even when its older Domain Decider is gone.
            (l2 / RELATIVE).unlink()
            another = create_research_run(run, root / "runs", public_input_confirmed=True)
            self.assertEqual((another / RELATIVE).read_bytes(), SOURCE)
            (l2 / RELATIVE).write_bytes(SOURCE)
            # Historical source-only input: resolve only its explicitly recorded parent.
            legacy = load_json(run / "run.json")
            legacy["inputs"].pop(RELATIVE)
            legacy["research"]["version"] = 4
            legacy["research"].pop("factsheet")
            (run / RELATIVE).unlink()
            write_json(run / "run.json", legacy)
            linked = create_research_run(run, root / "runs", public_input_confirmed=True)
            self.assertEqual((linked / RELATIVE).read_bytes(), SOURCE)
            (l2 / RELATIVE).write_bytes(b"changed")
            destination = root / "must-not-exist"
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                create_research_run(run, root / "runs", public_input_confirmed=True, destination=destination)
            self.assertFalse(destination.exists())
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                create_run(l2, root / "runs", public_input_confirmed=True, destination=destination)
            self.assertFalse(destination.exists())
            # Recorded missing bytes must not be silently classified as unavailable.
            (l2 / RELATIVE).unlink()
            with self.assertRaises(FileNotFoundError):
                factsheet_snapshot(run, legacy)
            legacy["source_l2"]["path"] = str(root / "absent-parent")
            write_json(run / "run.json", legacy)
            unavailable = create_research_run(run, root / "runs", public_input_confirmed=True)
            self.assertEqual(load_json(unavailable / "run.json")["research"]["factsheet"], {"status": "unavailable"})
            self.assertIn("Original factsheet unavailable", (unavailable / "README.md").read_text())

    async def test_projection_resume_hashes_and_historical_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = prepared(root)
            record = load_json(run / "run.json")
            domain = record["domains"][0]
            work, entry, content, _ = prepare_domain(run, record, domain, root / "checkpoints")
            self.assertNotIn("SPECIAL_RULE", content)
            self.assertEqual((work / "inputs/fact_sheet.md").read_bytes(), SOURCE)
            thread, fingerprint = entry["thread_id"], entry["fingerprint"]
            resumed = prepare_domain(run, load_json(run / "run.json"), domain, root / "checkpoints")
            self.assertEqual((resumed[1]["thread_id"], resumed[1]["fingerprint"]), (thread, fingerprint))
            (work / "inputs/fact_sheet.md").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "factsheet changed"):
                prepare_domain(run, record, domain, root / "checkpoints")
            (run / RELATIVE).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "input changed"):
                verify_inputs(run, record)
            # Old policies must not enable source projection or change existing fingerprints.
            for version in (1, 2, 3, 4):
                old_root = root / str(version)
                old_root.mkdir()
                _, old = prepared(old_root)
                legacy = load_json(old / "run.json")
                legacy["research"]["version"] = version
                legacy["research"].pop("factsheet")
                legacy["inputs"].pop(RELATIVE)
                (old / RELATIVE).unlink()
                write_json(old / "run.json", legacy)
                work, job, _, _ = prepare_domain(old, legacy, legacy["domains"][0], root / "checkpoints")
                self.assertFalse((work / "inputs/fact_sheet.md").exists())
                again = prepare_domain(old, legacy, legacy["domains"][0], root / "checkpoints")
                self.assertEqual(again[1]["fingerprint"], job["fingerprint"])

    async def test_native_read_search_permissions_compaction_and_same_thread_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = prepared(root)
            await FakeFinder().run(run)
            record = load_json(run / "run.json")
            record["research"].update(summary_trigger_tokens=1, summary_keep_tokens=100)
            write_json(run / "run.json", record)
            model, step = ResearchModel(), 0

            async def answer(domain, messages, options):
                """Force native file access, denied writes and checkpoint recovery without network."""
                nonlocal step
                step += 1
                self.assertEqual(messages[0].text.count("# Original supplied factsheet access"), 1)
                if step == 1:
                    self.assertFalse(any("SPECIAL_RULE" in m.text for m in messages))
                    return AIMessage(content="Locate source", tool_calls=[{"name": "grep", "id": "find",
                        "args": {"pattern": "SPECIAL_RULE", "path": "/inputs/fact_sheet.md", "output_mode": "content"}}])
                if step == 2:
                    return AIMessage(content="Read qualification", tool_calls=[{"name": "read_file", "id": "read",
                        "args": {"file_path": "/inputs/fact_sheet.md", "offset": 499, "limit": 5}}])
                if step == 3:
                    self.assertTrue(any("2030 deadline" in m.text for m in messages if isinstance(m, ToolMessage)))
                    raise TimeoutError("offline interruption")
                if step == 4:
                    return AIMessage(content="Check boundaries", tool_calls=[
                        {"name": "write_file", "id": "deny", "args": {"file_path": "/inputs/fact_sheet.md", "content": "bad"}},
                        {"name": "read_file", "id": "escape", "args": {"file_path": "/inputs/../../.env"}},
                        {"name": "read_file", "id": "other", "args": {"file_path": "/other-run/private.md"}}])
                results = [m.text.lower() for m in messages if isinstance(m, ToolMessage)]
                self.assertTrue(any("denied" in m for m in results))
                self.assertTrue(any("error" in m or "not found" in m for m in results))
                return AIMessage(content="# Checked\nOriginal condition and 2030 exception retained.\n")

            model.custom = answer
            with model.offline(root / "checkpoints"):
                await run_all(run)
                first = load_json(run / "run.json")
                job = next(iter(first["research"]["jobs"].values()))
                self.assertEqual(job["status"], "failed", (run / "run.log").read_text())
                used = job["budget"]["used"]
                await run_all(run, retry_failed=True)
                final = load_json(run / "run.json")
                done = next(iter(final["research"]["jobs"].values()))
                self.assertEqual(final["status"], "complete", (run / "run.log").read_text())
                self.assertEqual(done["thread_id"], job["thread_id"])
                self.assertGreater(done["budget"]["used"], used)
                calls = len(model.calls)
                await run_all(run)
                self.assertEqual(len(model.calls), calls)
            self.assertEqual((run / done["root"] / "inputs/fact_sheet.md").read_bytes(), SOURCE)
            self.assertIn("compaction_finished", (run / "run.log").read_text())
            self.assertNotIn("SPECIAL_RULE", (run / "run.log").read_text())

    async def test_source_read_remains_available_during_finalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = prepared(root)
            await FakeFinder().run(run)
            seed_domain(run, root / "checkpoints", 70)
            model = ResearchModel()

            async def answer(domain, messages, options):
                """The existing finalization tool policy still permits original-source reads."""
                self.assertNotIn("search_web", model.surfaces[-1])
                if not any(isinstance(m, ToolMessage) for m in messages):
                    return AIMessage(content="Check", tool_calls=[{"name": "read_file", "id": "original",
                        "args": {"file_path": "/inputs/fact_sheet.md", "offset": 499, "limit": 5}}])
                self.assertTrue(any("2030 deadline" in m.text for m in messages if isinstance(m, ToolMessage)))
                return AIMessage(content="Original meaning retained.")

            model.custom = answer
            with model.offline(root / "checkpoints"):
                await run_all(run)
            self.assertEqual(load_json(run / "run.json")["status"], "complete", (run / "run.log").read_text())

    async def test_alternate_objective_and_new_prompt_snapshots_preserve_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parent = prepared(root)
            await FakeFinder().run(parent)
            before = snapshot(parent)
            objective = root / "technical.md"
            objective.write_text("TECHNICAL_ONLY: Investigate material specifications, not risk sections.")
            run = create_research_run(parent, root / "runs", research_instruction=objective, public_input_confirmed=True)
            frozen = (run / "_internal/inputs/user_research_instruction.md").read_bytes()
            objective.write_text("CHANGED AFTER CREATION")
            from ML.deep_research.research_module.backend.settings import PROMPTS_DIR
            for name in ("domain_research", "research_summary", "read_document"):
                self.assertEqual((run / f"_internal/inputs/prompts/{name}.md").read_bytes(),
                                 (PROMPTS_DIR / f"{name}.md").read_bytes())
            model = ResearchModel()

            async def answer(domain, messages, options):
                """A user-supplied objective replaces the default without changing the harness."""
                self.assertIn("TECHNICAL_ONLY", messages[0].text)
                self.assertNotIn("## Risks and corresponding actions", messages[0].text)
                self.assertNotIn("CHANGED AFTER CREATION", messages[0].text)
                return AIMessage(content="## Material specification\nUnknown grade; no source claim invented.")

            model.custom = answer
            with model.offline(root / "checkpoints"):
                await run_all(run)
            self.assertEqual(load_json(run / "run.json")["status"], "complete", (run / "run.log").read_text())
            self.assertEqual((run / "_internal/inputs/user_research_instruction.md").read_bytes(), frozen)
            self.assertEqual(snapshot(parent), before)


if __name__ == "__main__":
    unittest.main()
