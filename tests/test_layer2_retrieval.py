import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import httpx
from ML.deep_research.layer2.backend.evidence import EvidenceStore
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ML.deep_research.layer2.ML.agent import Layer2Response, create_stage_agent, response_value
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.fs import write_json
from ML.deep_research.layer2.ML.context import estimate
from ML.deep_research.layer2.backend.jobs import run_jobs
from ML.deep_research.layer2.backend.run_log import operational_logger
from ML.deep_research.layer2.backend.usage import summarize_usage
from tests.layer2_fixtures import new_run


class NativeRetrievalTests(unittest.TestCase):
    def test_native_followups_archive_complete_history_without_summarizing(self):
        received = []

        async def generate(model, messages, **kwargs):
            received.append(messages)
            self.assertLess(estimate(messages, tools=kwargs.get("tools", ())), 50_000)
            if len(received) <= 10:
                response = AIMessage(content="", tool_calls=[{
                    "name": "read_file", "args": {"file_path": "/evidence/detail/0000/000001.txt"},
                    "id": f"r{len(received)}"}])
            else:
                response = AIMessage(content='{"domains": []}')
            return ChatResult(generations=[ChatGeneration(message=response)])

        async def scenario(run):
            store = EvidenceStore(run)
            store.add_text("detail", " unique" * 7_000)
            async with aiosqlite.connect(str(run / "offload.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[Layer2Response]))
                graph = create_stage_agent(run, "observations", saver)
                result = await graph.ainvoke({"messages": [{"role": "user", "content": "KEEP_ORIGINAL_JOB"}]},
                                             {"configurable": {"thread_id": "offload", "evidence_version": store.snapshot()}})
                self.assertEqual(response_value(result), {"domains": []})
            archives = list((run / "_internal/trace/history").rglob("*.json"))
            self.assertTrue(archives)
            self.assertTrue(any("unique" in p.read_text(encoding="utf-8") for p in archives))
            self.assertTrue(any("/history/" in str(m.content) for m in received[-1]))
            self.assertTrue(any("KEEP_ORIGINAL_JOB" in str(m.content) for m in received[-1]))
            for messages in received:
                calls = {c["id"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
                self.assertTrue(all(m.tool_call_id in calls for m in messages if isinstance(m, ToolMessage)))

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            record["context_policy"].update(target_tokens=35_000, maximum_tokens=50_000)
            write_json(run / "run.json", record)
            with operational_logger(run), patch.object(ChatOpenAI, "_agenerate", generate), patch.object(
                httpx.AsyncClient, "send", side_effect=AssertionError("offline test attempted network"),
            ):
                asyncio.run(scenario(run))
        self.assertEqual(len(received), 11)

    def test_native_read_only_tools_checkpoints_and_followup_budget(self):
        received = []
        reads = []
        original_body = EvidenceStore.body

        def transient_read(store, *args):
            reads.append(1)
            if len(reads) == 1:
                error = sqlite3.OperationalError("PRIVATE_DATABASE_PAYLOAD")
                error.sqlite_errorcode = sqlite3.SQLITE_PROTOCOL
                raise error
            return original_body(store, *args)

        async def generate(model, messages, **kwargs):
            received.append(messages)
            if len(received) <= 2:
                path = "/evidence/profile/0000/000001.txt" if len(received) == 1 else "/secrets/.env"
                response = AIMessage(content="", tool_calls=[
                    {"name": "read_file", "args": {"file_path": path},
                     "id": f"read-{len(received)}"}
                ])
            else:
                response = AIMessage(content=json.dumps({"domains": []}))
            return ChatResult(generations=[ChatGeneration(message=response)])

        async def scenario(run):
            async with aiosqlite.connect(str(run / "test.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
                    allowed_msgpack_modules=[Layer2Response],
                ))
                graph = create_stage_agent(run, "observations", saver)
                store = EvidenceStore(run)
                store.add_text("profile", "EXACT_RUN_EVIDENCE")
                config = {"configurable": {"thread_id": "native-retrieval-test", "evidence_version": store.snapshot()}}
                result = await graph.ainvoke({
                    "messages": [{"role": "user", "content": "Read the provided file."}],
                }, config)
                self.assertEqual(response_value(result), {"domains": []})
                state = await graph.aget_state(config)
                self.assertFalse(state.values.get("files"))
                count = len(received)
                result = await graph.ainvoke(None, config)
                self.assertEqual(response_value(result), {"domains": []})
                self.assertEqual(len(received), count)

            # Reopen persisted state through the relocated agent/serializer module.
            async with aiosqlite.connect(str(run / "test.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
                    allowed_msgpack_modules=[Layer2Response],
                ))
                graph = create_stage_agent(run, "observations", saver)
                state = await graph.aget_state(config)
                self.assertIsInstance(state.values["structured_response"], Layer2Response)
                self.assertEqual(response_value(await graph.ainvoke(None, config)), {"domains": []})
                self.assertEqual(len(received), count)

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with operational_logger(run), patch.object(EvidenceStore, "body", transient_read), patch(
                "ML.deep_research.layer2.ML.evidence_backend.time.sleep",
            ), patch.object(ChatOpenAI, "_agenerate", generate), patch.object(
                httpx.AsyncClient, "send", side_effect=AssertionError("offline test attempted network"),
            ):
                asyncio.run(scenario(run))
            log = (run / "run.log").read_text()
            self.assertEqual(log.count("input_estimate"), 3)
            self.assertEqual(log.count("sqlite_read_retry"), 1)
            self.assertEqual(log.count("sqlite_read_recovered"), 1)
            self.assertNotIn("PRIVATE_DATABASE_PAYLOAD", log)
        self.assertEqual(len(received), 3)
        self.assertTrue(any("EXACT_RUN_EVIDENCE" in str(m.content)
                            for m in received[1] if isinstance(m, ToolMessage)))
        unavailable = [m for m in received[2] if isinstance(m, ToolMessage) and m.tool_call_id == "read-2"]
        self.assertTrue(unavailable)
        self.assertIn("not found", str(unavailable[0].content).lower())

    def test_failed_retrieval_resumes_checkpoint_without_repeating_read(self):
        received = []

        async def generate(model, messages, **kwargs):
            received.append(messages)
            if len(received) == 1:
                response = AIMessage(content="", tool_calls=[
                    {"name": "read_file", "args": {"file_path": "/evidence/profile/0000/000001.txt"},
                     "id": "read-before-interruption"},
                ], usage_metadata={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11})
            elif len(received) == 2:
                raise ConnectionError("offline interrupted provider")
            else:
                response = AIMessage(content='{"domains": []}',
                                     usage_metadata={"input_tokens": 12, "output_tokens": 2, "total_tokens": 14})
            return ChatResult(generations=[ChatGeneration(message=response)])

        async def scenario(run, logger):
            async with aiosqlite.connect(str(run / "_internal/trace/checkpoints.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
                    allowed_msgpack_modules=[Layer2Response],
                ))
                store = EvidenceStore(run)
                store.add_text("profile", "PRESERVED_EVIDENCE")
                args = (run, "observations", [{"task": "Read the profile"}], store.snapshot(), saver, logger)
                self.assertEqual(await run_jobs(*args), [])
                first = load_json(run / "run.json")["jobs"]["observations/000001"]
                self.assertEqual(first["status"], "failed")
                result = await run_jobs(*args)
                second = load_json(run / "run.json")["jobs"]["observations/000001"]
                self.assertEqual(result[0]["value"], {"domains": []})
                self.assertEqual(first["thread_id"], second["thread_id"])
                self.assertEqual(second["attempt"], 2)
                # A lost response file is recovered from the completed checkpoint, not repaired.
                (run / second["response_path"]).write_text("unreadable", encoding="utf-8")
                self.assertEqual((await run_jobs(*args))[0]["value"], {"domains": []})

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with operational_logger(run) as logger, patch.object(ChatOpenAI, "_agenerate", generate), patch.object(
                httpx.AsyncClient, "send", side_effect=AssertionError("offline test attempted network"),
            ):
                asyncio.run(asyncio.wait_for(scenario(run, logger), timeout=20))
            usage = summarize_usage(run / "_internal/trace")
            self.assertEqual(usage["model_calls"], 2)
            self.assertEqual(usage["total_tokens"], 25)
            self.assertFalse((run / "usage.jsonl").exists())
        self.assertEqual(len(received), 3)
        self.assertTrue(any("PRESERVED_EVIDENCE" in str(m.content)
                            for m in received[2] if isinstance(m, ToolMessage)))
        self.assertEqual(sum(m.type == "human" for m in received[2]), 1)
