import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import httpx
from deepagents.backends.utils import create_file_data
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ML.deep_research.layer2.ML.agent import Layer2Response, create_stage_agent, response_value
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.jobs import run_jobs
from ML.deep_research.layer2.backend.run_log import operational_logger
from tests.layer2_fixtures import new_run


class NativeRetrievalTests(unittest.TestCase):
    def test_native_read_only_tools_checkpoints_and_followup_budget(self):
        received = []

        async def generate(model, messages, **kwargs):
            received.append(messages)
            if len(received) <= 2:
                path = "/evidence/profile/000001.txt" if len(received) == 1 else "/secrets/.env"
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
                graph = create_stage_agent(run, "design", saver)
                config = {"configurable": {"thread_id": "native-retrieval-test"}}
                result = await graph.ainvoke({
                    "messages": [{"role": "user", "content": "Read the provided file."}],
                    "files": {"/evidence/profile/000001.txt": create_file_data("EXACT_RUN_EVIDENCE")},
                }, config)
                self.assertEqual(response_value(result), {"domains": []})
                state = await graph.aget_state(config)
                self.assertTrue(state.values["files"])
                count = len(received)
                result = await graph.ainvoke(None, config)
                self.assertEqual(response_value(result), {"domains": []})
                self.assertEqual(len(received), count)

            # Reopen persisted state through the relocated agent/serializer module.
            async with aiosqlite.connect(str(run / "test.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
                    allowed_msgpack_modules=[Layer2Response],
                ))
                graph = create_stage_agent(run, "design", saver)
                state = await graph.aget_state(config)
                self.assertIsInstance(state.values["structured_response"], Layer2Response)
                self.assertEqual(response_value(await graph.ainvoke(None, config)), {"domains": []})
                self.assertEqual(len(received), count)

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with operational_logger(run), patch.object(ChatOpenAI, "_agenerate", generate), patch.object(
                httpx.AsyncClient, "send", side_effect=AssertionError("offline test attempted network"),
            ):
                asyncio.run(scenario(run))
            log = (run / "run.log").read_text()
            self.assertEqual(log.count("input_estimate"), 3)
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
                    {"name": "read_file", "args": {"file_path": "/evidence/profile/000001.txt"},
                     "id": "read-before-interruption"},
                ])
            elif len(received) == 2:
                raise ConnectionError("offline interrupted provider")
            else:
                response = AIMessage(content='{"domains": []}')
            return ChatResult(generations=[ChatGeneration(message=response)])

        async def scenario(run, logger):
            async with aiosqlite.connect(str(run / "checkpoints.sqlite3")) as connection:
                saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
                    allowed_msgpack_modules=[Layer2Response],
                ))
                args = (run, "design", [{"task": "Read the profile"}],
                        {"/evidence/profile/000001.txt": "PRESERVED_EVIDENCE"}, saver, logger)
                self.assertEqual(await run_jobs(*args), [])
                first = load_json(run / "run.json")["jobs"]["design/000001"]
                self.assertEqual(first["status"], "failed")
                result = await run_jobs(*args)
                second = load_json(run / "run.json")["jobs"]["design/000001"]
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
        self.assertEqual(len(received), 3)
        self.assertTrue(any("PRESERVED_EVIDENCE" in str(m.content)
                            for m in received[2] if isinstance(m, ToolMessage)))
        self.assertEqual(sum(m.type == "human" for m in received[2]), 1)
