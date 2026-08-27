from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ML.deep_research.layer2.fs import load_json, slug, write_json
from ML.deep_research.layer3.document_extraction import manifest_path
from ML.deep_research.layer3.document_supervisor import _run_worker
from ML.deep_research.layer3.pipeline.progress import stage_record
from ML.deep_research.layer3.runner import _publish_domain, _run_stage


class _ParallelState(TypedDict, total=False):
    seed: str
    first: str
    second: str


def _parallel_graph(saver):
    async def first(_state):
        return {
            "first": interrupt(
                {"type": "document_extraction", "source_id": "source-a", "url": "a"}
            )
        }

    async def second(_state):
        return {
            "second": interrupt(
                {"type": "document_extraction", "source_id": "source-b", "url": "b"}
            )
        }

    builder = StateGraph(_ParallelState)
    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge(START, "second")
    builder.add_edge("first", END)
    builder.add_edge("second", END)
    return builder.compile(checkpointer=saver)


def _run_state(run_dir: Path) -> tuple[dict, dict]:
    run = {"run_id": "interrupt-test", "status": "created"}
    record = stage_record(run, "coordinator", "test-domain", 0)
    run["execution"] = {"domains": {"test-domain": record}}
    (run_dir / "usage.jsonl").touch()
    write_json(run_dir / "run.json", run)
    return run, record


