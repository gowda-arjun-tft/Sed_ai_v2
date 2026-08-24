from __future__ import annotations

import asyncio
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ML.deep_research.layer2.fs import load_json, read_text, slug, write_json
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.runner import run_research
from ML.deep_research.layer3.settings import DOMAIN_NAMES, SCHEMA_VERSION
from tests.common import create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(create_complete_run(root), root / "l3", public_input_confirmed=True)


def _domain_state(domain: str) -> dict:
    return {"messages": [AIMessage(content=f"# {domain}\n\nFinal domain report.\n")]}


class FakeGraph:
    order: list[str] = []
    checkpointed: set[str] = set()
    active = 0
    maximum = 0

    def __init__(self, actor: str = "", *, failing: str = ""):
        self.actor = actor
        self.failing = failing
        self.calls = 0
        self.actors: list[str] = []
        self.inputs: list[object] = []
        self.thread_ids: list[str] = []
        self.sessions: list[str] = []

    async def aget_state(self, config):
        if config["configurable"]["thread_id"] in FakeGraph.checkpointed:
            return SimpleNamespace(values={"messages": []}, next=("model",))
        return SimpleNamespace(values={}, next=())

    async def ainvoke(self, value, **kwargs):
        actor = self.actor or kwargs["context"].agent
        thread_id = kwargs["config"]["configurable"]["thread_id"]
        self.calls += 1
        self.actors.append(actor)
        self.inputs.append(value)
        self.thread_ids.append(thread_id)
        self.sessions.append(kwargs["context"].session_id)
        FakeGraph.order.append(actor)
        FakeGraph.active += 1
        FakeGraph.maximum = max(FakeGraph.maximum, FakeGraph.active)
        await asyncio.sleep(0)
        FakeGraph.active -= 1
        if actor == self.failing:
            FakeGraph.checkpointed.add(thread_id)
            raise RuntimeError("provider failure")
        if actor == "property-synthesis":
            return {"messages": [AIMessage(content="# Property decision\n\nProceed.\n")]}
        return _domain_state(actor)


@asynccontextmanager
async def _saver(_run_dir):
    yield object()


