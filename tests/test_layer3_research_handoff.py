"""Frozen user objectives, read-only prior work and execution-owned transports."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer3 import run_all
from ML.deep_research.layer3.domain_research import prepare_domain
from ML.deep_research.layer3.research_run import create_research_run
from tests.layer3_fixtures import new_run, snapshot
from tests.research_fixtures import ResearchModel, linked_run


class ResearchHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def test_objective_snapshots_and_readonly_checkpoint_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parent = await linked_run(root)
            record = load_json(parent / "run.json")
            record["research"]["checkpoint_root"] = str(root / "checkpoints")
            write_json(parent / "run.json", record)
            model = ResearchModel()
            with model.offline(root / "checkpoints"):
                await run_all(parent)
            parent_record = load_json(parent / "run.json")
            # Force export from actual checkpoint rather than the convenience working-state copy.
            for job in parent_record["research"]["jobs"].values():
                (parent / job["root"] / "working_state.json").unlink()
            before, checkpoints = snapshot(parent), snapshot(root / "checkpoints")
            instruction = root / "technical.md"
            instruction.write_text("# Technical objective\nAssess maintenance tolerances; retain 2030 exceptions.\n", encoding="utf-8")
            child = create_research_run(parent, root / "runs", public_input_confirmed=True, research_instruction=instruction)
            self.assertEqual(snapshot(parent), before)
            self.assertEqual(snapshot(root / "checkpoints"), checkpoints)
            instruction.write_text("Edited after freezing", encoding="utf-8")
            saved = load_json(child / "run.json")
            self.assertNotEqual(saved["research"]["identity"], parent_record["research"]["identity"])
            for key, item in saved["research"]["prior_work"].items():
                self.assertEqual(item["notes"], "checkpoint_export")
                self.assertEqual(item["parent_budget"]["used"], 3)
                self.assertTrue((child / item["path"] / "notes/findings.md").exists(),
                                load_json(child / item["path"] / "working_state.json"))
            self.assertEqual(saved["research"]["jobs"], {})
            model = ResearchModel()
            turn = {}

            async def replies(domain, messages, options):
                """Use saved notes and a cached source without discovery or source downloads."""
                count = turn[domain] = turn.get(domain, 0) + 1
                if count == 1:
                    context = "\n".join(m.text for m in messages)
                    self.assertIn("Technical objective", context)
                    self.assertNotIn("Edited after freezing", context)
                    self.assertIn("/prior/manifest.json", context)
                    return AIMessage(content="Inspect prior work", tool_calls=[
                        {"name": "read_file", "args": {"file_path": "/prior/notes/findings.md"}, "id": "prior-note"},
                        {"name": "read_source", "args": {"url": "https://official.example/record"}, "id": "cached-read"},
                        {"name": "write_file", "args": {"file_path": "/prior/notes/findings.md", "content": "tamper"}, "id": "denied-write"}])
                outputs = {m.tool_call_id: m.text for m in messages if isinstance(m, ToolMessage)}
                self.assertIn("医院", outputs["prior-note"])
                self.assertIn("2030", outputs["cached-read"])
                self.assertIn("denied", outputs["denied-write"].lower())
                return AIMessage(content="# Technical assessment\n2030 exception retained.\n")

            model.custom = replies
            with model.offline(root / "checkpoints"), patch(
                "ML.deep_research.layer3.domain_tools._fetch", side_effect=AssertionError("Reuse existing evidence")):
                await run_all(child)
                count = len(model.calls)
                await run_all(child)
                self.assertEqual(len(model.calls), count)
            self.assertEqual(load_json(child / "run.json")["status"], "complete", (child / "run.log").read_text())
            for key, job in load_json(child / "run.json")["research"]["jobs"].items():
                self.assertEqual(job["budget"]["used"], 2)
                self.assertNotEqual(job["thread_id"], parent_record["research"]["jobs"][key]["thread_id"])
            self.assertEqual(snapshot(parent), before)

    async def test_missing_notes_are_disclosed_and_domains_cannot_read_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parent = await linked_run(root)
            model = ResearchModel()
            model.fail_domain = "source_finder/000001"
            with model.offline(root / "checkpoints"):
                await run_all(parent)
            before = snapshot(parent)
            child = create_research_run(parent, root / "runs", public_input_confirmed=True)
            record = load_json(child / "run.json")
            item = record["research"]["prior_work"][model.fail_domain]
            self.assertEqual(item["notes"], "notes_unavailable")
            first, _, _, _ = prepare_domain(child, record, record["domains"][0], root / "checkpoints")
            self.assertFalse((first / "prior/notes/findings.md").exists())
            second, _, _, _ = prepare_domain(child, record, record["domains"][1], root / "checkpoints")
            self.assertTrue((second / "prior/notes/findings.md").exists())
            self.assertEqual(snapshot(parent), before)

    async def test_owned_clients_survive_domains_and_close_after_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root)
            from ML.deep_research.layer3.domain_research import build_model
            clients = []

            def build(*args, **kwargs):
                """Inspect real client ownership without replacing the installed model builder."""
                clients.append((kwargs["http_client"], kwargs["http_async_client"]))
                self.assertTrue(all(not client.is_closed for group in clients for client in group))
                return build_model(*args, **kwargs)

            model = ResearchModel()
            with model.offline(root / "checkpoints"), patch("ML.deep_research.layer3.domain_research.build_model", build):
                await run_all(run)
            self.assertEqual(len(clients), 2)
            self.assertIs(clients[0][0], clients[1][0])
            self.assertIs(clients[0][1], clients[1][1])
            self.assertTrue(all(client.is_closed for group in clients for client in group))
            self.assertEqual(load_json(run / "run.json")["status"], "complete")

    async def test_historical_version_one_keeps_its_frozen_no_budget_concurrency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root)
            record = load_json(run / "run.json")
            policy = record["research"]
            policy.update(version=1, max_concurrency=5)
            for key in ("maximum_calls", "wrap_up_after", "finalize_after"):
                policy.pop(key)
            write_json(run / "run.json", record)
            frozen = snapshot(run / "_internal/inputs")
            model = ResearchModel()
            with model.offline(root / "checkpoints"):
                await run_all(run)
            self.assertGreater(model.peak, 1)
            self.assertFalse(list((run / "_internal/trace/research").rglob("calls.json")))
            self.assertEqual(snapshot(run / "_internal/inputs"), frozen)
            self.assertTrue(all("Runtime call allowance:" not in m[0].text for _, m, _ in model.calls))

    def test_full_run_freezes_default_and_alternate_instructions_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = new_run(root)
            raw = (default / "_internal/inputs/user_research_instruction.md").read_text()
            for meaning in ("Risks", "Opportunities", "corresponding action", "missing record", "numerical reconciliations"):
                self.assertIn(meaning, raw)
            alternate = root / "alternate.md"
            alternate.write_text("Technical assessment only.\n", encoding="utf-8")
            run = new_run(root, research_instruction=alternate)
            self.assertEqual((run / "_internal/inputs/user_research_instruction.md").read_bytes(), alternate.read_bytes())
            before = snapshot(root / "runs")
            alternate.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                new_run(root, research_instruction=alternate)
            self.assertEqual(snapshot(root / "runs"), before)
