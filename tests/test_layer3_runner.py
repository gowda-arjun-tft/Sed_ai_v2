from __future__ import annotations

import asyncio
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer2.backend.fs import load_json, read_text, slug, write_json
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.runner import run_research
from ML.deep_research.layer3.settings import DOMAIN_NAMES
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
        researcher_graph = FakeGraph(failing=fail)
        constructor_calls = 0

        def researcher(_run_dir, _saver):
            nonlocal constructor_calls
            constructor_calls += 1
            return researcher_graph

        synthesis = FakeGraph(
            "property-synthesis",
            failing="property-synthesis" if fail_synthesis else "",
        )
        with (
            patch("ML.deep_research.layer3.runner.checkpoint_saver", _saver),
            patch("ML.deep_research.layer3.runner.from_run", return_value=object()),
            patch(
                "ML.deep_research.layer3.runner.create_domain_researcher_harness",
                side_effect=researcher,
            ),
            patch(
                "ML.deep_research.layer3.runner.create_synthesis_harness",
                return_value=synthesis,
            ),
        ):
            await run_research(run_dir, retry_failed=retry_failed)
        return researcher_graph, synthesis, constructor_calls

    async def test_researchers_run_one_at_a_time_then_synthesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            researcher, _, constructor_calls = await self._run(run_dir)
            run = load_json(run_dir / "run.json")

        self.assertEqual(FakeGraph.order, [*DOMAIN_NAMES, "property-synthesis"])
        self.assertEqual(FakeGraph.maximum, 1)
        self.assertEqual(constructor_calls, 1)
        self.assertEqual(researcher.calls, len(DOMAIN_NAMES))
        self.assertEqual(researcher.actors, list(DOMAIN_NAMES))
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
            researcher, synthesis, constructor_calls = await self._run(run_dir, fail=failed)
            run = load_json(run_dir / "run.json")

        self.assertEqual(constructor_calls, 1)
        self.assertEqual(researcher.calls, len(DOMAIN_NAMES))
        self.assertEqual(synthesis.calls, 1)
        self.assertEqual(FakeGraph.order, [*DOMAIN_NAMES, "property-synthesis"])
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["execution"]["domains"][failed]["status"], "failed")

    async def test_resume_skips_every_completed_model_response(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            FakeGraph.order = []
            researcher, synthesis, constructor_calls = await self._run(run_dir)

        self.assertEqual(FakeGraph.order, [])
        self.assertEqual(constructor_calls, 1)
        self.assertEqual(researcher.calls, 0)
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
            researcher, synthesis, _ = await self._run(run_dir, retry_failed=True)
            after_run = load_json(run_dir / "run.json")
            after = after_run["execution"]["domains"][failed]
            final = after_run["execution"]["final"]

        self.assertEqual(after["attempt"], 2)
        self.assertEqual(after["thread_id"], old_thread)
        self.assertEqual(researcher.inputs, [None])
        self.assertEqual(researcher.sessions, [f"{old_thread}:attempt-2"])
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

    async def test_old_schema_is_rejected_before_graph_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["schema_version"] = 7
            write_json(run_dir / "run.json", run)
            with self.assertRaisesRegex(ValueError, "fresh Layer 3"):
                await run_research(run_dir)
            self.assertEqual(load_json(run_dir / "run.json"), run)


if __name__ == "__main__":
    unittest.main()
