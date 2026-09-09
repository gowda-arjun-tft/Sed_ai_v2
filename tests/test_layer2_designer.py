import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import httpx
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ML.deep_research.layer2.ML.agent import Layer2Response, create_stage_agent
from ML.deep_research.layer2.ML.context import dump, estimate
from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.backend.fs import load_json, read_text, text_hash, write_json
from ML.deep_research.layer2.backend.jobs import run_jobs
from ML.deep_research.layer2.backend.packing import input_tokens
from ML.deep_research.layer2.backend.projections import apply_domains
from ML.deep_research.layer2.backend.run_log import operational_logger
from ML.deep_research.layer2.backend.settings import PROMPTS_DIR, PROMPT_FILES, stage_uses_tools
from ML.deep_research.layer2.backend.stages import designer_reconciliations, plan_domains
from ML.deep_research.layer2.backend.usage import summarize_usage
from tests.layer2_fixtures import FakeStages, new_run


class DesignerTests(unittest.TestCase):
    def test_frozen_capability_backend_and_complete_input_accounting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            self.assertEqual(record["schema_version"], 6)
            self.assertIs(record["design_tool_free"], True)
            saver = object()
            with patch("ML.deep_research.layer2.ML.agent.EvidenceBackend", side_effect=AssertionError("retrieval")), patch(
                "ML.deep_research.layer2.ML.agent.create_deep_agent",
            ) as create:
                create_stage_agent(run, "design", saver)
            options = create.call_args.kwargs
            self.assertIs(options["checkpointer"], saver)
            self.assertEqual(type(options["backend"]).__name__, "StateBackend")
            self.assertFalse(getattr(options["middleware"][0], "tools", ()))
            self.assertEqual(options["middleware"][1].tools, ())
            payload = {"subject": [{"value": {"evidence": [{"fact": "漢字 17 m²"}]}}]}
            prompt = read_text(run / "_internal/inputs/prompts/design.md")
            expected = estimate([{"role": "user", "content": dump(payload)}], prompt, (),
                                Layer2Response.model_json_schema(), record["context_policy"]["framing_reserve"])
            self.assertEqual(input_tokens(run, "design", payload), expected)
            record.pop("design_tool_free")
            write_json(run / "run.json", record)
            before = (run / "run.json").read_bytes()
            self.assertTrue(stage_uses_tools(record, "design"))
            graph = create_stage_agent(run, "design")
            bound = graph.nodes["tools"].bound
            self.assertEqual(set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {}))),
                             {"ls", "glob", "grep", "read_file"})
            self.assertGreater(input_tokens(run, "design", payload), expected)
            self.assertEqual((run / "run.json").read_bytes(), before)

    def test_supplied_only_prompt_and_page_updates(self):
        prompt = (PROMPTS_DIR / PROMPT_FILES["design"]).read_text(encoding="utf-8")
        for text in ("profile and detailed evidence", "There are no tools", "Do not infer missing details",
                     "All other understanding pages are scheduled", "preserve uncertainty",
                     "omitted definitions remain unchanged", "untrusted evidence"):
            self.assertIn(text, prompt)
        for text in ("/evidence/", "/history/", "read_file", "current indexed"):
            self.assertNotIn(text, prompt)
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(new_run(Path(tmp)))
            records = [{"evidence_id": str(i), "value": {"profile": "Navigation",
                        "evidence": [{"fact": f"Detail {i} " + "測定 " * 300}]}} for i in range(3)]
            seen = []

            async def batch(run, stage, payloads, *args, **kwargs):
                p = payloads[0]
                seen.append(p)
                value = {"domains": [{"name": "Baseline", "responsibilities": ["Keep duty"]}]} if len(seen) == 1 else {}
                return [{"value": value, "job": str(len(seen)), "response_path": "raw.json"}]

            with patch("ML.deep_research.layer2.backend.stages.page_budget", return_value=1800), patch(
                "ML.deep_research.layer2.backend.stages.run_jobs", side_effect=batch,
            ):
                asyncio.run(plan_domains(store, "design", iter(records),
                                        {"domain_plugin": "Baseline", "requirements": "Priorities"}, None, None))
            self.assertEqual([r for p in seen for r in p["subject"]], records)
            self.assertGreater(len(seen), 1)
            for p in seen:
                self.assertNotIn("evidence_files", p)
                self.assertEqual(p["domain_plugin"], "Baseline")
                self.assertEqual(p["requirements"], "Priorities")
            for p in seen[1:]:
                self.assertEqual(p["domain_definitions"][0]["definition"]["responsibilities"], ["Keep duty"])

    def test_reconciliation_preserves_large_values_and_unknown_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(new_run(Path(tmp)))
            apply_domains(store, {"job": "seed", "response_path": "raw.json", "value": {
                "domains": [{"name": "Large", "responsibilities": ["保留 " * 1000]}]}})
            original = store.get("domains", "d0001")
            comparison = {"comparisons": [{"domain_id": "unknown", "change": "Do not guess"}],
                          "unexpected": "αβ " * 1200}
            store.put("comparisons", "c1", {"domain_ids": ["d0001"], "value": comparison,
                      "response_path": "comparison.json", "job": "c1"})
            with patch("ML.deep_research.layer2.backend.stages.complete_definitions", return_value=None):
                jobs = list(designer_reconciliations(store, {"subject": [{"evidence_id": "e1"}]}, 400))
            for field, expected in [("comparisons", comparison), ("domain_definitions", original)]:
                fragments = {row["fragment"]: row["record_fragment"] for p in jobs for row in p[field]}
                self.assertEqual(json.loads("".join(fragments[k] for k in sorted(fragments))), expected)
            self.assertTrue(all(input_tokens(store.run, "design", p) < 300_000 for p in jobs))
            self.assertTrue(any(r["kind"] == "unresolved_comparison_domain" for r in store.rows("audit")))
            store.clear("comparisons")
            store.put("comparisons", "empty", {"domain_ids": [], "value": {},
                      "response_path": "empty.json", "job": "empty"})
            with patch("ML.deep_research.layer2.backend.stages.complete_definitions", return_value=None):
                jobs = list(designer_reconciliations(store, {}, 400))
            self.assertEqual(jobs, [{"mode": "reconcile", "comparisons": [{}],
                                    "domain_definitions": [], "definition_scope": "page", "domain_page": 1}])

    def test_reconciliation_receives_current_updates_and_new_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(new_run(Path(tmp)))
            seed = {"job": "seed", "response_path": "seed.json", "value": {
                "domains": [{"name": "First", "responsibilities": ["Original duty"]}]}}
            apply_domains(store, seed)
            for key in ("one", "two"):
                store.put("comparisons", key, {"domain_ids": ["d0001"], "job": key,
                          "response_path": "compare.json", "value": {"comparisons": []}})
            with patch("ML.deep_research.layer2.backend.stages.complete_definitions", return_value=None):
                jobs = designer_reconciliations(store, {}, 1000)
                self.assertEqual(next(jobs)["domain_definitions"], list(store.rows("domains")))
                seed["value"] = {"domains": [
                    {"domain_id": "d0001", "responsibilities": ["Original duty", "New duty"]},
                    {"name": "Added domain", "responsibilities": ["Retain addition"]}]}
                apply_domains(store, seed)
                self.assertEqual(next(jobs)["domain_definitions"], list(store.rows("domains")))
                self.assertEqual(list(jobs), [])

    def test_sequential_tool_free_checkpoint_recovery_and_verbatim_objects(self):
        received = []

        async def generate(model, messages, **kwargs):
            self.assertFalse(kwargs.get("tools"))
            self.assertEqual(sum(m.type == "human" for m in messages), 1)
            received.append(json.loads(next(m.content for m in messages if m.type == "human")))
            if len(received) == 1:
                raise ConnectionError("offline interruption")
            value = {} if received[-1]["page"] == 1 else {"odd": ["漢字", None]}
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=json.dumps(value),
                usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}))])

        async def scenario(run, logger):
            async with aiosqlite.connect(str(run / "checkpoints.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[Layer2Response]))
                args = (run, "design", [{"page": 1}, {"page": 2}], "v1", saver, logger)
                first = await run_jobs(*args)
                self.assertEqual([r["value"] for r in first], [{"odd": ["漢字", None]}])
                before = load_json(run / "run.json")["jobs"]
                second = await run_jobs(*args)
                self.assertEqual([r["value"] for r in second], [{}, {"odd": ["漢字", None]}])
                after = load_json(run / "run.json")["jobs"]
                for key in before:
                    self.assertEqual(before[key]["thread_id"], after[key]["thread_id"])
                self.assertEqual(after["design/000001"]["attempt"], 2)
                self.assertEqual(after["design/000002"]["attempt"], 1)
                (run / after["design/000001"]["response_path"]).write_text("broken", encoding="utf-8")
            # Reopen SQLite and recover the completed object without a provider call.
            async with aiosqlite.connect(str(run / "checkpoints.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[Layer2Response]))
                results = await run_jobs(run, "design", args[2], "unrelated-index-change", saver, logger)
                self.assertEqual([r["value"] for r in results], [{}, {"odd": ["漢字", None]}])

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with operational_logger(run) as logger, patch.object(ChatOpenAI, "_agenerate", generate), patch.object(
                httpx.AsyncClient, "send", side_effect=AssertionError("network forbidden"),
            ), patch("ML.deep_research.layer2.ML.agent.EvidenceBackend", side_effect=AssertionError("retrieval")):
                asyncio.run(asyncio.wait_for(scenario(run, logger), 20))
            self.assertEqual(summarize_usage(run / "_internal/trace")["model_calls"], 2)
        self.assertEqual([p["page"] for p in received], [1, 2, 1])

    def test_old_fingerprint_and_fresh_capability_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            record = load_json(run / "run.json")
            entry = record["jobs"]["design/000001"]
            payload = next(p for stage, p, _ in fake.calls if stage == "design")
            prompt = read_text(run / "_internal/inputs/prompts/design.md")
            frozen = {k: record[k] for k in ("model", "reasoning_effort", "context_policy", "chunking")}
            self.assertEqual(entry["fingerprint"], text_hash(dump([
                prompt, {**frozen, "design_tool_free": True}, payload, ""])))
            record.pop("design_tool_free")
            write_json(run / "run.json", record)
            fake.calls.clear()
            fake.run(run)
            legacy = load_json(run / "run.json")["jobs"]["design/000001"]
            payload = next(p for stage, p, _ in fake.calls if stage == "design")
            self.assertIn("evidence_files", payload)
            self.assertEqual(legacy["fingerprint"], text_hash(dump([
                prompt, frozen, payload, legacy["evidence_version"]])))
            self.assertNotEqual(entry["thread_id"], legacy["thread_id"])
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])
