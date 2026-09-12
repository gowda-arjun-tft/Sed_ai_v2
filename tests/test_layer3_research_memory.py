"""Forced compaction, domain isolation, unbounded graph policy and operational input limits."""

import asyncio
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ML.deep_research.layer2.ML.context import InputSizeError
from ML.deep_research.layer2.backend.fs import load_json, text_hash, write_json
from ML.deep_research.layer3 import run_all
from ML.deep_research.layer3.research_memory import check_input, count_input
from tests.research_fixtures import ResearchModel, linked_run


class ResearchMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_early_evidence_and_conversation_survive_native_compaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            record = load_json(run / "run.json")
            record["research"].update(summary_trigger_tokens=1, summary_keep_tokens=100)
            write_json(run / "run.json", record)
            model = ResearchModel()
            step, evidence_path = 0, None
            seen_archive = []

            async def replies(domain, messages, options):
                """Read early evidence again after several forced compaction boundaries."""
                nonlocal step, evidence_path
                step += 1
                if step == 1:
                    return AIMessage(content="Investigate", tool_calls=[{"name": "read_source", "args": {
                        "url": "https://official.example/record"}, "id": "early-read"}])
                for message in messages:
                    if isinstance(message, ToolMessage) and "Saved: /evidence/" in message.text:
                        evidence_path = re.search(r"Saved: (/evidence/[^\n]+)", message.text).group(1)
                    if isinstance(message, HumanMessage) and "/archive/conversation_history/" in message.text:
                        seen_archive.append(message.text)
                if step == 2:
                    return AIMessage(content="Save findings", tool_calls=[{"name": "write_file", "args": {
                        "file_path": "/notes/later.md", "content": "Later question " * 300}, "id": "later-note"}])
                if step == 3:
                    self.assertIsNotNone(evidence_path)
                    return AIMessage(content="Reopen evidence", tool_calls=[{"name": "read_file", "args": {
                        "file_path": evidence_path}, "id": "read-early-file"}])
                self.assertTrue(any(isinstance(m, ToolMessage) and "2030" in m.text for m in messages))
                return AIMessage(content="# Report\nRetained original scope and 2030 exception.\n")

            model.custom = replies
            with model.offline(root / "checkpoints"):
                await run_all(run)
            record = load_json(run / "run.json")
            self.assertEqual(record["status"], "complete", (run / "run.log").read_text())
            self.assertTrue(seen_archive)
            archives = list((run / "_internal/trace/research").rglob("conversation_history/*.md"))
            self.assertTrue(archives)
            combined = "\n".join(path.read_text(encoding="utf-8") for path in archives)
            self.assertIn("early-read", combined)
            self.assertIn("2030", combined)
            self.assertIn("compaction_finished", (run / "run.log").read_text())
            job = next(iter(record["research"]["jobs"].values()))
            ledger = load_json(run / job["root"] / "calls.json")["calls"]
            self.assertEqual(len(ledger), len(model.calls))
            self.assertIn("summary", {c["kind"] for c in ledger})
            self.assertTrue(all("Runtime call allowance:" in group[0].text for _, group, _ in model.calls))
            self.assertTrue(all("# Selected user research instruction" in group[0].text
                                for _, group, _ in model.calls if isinstance(group[0], SystemMessage)))
            # Every dispatched call must preserve complete tool-call/result groups.
            for _, messages, _ in model.calls:
                pending = set()
                for message in messages:
                    if isinstance(message, AIMessage):
                        self.assertFalse(pending)
                        pending = {call["id"] for call in message.tool_calls}
                    elif isinstance(message, ToolMessage):
                        self.assertIn(message.tool_call_id, pending)
                        pending.remove(message.tool_call_id)
                self.assertFalse(pending)

    async def test_native_permissions_block_writes_to_evidence_and_host_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            model = ResearchModel()
            step = 0

            async def replies(domain, messages, options):
                """Probe native tool boundaries rather than trusting declared tool descriptions."""
                nonlocal step
                step += 1
                if step == 1:
                    return AIMessage(content="Probe", tool_calls=[
                        {"name": "write_file", "id": "bad-input", "args": {"file_path": "/inputs/context.md", "content": "OVERWRITE"}},
                        {"name": "write_file", "id": "bad-archive", "args": {"file_path": "/archive/evil.md", "content": "OVERWRITE"}},
                        {"name": "read_file", "id": "host", "args": {"file_path": "/inputs/../../.env"}},
                        {"name": "read_file", "id": "other", "args": {"file_path": "/other-domain/notes/private.md"}}])
                results = [m.text for m in messages if isinstance(m, ToolMessage)]
                self.assertEqual(len(results), 4)
                self.assertTrue(all("error" in t.lower() or "denied" in t.lower() or "not found" in t.lower() for t in results), results)
                return AIMessage(content="")  # Empty completions are preserved, not retried.

            model.custom = replies
            with model.offline(root / "checkpoints"):
                await run_all(run)
            record = load_json(run / "run.json")
            self.assertEqual(record["status"], "complete", (run / "run.log").read_text())
            job = next(iter(record["research"]["jobs"].values()))
            self.assertEqual((run / job["output_path"]).read_text(), "")
            self.assertNotIn("OVERWRITE", (run / job["root"] / "inputs/context.md").read_text(encoding="utf-8"))
            self.assertFalse((run / job["root"] / "archive/evil.md").exists())

    async def test_input_accounting_includes_tools_and_followup_and_preserves_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["small", "large"])
            record = load_json(run / "run.json")
            small = [SystemMessage(content="Rules"), HumanMessage(content="Input")]
            tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
            self.assertGreater(check_input(small, record, tools=tools), check_input(small, record))
            with self.assertRaises(InputSizeError):
                check_input([HumanMessage(content="large " * 100)], record, ceiling=10)
            policy = record["research"]
            for forbidden in ("max_turns", "max_tool_calls", "max_seconds", "budget", "max_output_tokens"):
                self.assertNotIn(forbidden, policy)
            # Enormous follow-up tool schemas/context fail before a fake/provider call.
            from ML.deep_research.layer3.research_memory import ResearchGuard
            from langchain.agents.middleware.types import ModelRequest
            from unittest.mock import AsyncMock, Mock
            request = ModelRequest(model=Mock(profile={}), messages=[HumanMessage(content="followup " * 100)],
                                   tools=tools, model_settings={})
            record["research"]["maximum_tokens"] = 20
            guard = ResearchGuard(record, root, "fingerprint", Mock())
            handler = AsyncMock()
            with self.assertRaises(InputSizeError):
                await guard.awrap_model_call(request, handler)
            handler.assert_not_awaited()

    async def test_seven_domains_are_sequential_and_missing_checkpoint_is_not_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, [str(i) for i in range(7)])
            model = ResearchModel()
            model.fail_domain = "source_finder/000001"
            with model.offline(root / "checkpoints"):
                await run_all(run)
                self.assertEqual(model.peak, 1)
                record = load_json(run / "run.json")
                job = record["research"]["jobs"][model.fail_domain]
                Path(job["checkpoint_path"]).unlink()  # Disposable fixture only.
                model.fail_domain = None
                calls = len(model.calls)
                await run_all(run, retry_failed=True)
                self.assertEqual(len(model.calls), calls)
                self.assertEqual(load_json(run / "run.json")["research"]["jobs"]["source_finder/000001"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
