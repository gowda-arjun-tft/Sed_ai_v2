from __future__ import annotations

import asyncio
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer2.fs import load_json, read_text, slug, write_json
from ML.deep_research.layer3.contracts import DomainQuestions, ResearchOutcome, ReviewOutcome
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.research_tools import _append_fragment
from ML.deep_research.layer3.runner import _questions, _run_stage, run_research
from ML.deep_research.layer3.settings import DOMAIN_NAMES, SCHEMA_VERSION
from tests.common import create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(
        create_complete_run(root), root / "l3", public_input_confirmed=True
    )


@asynccontextmanager
async def _saver(_run_dir):
    yield object()


class FakeGraph:
    active = 0
    maximum = 0
    review_calls = 0
    questions: tuple[str, ...] = ()
    failing_actor = ""

    def __init__(self, actor: str, run_dir: Path):
        self.actor = actor
        self.run_dir = run_dir

    async def aget_state(self, _config):
        return SimpleNamespace(values={}, next=())

    async def ainvoke(self, value, **kwargs):
        if self.actor in DOMAIN_NAMES:
            context = kwargs["context"]
            content = value["messages"][0]["content"]
            phase = "clarification" if "clarification-1" in content else "initial"
            type(self).active += 1
            type(self).maximum = max(type(self).maximum, type(self).active)
            _append_fragment(
                context,
                self.actor,
                phase,
                f"{self.actor} {phase}\n",
            )
            await asyncio.sleep(0.01)
            type(self).active -= 1
            if self.actor == type(self).failing_actor:
                raise RuntimeError("fixture failure")
            return {
                "structured_response": {
                    "status": "answered",
                    "unknowns": [],
                    "reason": "",
                }
            }
        if self.actor == "review":
            type(self).review_calls += 1
            return {
                "structured_response": {
                    "review_markdown": "# Review\n\nReview complete.\n",
                    "questions": [
                        {"domain": name, "questions": [f"Clarify {name}?"]}
                        for name in type(self).questions
                    ],
                }
            }
        return {
            "messages": [AIMessage(content="# Final\n\nAnswer.\n")]
        }


class ProgressiveRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeGraph.active = 0
        FakeGraph.maximum = 0
        FakeGraph.review_calls = 0
        FakeGraph.questions = ()
        FakeGraph.failing_actor = ""

    async def _run(self, run_dir: Path, *, retry_failed: bool = False) -> None:
        with (
            patch("ML.deep_research.layer3.runner.checkpoint_saver", _saver),
            patch("ML.deep_research.layer3.runner.from_run", return_value=object()),
            patch(
                "ML.deep_research.layer3.runner.create_domain_harness",
                side_effect=lambda root, name, _saver: FakeGraph(name, root),
            ),
            patch(
                "ML.deep_research.layer3.runner.create_reviewer_harness",
                side_effect=lambda root, _saver: FakeGraph("review", root),
            ),
            patch(
                "ML.deep_research.layer3.runner.create_synthesis_harness",
                side_effect=lambda root, _saver: FakeGraph("synthesis", root),
            ),
        ):
            await run_research(run_dir, retry_failed=retry_failed)

    async def test_eight_domains_publish_concurrently_before_one_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            run = load_json(run_dir / "run.json")
            reports = [
                path for path in (run_dir / "domains").glob("*.md")
                if not path.name.endswith(".partial.md")
            ]

        self.assertEqual(FakeGraph.maximum, len(DOMAIN_NAMES))
        self.assertEqual(FakeGraph.review_calls, 1)
        self.assertEqual(run["status"], "complete")
        self.assertEqual(len(reports), len(DOMAIN_NAMES))
        self.assertIsNone(run["execution"]["clarification"])

    async def test_one_review_can_target_multiple_domains_in_one_batch(self):
        FakeGraph.questions = DOMAIN_NAMES[:2]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            run = load_json(run_dir / "run.json")
            reports = {
                name: read_text(run_dir / "domains" / f"{slug(name)}.md")
                for name in DOMAIN_NAMES
            }

        clarification = run["execution"]["clarification"]
        self.assertEqual(FakeGraph.review_calls, 1)
        self.assertEqual(set(clarification["domains"]), set(DOMAIN_NAMES[:2]))
        self.assertTrue(
            all(record["status"] == "complete" for record in clarification["domains"].values())
        )
        for name in DOMAIN_NAMES[:2]:
            self.assertEqual(
                reports[name],
                f"{name} initial\n\n## Clarification\n\n{name} clarification\n",
            )
        self.assertEqual(reports[DOMAIN_NAMES[2]], f"{DOMAIN_NAMES[2]} initial\n")

    async def test_duplicate_question_groups_merge_without_rejecting_the_review(self):
        domain = DOMAIN_NAMES[0]
        outcome = ReviewOutcome(
            review_markdown="# Review",
            questions=[
                DomainQuestions(domain=domain, questions=["First?"]),
                DomainQuestions(domain=domain, questions=["Second?"]),
            ],
        )
        self.assertEqual(_questions(outcome), {domain: ["First?", "Second?"]})

    async def test_failure_keeps_partial_and_published_peer_reports(self):
        FakeGraph.failing_actor = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            run = load_json(run_dir / "run.json")
            failed_partial = run_dir / "domains" / f"{slug(DOMAIN_NAMES[0])}.partial.md"
            failed_final = run_dir / "domains" / f"{slug(DOMAIN_NAMES[0])}.md"
            peer_finals = [
                run_dir / "domains" / f"{slug(name)}.md" for name in DOMAIN_NAMES[1:]
            ]

            self.assertTrue(failed_partial.is_file())
            self.assertFalse(failed_final.exists())
            self.assertTrue(all(path.is_file() for path in peer_finals))
            self.assertFalse((run_dir / "review" / "final_review.md").exists())
        self.assertEqual(run["status"], "incomplete")

    async def test_failed_retry_uses_only_new_attempt_fragments(self):
        FakeGraph.failing_actor = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            await self._run(run_dir)
            record = load_json(run_dir / "run.json")["execution"]["domains"][DOMAIN_NAMES[0]]
            old_thread = record["thread_id"]
            FakeGraph.failing_actor = ""
            await self._run(run_dir, retry_failed=True)
            run = load_json(run_dir / "run.json")
            record = run["execution"]["domains"][DOMAIN_NAMES[0]]
            report = read_text(run_dir / "domains" / f"{slug(DOMAIN_NAMES[0])}.md")

        self.assertEqual(record["attempt"], 2)
        self.assertNotEqual(record["thread_id"], old_thread)
        self.assertEqual(report, f"{DOMAIN_NAMES[0]} initial\n")

    async def test_stage_has_no_whole_invocation_asyncio_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            record = run["execution"]["domains"][DOMAIN_NAMES[0]]

            class Graph:
                async def aget_state(self, _config):
                    return SimpleNamespace(values={}, next=())

                async def ainvoke(self, *_args, **_kwargs):
                    return {
                        "structured_response": {
                            "status": "answered",
                            "unknowns": [],
                            "reason": "",
                        }
                    }

            with patch("asyncio.timeout", side_effect=AssertionError("unexpected timeout")):
                result = await _run_stage(
                    Graph(), run_dir, run, record, object(), {}, ResearchOutcome,
                    asyncio.Lock(), retry_failed=False,
                )

        self.assertIsNotNone(result)
        self.assertEqual(record["status"], "staged")

    async def test_old_schema_is_rejected_before_any_graph_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["schema_version"] = SCHEMA_VERSION - 1
            write_json(run_dir / "run.json", run)
            with self.assertRaisesRegex(ValueError, "fresh Layer 3"):
                await run_research(run_dir)


if __name__ == "__main__":
    unittest.main()
