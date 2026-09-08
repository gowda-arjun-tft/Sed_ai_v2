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
from ML.deep_research.layer3.settings import DOMAIN_NAMES
from ML.deep_research.layer4.create_run import create_run
from ML.deep_research.layer4.runner import run_external_research
from ML.deep_research.layer4.settings import MISSING_CANDIDATE_REPORT, SYNTHESIS_NAME
from tests.common import create_complete_l3_run


def _new_l4(root: Path) -> Path:
    return create_run(create_complete_l3_run(root), public_input_confirmed=True)


class FakeGraph:
    order: list[tuple[str, str]] = []
    checkpointed: set[str] = set()
    active = 0
    maximum = 0

    def __init__(
        self,
        kind: str,
        *,
        failing: tuple[str, str] | None = None,
        special: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self.kind = kind
        self.failing = failing
        self.special = special or {}
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
        actor = kwargs["context"].agent
        thread_id = kwargs["config"]["configurable"]["thread_id"]
        key = (actor, self.kind)
        self.calls += 1
        self.actors.append(actor)
        self.inputs.append(value)
        self.thread_ids.append(thread_id)
        self.sessions.append(kwargs["context"].session_id)
        FakeGraph.order.append(key)
        FakeGraph.active += 1
        FakeGraph.maximum = max(FakeGraph.maximum, FakeGraph.active)
        await asyncio.sleep(0)
        FakeGraph.active -= 1
        if key == self.failing:
            FakeGraph.checkpointed.add(thread_id)
            raise RuntimeError("provider failure")
        content = self.special.get(key, f"# {actor} — {self.kind}\n\nModel response.\n")
        return {"messages": [AIMessage(content=content)]}


@asynccontextmanager
async def _saver(_run_dir):
    yield object()


class Layer4RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeGraph.order = []
        FakeGraph.checkpointed = set()
        FakeGraph.active = 0
        FakeGraph.maximum = 0

    async def _run(
        self,
        run_dir: Path,
        *,
        failing: tuple[str, str] | None = None,
        special: dict[tuple[str, str], str] | None = None,
        retry_failed: bool = False,
    ) -> dict[str, FakeGraph]:
        graphs = {
            "internal": FakeGraph("internal", failing=failing, special=special),
            "candidates": FakeGraph("candidates", failing=failing, special=special),
            "research": FakeGraph("research", failing=failing, special=special),
            "synthesis": FakeGraph("synthesis", failing=failing, special=special),
        }
        with (
            patch("ML.deep_research.layer4.runner.checkpoint_saver", _saver),
            patch("ML.deep_research.layer4.runner.from_run", return_value=object()),
            patch(
                "ML.deep_research.layer4.runner.create_internal_harness",
                return_value=graphs["internal"],
            ),
            patch(
                "ML.deep_research.layer4.runner.create_candidate_harness",
                return_value=graphs["candidates"],
            ),
            patch(
                "ML.deep_research.layer4.runner.create_external_researcher_harness",
                return_value=graphs["research"],
            ),
            patch(
                "ML.deep_research.layer4.runner.create_synthesis_harness",
                return_value=graphs["synthesis"],
            ),
        ):
            await run_external_research(run_dir, retry_failed=retry_failed)
        return graphs

    async def test_success_runs_sequentially_and_publishes_twenty_five_responses(self):
        first = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            graphs = await self._run(
                run_dir,
                special={(first, "internal"): ""},
            )
            run = load_json(run_dir / "run.json")
            domain_outputs = list((run_dir / "domains").glob("*/*.md"))
            final_path = run_dir / "research" / "final.md"
            final_exists = final_path.is_file()
            internal_text = read_text(run_dir / "domains" / slug(first) / "internal.md")

        expected = [
            (name, stage)
            for name in DOMAIN_NAMES
            for stage in ("internal", "candidates", "research")
        ] + [(SYNTHESIS_NAME, "synthesis")]
        self.assertEqual(FakeGraph.order, expected)
        self.assertEqual(FakeGraph.maximum, 1)
        self.assertEqual(sum(graph.calls for graph in graphs.values()), 25)
        self.assertEqual(len(domain_outputs), 24)
        self.assertTrue(final_exists)
        self.assertEqual(internal_text, "")
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["execution"]["domains"][first]["internal"]["status"], "complete")

    async def test_failed_internal_stage_does_not_block_research_or_synthesis(self):
        domain = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            graphs = await self._run(run_dir, failing=(domain, "internal"))
            run = load_json(run_dir / "run.json")
            layer3_report = read_text(
                run_dir / "inputs" / "domains" / f"{slug(domain)}.md"
            )
            candidate_input = graphs["candidates"].inputs[
                graphs["candidates"].actors.index(domain)
            ]["messages"][0]["content"]
            research_input = graphs["research"].inputs[
                graphs["research"].actors.index(domain)
            ]["messages"][0]["content"]

        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["execution"]["domains"][domain]["internal"]["status"], "failed")
        self.assertEqual(candidate_input.count(layer3_report), 1)
        self.assertEqual(research_input.count(layer3_report), 1)
        self.assertNotIn("internal_conditions_report", candidate_input)
        self.assertNotIn("internal_conditions_report", research_input)
        self.assertIn((domain, "research"), FakeGraph.order)
        self.assertEqual(FakeGraph.order[-1], (SYNTHESIS_NAME, "synthesis"))

    async def test_internal_recovery_reuses_only_its_own_thread(self):
        domain = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            await self._run(run_dir, failing=(domain, "internal"))
            before = load_json(run_dir / "run.json")
            old = before["execution"]["domains"][domain]
            old_final = before["execution"]["final"]["thread_id"]
            old_threads = {name: value["thread_id"] for name, value in old.items()}
            FakeGraph.order = []
            graphs = await self._run(run_dir, retry_failed=True)
            after = load_json(run_dir / "run.json")
            new = after["execution"]["domains"][domain]

        self.assertEqual(
            FakeGraph.order,
            [(domain, "internal")],
        )
        self.assertIsNone(graphs["internal"].inputs[0])
        self.assertEqual(new["internal"]["thread_id"], old_threads["internal"])
        self.assertEqual(new["internal"]["attempt"], 2)
        self.assertEqual(new["external_candidates"]["thread_id"], old_threads["external_candidates"])
        self.assertEqual(new["external_research"]["thread_id"], old_threads["external_research"])
        self.assertEqual(after["execution"]["final"]["thread_id"], old_final)
        self.assertEqual(
            after["execution"]["domains"][DOMAIN_NAMES[1]]["internal"]["attempt"],
            1,
        )

    async def test_missing_internal_artifact_regenerates_only_internal(self):
        domain = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            await self._run(run_dir)
            before = load_json(run_dir / "run.json")
            old_domain = before["execution"]["domains"][domain]
            old_candidate = old_domain["external_candidates"]["thread_id"]
            old_research = old_domain["external_research"]["thread_id"]
            old_synthesis = before["execution"]["final"]["thread_id"]
            (run_dir / "domains" / slug(domain) / "internal.md").unlink()
            FakeGraph.order = []
            await self._run(run_dir)
            after = load_json(run_dir / "run.json")
            new_domain = after["execution"]["domains"][domain]

        self.assertEqual(
            FakeGraph.order,
            [(domain, "internal")],
        )
        self.assertEqual(new_domain["external_candidates"]["thread_id"], old_candidate)
        self.assertEqual(new_domain["external_research"]["thread_id"], old_research)
        self.assertEqual(after["execution"]["final"]["thread_id"], old_synthesis)

    async def test_candidate_and_research_recovery_restart_only_their_dependents(self):
        domain = DOMAIN_NAMES[0]
        cases = (
            ("candidates", ["candidates", "research", "synthesis"]),
            ("research", ["research", "synthesis"]),
        )
        for failed_kind, expected_kinds in cases:
            with self.subTest(failed_kind=failed_kind), tempfile.TemporaryDirectory() as temporary:
                FakeGraph.order = []
                FakeGraph.checkpointed = set()
                run_dir = _new_l4(Path(temporary))
                first_graphs = await self._run(run_dir, failing=(domain, failed_kind))
                before = load_json(run_dir / "run.json")
                key = "external_candidates" if failed_kind == "candidates" else "external_research"
                failed_thread = before["execution"]["domains"][domain][key]["thread_id"]
                old_research_thread = before["execution"]["domains"][domain][
                    "external_research"
                ]["thread_id"]
                old_final_thread = before["execution"]["final"]["thread_id"]
                FakeGraph.order = []
                graphs = await self._run(run_dir, retry_failed=True)
                after = load_json(run_dir / "run.json")

                self.assertEqual([kind for _, kind in FakeGraph.order], expected_kinds)
                self.assertEqual(after["execution"]["domains"][domain][key]["thread_id"], failed_thread)
                self.assertIsNone(graphs[failed_kind].inputs[0])
                self.assertNotEqual(after["execution"]["final"]["thread_id"], old_final_thread)
                if failed_kind == "candidates":
                    research_input = first_graphs["research"].inputs[
                        first_graphs["research"].actors.index(domain)
                    ]["messages"][0]["content"]
                    layer3_report = read_text(
                        run_dir / "inputs" / "domains" / f"{slug(domain)}.md"
                    )
                    self.assertIn(MISSING_CANDIDATE_REPORT, research_input)
                    self.assertEqual(research_input.count(layer3_report), 1)
                    self.assertNotEqual(
                        after["execution"]["domains"][domain]["external_research"][
                            "thread_id"
                        ],
                        old_research_thread,
                    )

    async def test_candidate_recovery_persists_research_invalidation_before_rerun(self):
        class SimulatedCrash(BaseException):
            pass

        domain = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            await self._run(run_dir, failing=(domain, "candidates"))
            before = load_json(run_dir / "run.json")
            old_research_thread = before["execution"]["domains"][domain][
                "external_research"
            ]["thread_id"]
            from ML.deep_research.layer4 import runner

            original_publish = runner._publish
            calls = 0

            async def crash_before_research(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise SimulatedCrash()
                return await original_publish(*args, **kwargs)

            with patch.object(runner, "_publish", crash_before_research):
                with self.assertRaises(SimulatedCrash):
                    await self._run(run_dir, retry_failed=True)
            recovered = load_json(run_dir / "run.json")["execution"]["domains"][domain]

        self.assertEqual(recovered["external_candidates"]["status"], "complete")
        self.assertEqual(recovered["external_research"]["status"], "pending")
        self.assertNotEqual(
            recovered["external_research"]["thread_id"], old_research_thread
        )

    async def test_failed_synthesis_resumes_its_unchanged_thread(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            await self._run(run_dir, failing=(SYNTHESIS_NAME, "synthesis"))
            before = load_json(run_dir / "run.json")
            old_thread = before["execution"]["final"]["thread_id"]
            self.assertEqual(before["status"], "incomplete")
            FakeGraph.order = []
            graphs = await self._run(run_dir, retry_failed=True)
            after = load_json(run_dir / "run.json")

        self.assertEqual(FakeGraph.order, [(SYNTHESIS_NAME, "synthesis")])
        self.assertEqual(after["execution"]["final"]["thread_id"], old_thread)
        self.assertIsNone(graphs["synthesis"].inputs[0])
        self.assertEqual(after["status"], "complete")

    async def test_incompatible_schema_is_rejected_without_mutating_the_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l4(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["schema_version"] = 1
            write_json(run_dir / "run.json", run)
            with self.assertRaisesRegex(ValueError, "fresh Layer 4"):
                await run_external_research(run_dir)
            self.assertEqual(load_json(run_dir / "run.json"), run)


if __name__ == "__main__":
    unittest.main()