class Layer3RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeGraph.order = []
        FakeGraph.checkpointed = set()
        FakeGraph.active = 0
        FakeGraph.maximum = 0

    async def _run(
        self,
        run_dir: Path,
        *,
        fail: str = "",
        fail_synthesis: bool = False,
        retry_failed: bool = False,
    ):
        coordinator_graph = FakeGraph(failing=fail)
        constructor_calls = 0

        def coordinator(_run_dir, _saver):
            nonlocal constructor_calls
            constructor_calls += 1
            return coordinator_graph

        synthesis = FakeGraph(
            "property-synthesis",
            failing="property-synthesis" if fail_synthesis else "",
        )
        with (
            patch("ML.deep_research.layer3.runner.checkpoint_saver", _saver),
            patch("ML.deep_research.layer3.runner.from_run", return_value=object()),
            patch(
                "ML.deep_research.layer3.runner.create_domain_coordinator_harness",
                side_effect=coordinator,
            ),
            patch(
                "ML.deep_research.layer3.runner.create_synthesis_harness",
                return_value=synthesis,
            ),
        ):
            await run_research(run_dir, retry_failed=retry_failed)
        return coordinator_graph, synthesis, constructor_calls

    async def test_coordinators_run_one_at_a_time_then_synthesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            coordinator, _, constructor_calls = await self._run(run_dir)
            run = load_json(run_dir / "run.json")

        self.assertEqual(FakeGraph.order, [*DOMAIN_NAMES, "property-synthesis"])
        self.assertEqual(FakeGraph.maximum, 1)
        self.assertEqual(constructor_calls, 1)
        self.assertEqual(coordinator.calls, len(DOMAIN_NAMES))
        self.assertEqual(coordinator.actors, list(DOMAIN_NAMES))
        self.assertEqual(run["status"], "complete")
        self.assertTrue(all(item["status"] == "complete" for item in run["execution"]["domains"].values()))
        self.assertEqual(run["execution"]["final"]["status"], "complete")

    async def test_publishes_model_responses_without_auxiliary_artifact_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            first = run_dir / "domains" / slug(DOMAIN_NAMES[0])
            paths = {path.relative_to(first).as_posix() for path in first.rglob("*.md")}
            answer = read_text(run_dir / "research" / "final.md")

        self.assertEqual(paths, {"final.md"})
        self.assertEqual(answer, "# Property decision\n\nProceed.\n")

    async def test_transport_failure_does_not_stop_other_domains_or_synthesis(self):
        failed = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            coordinator, synthesis, constructor_calls = await self._run(run_dir, fail=failed)
            run = load_json(run_dir / "run.json")

        self.assertEqual(constructor_calls, 1)
        self.assertEqual(coordinator.calls, len(DOMAIN_NAMES))
        self.assertEqual(synthesis.calls, 1)
        self.assertEqual(FakeGraph.order, [*DOMAIN_NAMES, "property-synthesis"])
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["execution"]["domains"][failed]["status"], "failed")

    async def test_resume_skips_every_completed_model_response(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            FakeGraph.order = []
            coordinator, synthesis, constructor_calls = await self._run(run_dir)

        self.assertEqual(FakeGraph.order, [])
        self.assertEqual(constructor_calls, 1)
        self.assertEqual(coordinator.calls, 0)
        self.assertEqual(synthesis.calls, 0)

    async def test_retry_failed_resumes_domain_and_restarts_changed_synthesis(self):
        failed = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir, fail=failed)
            before_run = load_json(run_dir / "run.json")
            old_thread = before_run["execution"]["domains"][failed]["thread_id"]
            old_synthesis_thread = before_run["execution"]["final"]["thread_id"]
            FakeGraph.order = []
            coordinator, synthesis, _ = await self._run(run_dir, retry_failed=True)
            after_run = load_json(run_dir / "run.json")
            after = after_run["execution"]["domains"][failed]
            final = after_run["execution"]["final"]

        self.assertEqual(after["attempt"], 2)
        self.assertEqual(after["thread_id"], old_thread)
        self.assertEqual(coordinator.inputs, [None])
        self.assertEqual(coordinator.sessions, [f"{old_thread}:attempt-2"])
        self.assertEqual(final["attempt"], 2)
        self.assertNotEqual(final["thread_id"], old_synthesis_thread)
        self.assertIsInstance(synthesis.inputs[0], dict)
        self.assertEqual(FakeGraph.order, [failed, "property-synthesis"])

    async def test_retry_failed_resumes_unchanged_failed_synthesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir, fail_synthesis=True)
            before = load_json(run_dir / "run.json")["execution"]["final"]
            FakeGraph.order = []
            _, synthesis, _ = await self._run(run_dir, retry_failed=True)
            after = load_json(run_dir / "run.json")["execution"]["final"]

        self.assertEqual(after["attempt"], 2)
        self.assertEqual(after["thread_id"], before["thread_id"])
        self.assertEqual(synthesis.inputs, [None])
        self.assertEqual(
            synthesis.sessions,
            [f"{before['thread_id']}:attempt-2"],
        )
        self.assertEqual(FakeGraph.order, ["property-synthesis"])

    async def test_deepagents_retry_reuses_completed_sibling_and_tool_call(self):
        class BoundFake(FakeMessagesListChatModel):
            @property
            def _llm_type(self):
                return "checkpoint-retry-fake"

            def bind_tools(self, _tools, *, tool_choice=None, **_kwargs):
                return self

        class FailAfterTool(BoundFake):
            call_count: int = 0

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                self.call_count += 1
                if self.call_count == 2:
                    raise RuntimeError("fail after tool")
                return await super()._agenerate(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                )

        tool_calls = {"count": 0}

        @tool
        def lookup(value: str) -> str:
            """Lookup one fixture value."""
            tool_calls["count"] += 1
            return f"found {value}"

        root = BoundFake(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "args": {"description": "do A", "subagent_type": "a"},
                            "id": "call-a",
                        },
                        {
                            "name": "task",
                            "args": {"description": "do B", "subagent_type": "b"},
                            "id": "call-b",
                        },
                    ],
                ),
                AIMessage(content="root final"),
            ]
        )
        sibling = BoundFake(
            responses=[AIMessage(content="A final"), AIMessage(content="A rerun")]
        )
        failing = FailAfterTool(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup",
                            "args": {"value": "x"},
                            "id": "lookup-1",
                        }
                    ],
                ),
                AIMessage(content="B final"),
            ]
        )

        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "checkpoints.sqlite3"
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                graph = create_deep_agent(
                    model=root,
                    tools=[],
                    subagents=[
                        {
                            "name": "a",
                            "description": "A",
                            "system_prompt": "A",
                            "tools": [],
                            "model": sibling,
                        },
                        {
                            "name": "b",
                            "description": "B",
                            "system_prompt": "B",
                            "tools": [lookup],
                            "model": failing,
                        },
                    ],
                    checkpointer=saver,
                )
                config = {"configurable": {"thread_id": "retry-probe"}}
                with self.assertRaisesRegex(RuntimeError, "fail after tool"):
                    await graph.ainvoke(
                        {"messages": [{"role": "user", "content": "start"}]},
                        config=config,
                    )
                sibling_calls = sibling.i
                result = await graph.ainvoke(None, config=config)

        self.assertEqual(result["messages"][-1].text, "root final")
        self.assertEqual(sibling.i, sibling_calls)
        self.assertEqual(tool_calls["count"], 1)
        self.assertEqual(failing.call_count, 3)

    async def test_old_schema_is_rejected_before_graph_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["schema_version"] = SCHEMA_VERSION - 1
            write_json(run_dir / "run.json", run)
            with self.assertRaisesRegex(ValueError, "fresh Layer 3"):
                await run_research(run_dir)


if __name__ == "__main__":
    unittest.main()