class Layer3DocumentInterruptTests(unittest.IsolatedAsyncioTestCase):
    async def test_nested_deepagent_tool_interrupt_reaches_supervisor(self):
        class BoundFake(FakeMessagesListChatModel):
            @property
            def _llm_type(self):
                return "document-interrupt-fake"

            def bind_tools(self, _tools, *, tool_choice=None, **_kwargs):
                return self

        tool_calls = {"count": 0}

        @tool
        def open_document(url: str) -> str:
            """Open one document fixture."""
            tool_calls["count"] += 1
            return str(
                interrupt(
                    {
                        "type": "document_extraction",
                        "source_id": "nested-source",
                        "url": url,
                    }
                )
            )

        root = BoundFake(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "args": {
                                "description": "read the document",
                                "subagent_type": "reader",
                            },
                            "id": "task-1",
                        }
                    ],
                ),
                AIMessage(content="root final"),
            ]
        )
        reader = BoundFake(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "open_document",
                            "args": {"url": "https://example.test/file.pdf"},
                            "id": "document-1",
                        }
                    ],
                ),
                AIMessage(content="reader final"),
            ]
        )
        seen = []

        async def process(_run_dir, interrupts):
            seen.extend(interrupts)
            return {item.id: "extracted document text" for item in interrupts}

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            run, record = _run_state(run_dir)
            database = run_dir / "checkpoints.sqlite3"
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                graph = create_deep_agent(
                    model=root,
                    tools=[],
                    subagents=[
                        {
                            "name": "reader",
                            "description": "Reads documents",
                            "system_prompt": "Read the requested document.",
                            "tools": [open_document],
                            "model": reader,
                        }
                    ],
                    checkpointer=saver,
                )
                with patch(
                    "ML.deep_research.layer3.runner.process_document_interrupts",
                    side_effect=process,
                ):
                    result = await _run_stage(
                        graph,
                        run_dir,
                        run,
                        record,
                        object(),
                        {"messages": [{"role": "user", "content": "start"}]},
                        asyncio.Lock(),
                        retry_failed=False,
                    )

        self.assertEqual(result["messages"][-1].text, "root final")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].value["source_id"], "nested-source")
        self.assertEqual(tool_calls["count"], 2)
        self.assertEqual(record["status"], "staged")

    async def test_parallel_interrupts_resume_same_checkpoint_thread(self):
        seen = []

        async def process(_run_dir, interrupts):
            seen.append(interrupts)
            return {
                item.id: f"ready:{item.value['source_id']}" for item in interrupts
            }

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            run, record = _run_state(run_dir)
            database = run_dir / "checkpoints.sqlite3"
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                graph = _parallel_graph(saver)
                with patch(
                    "ML.deep_research.layer3.runner.process_document_interrupts",
                    side_effect=process,
                ):
                    result = await _run_stage(
                        graph,
                        run_dir,
                        run,
                        record,
                        object(),
                        {"seed": "start"},
                        asyncio.Lock(),
                        retry_failed=False,
                    )
                snapshot = await graph.aget_state(
                    {"configurable": {"thread_id": record["thread_id"]}}
                )

        self.assertEqual(len(seen), 1)
        self.assertEqual(len(seen[0]), 2)
        self.assertEqual(result["first"], "ready:source-a")
        self.assertEqual(result["second"], "ready:source-b")
        self.assertEqual(record["status"], "staged")
        self.assertEqual(record["attempt"], 1)
        self.assertFalse(snapshot.next)

    async def test_waiting_stage_survives_restart_without_retry_failed(self):
        async def stop_after_checkpoint(_run_dir, _interrupts):
            raise asyncio.CancelledError

        async def process(_run_dir, interrupts):
            return {item.id: f"ready:{item.value['source_id']}" for item in interrupts}

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            run, record = _run_state(run_dir)
            thread_id = record["thread_id"]
            database = run_dir / "checkpoints.sqlite3"
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                graph = _parallel_graph(saver)
                with (
                    patch(
                        "ML.deep_research.layer3.runner.process_document_interrupts",
                        side_effect=stop_after_checkpoint,
                    ),
                    self.assertRaises(asyncio.CancelledError),
                ):
                    await _run_stage(
                        graph,
                        run_dir,
                        run,
                        record,
                        object(),
                        {"seed": "start"},
                        asyncio.Lock(),
                        retry_failed=False,
                    )

            saved = load_json(run_dir / "run.json")
            saved_record = saved["execution"]["domains"]["test-domain"]
            self.assertEqual(saved["status"], "waiting_for_documents")
            self.assertEqual(saved_record["status"], "waiting_for_documents")
            self.assertEqual(saved_record["thread_id"], thread_id)
            self.assertEqual(len(saved_record["document_interrupts"]), 2)

            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                graph = _parallel_graph(saver)
                with patch(
                    "ML.deep_research.layer3.runner.process_document_interrupts",
                    side_effect=process,
                ):
                    result = await _run_stage(
                        graph,
                        run_dir,
                        saved,
                        saved_record,
                        object(),
                        {"seed": "ignored"},
                        asyncio.Lock(),
                        retry_failed=False,
                    )

        self.assertEqual(result["first"], "ready:source-a")
        self.assertEqual(result["second"], "ready:source-b")
        self.assertEqual(saved_record["status"], "staged")
        self.assertEqual(saved_record["attempt"], 1)
        self.assertEqual(saved_record["thread_id"], thread_id)

    async def test_interrupted_domain_is_not_published(self):
        async def stop_after_checkpoint(_run_dir, _interrupts):
            raise asyncio.CancelledError

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            run, record = _run_state(run_dir)
            database = run_dir / "checkpoints.sqlite3"
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                with (
                    patch(
                        "ML.deep_research.layer3.runner.process_document_interrupts",
                        side_effect=stop_after_checkpoint,
                    ),
                    self.assertRaises(asyncio.CancelledError),
                ):
                    await _publish_domain(
                        _parallel_graph(saver),
                        run_dir,
                        run,
                        record,
                        object(),
                        {"seed": "start"},
                        asyncio.Lock(),
                        retry_failed=False,
                    )

            target = run_dir / "domains" / slug(record["actor"]) / "final.md"
            saved_record = load_json(run_dir / "run.json")["execution"]["domains"][
                "test-domain"
            ]

        self.assertFalse(target.exists())
        self.assertEqual(saved_record["status"], "waiting_for_documents")

    async def test_parent_terminates_a_worker_after_its_heartbeat_expires(self):
        class Process:
            pid = 123
            returncode = None
            stopped = False

            def communicate(self):
                while not self.stopped:
                    pass
                self.returncode = -1
                return b"", b""

            def terminate(self):
                self.stopped = True

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            source_id = "f" * 64
            write_json(manifest_path(run_dir, source_id), {"status": "running", "worker_pid": 123, "heartbeat_at": "old"})
            process = Process()
            policy = type("Policy", (), {
                "worker_heartbeat_seconds": 0.001,
                "worker_stale_seconds": 1,
            })()
            with (
                patch("ML.deep_research.layer3.document_supervisor.subprocess.Popen", return_value=process),
                patch("ML.deep_research.layer3.document_supervisor._heartbeat_is_fresh", return_value=False),
                self.assertRaisesRegex(ChildProcessError, "heartbeat expired"),
            ):
                await _run_worker(run_dir, source_id, policy)

        self.assertTrue(process.stopped)


if __name__ == "__main__":
    unittest.main()
