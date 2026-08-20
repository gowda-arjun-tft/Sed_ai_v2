from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ML.deep_research.layer2.fs import load_json, now_iso, sha256, slug
from ML.deep_research.layer2.agent import create_mission_agent
from ML.deep_research.layer3.contracts import Document
from ML.deep_research.layer3.llm import create_mission_supervisor
from ML.deep_research.layer3.mission import load_inputs, mission_thread_id
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.pipeline.run_checks import run_checks
from ML.deep_research.layer3.research_tools import make_research_tools
from ML.deep_research.layer3.runner import _run_one, commit_outputs
from ML.deep_research.layer3.settings import AGENT_NAMES, LENSES
from ML.deep_research.layer3.sources import SourceStore, load_jsonl

from tests.common import create_complete_l3_run, create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(
        create_complete_run(root),
        root / "l3-runs",
        public_input_confirmed=True,
    )


class Layer3HarnessTests(unittest.TestCase):
    def test_create_run_snapshots_prompts_and_stable_mission_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            prompt_root = run_dir / "inputs" / "prompts"

            self.assertEqual(run["schema_version"], 2)
            self.assertEqual(run["harness"], "mission_supervisor")
            self.assertEqual(run["provider"], "online")
            self.assertTrue(run["public_input_confirmed"])
            self.assertEqual(set(run["missions"]), {slug(name) for name in AGENT_NAMES})
            for name in AGENT_NAMES:
                record = run["missions"][slug(name)]
                self.assertEqual(record["status"], "pending")
                self.assertEqual(
                    record["thread_id"],
                    mission_thread_id(run["run_id"], name, 1),
                )

            skill = run["skill"]
            self.assertEqual(sha256(run_dir / skill["path"]), skill["sha256"])
            actual = {
                path.relative_to(prompt_root).as_posix(): sha256(path)
                for path in prompt_root.rglob("*.md")
                if path.name != "SKILL.md"
            }
            self.assertEqual(actual, run["prompt_hashes"])
            self.assertFalse((run_dir / "questions").exists())
            self.assertFalse((run_dir / "register.csv").exists())

    def test_graph_has_only_supervisor_tools_and_fixed_subagents(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                graph = create_mission_supervisor(run_dir)

            tools = graph.nodes["tools"].bound._tools_by_name
            self.assertEqual(set(tools), {"task", "ls", "read_file", "write_file"})
            description = tools["task"].description
            for lens in LENSES:
                self.assertIn(f"- {lens}:", description)
            self.assertIn("- additional-researcher:", description)
            self.assertNotIn("- general-purpose:", description)
            subgraphs = next(
                cell.cell_contents
                for cell in tools["task"].coroutine.__closure__
                if isinstance(cell.cell_contents, dict)
            )
            expected = {"ls", "read_file", "write_file", "search_web", "read_source", "cite"}
            for name, subgraph in subgraphs.items():
                self.assertEqual(
                    set(subgraph.nodes["tools"].bound._tools_by_name), expected, name
                )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                layer2 = create_mission_agent(
                    Path(load_json(run_dir / "run.json")["source_l2"]["path"])
                )
            layer2_task = layer2.nodes["tools"].bound.tools_by_name["task"]
            self.assertIn("- general-purpose:", layer2_task.description)

    def test_commit_preserves_first_report_prefix_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            agent = AGENT_NAMES[0]
            first = "First-round bytes stay exactly here.\n"
            files = {
                f"/lenses/{lens}/first.md": {"content": first}
                for lens in LENSES
            }

            with self.assertRaisesRegex(ValueError, "answer"):
                commit_outputs(run_dir, agent, {"files": files})
            self.assertFalse((run_dir / "lenses" / slug(agent)).exists())

            files["/lenses/practitioner/followup.md"] = {
                "content": "One direct follow-up answer.\n"
            }
            files["/lenses/additional/report.md"] = {
                "content": "One optional perspective.\n"
            }
            files["/answer.md"] = {"content": "Final answer.\n"}
            state = {"files": files}
            commit_outputs(run_dir, agent, state)

            lens_dir = run_dir / "lenses" / slug(agent)
            practitioner = (lens_dir / "practitioner.md").read_bytes()
            self.assertTrue(practitioner.startswith(first.encode("utf-8")))
            self.assertIn(b"## Follow-up\n\nOne direct follow-up answer.", practitioner)
            self.assertEqual(
                (lens_dir / "additional.md").read_text(encoding="utf-8"),
                "One optional perspective.\n",
            )
            commit_outputs(run_dir, agent, state)
            self.assertEqual((lens_dir / "practitioner.md").read_bytes(), practitioner)
            del files["/lenses/additional/report.md"]
            commit_outputs(run_dir, agent, state)
            self.assertFalse((lens_dir / "additional.md").exists())


class Layer3EvidenceTests(unittest.TestCase):
    def test_three_tools_and_exact_idempotent_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            tools = make_research_tools("skeptic")
            self.assertEqual({tool.name for tool in tools}, {"search_web", "read_source", "cite"})

            store = SourceStore(run_dir)
            record = store.store(
                Document(
                    url="https://example.com/report",
                    content_type="text/html; charset=utf-8",
                    body=b"<p>Verified public fact.</p>",
                    fetched_at=now_iso(),
                )
            )
            citation = dict(
                source_id=record["source_sha256"],
                quote="Verified public fact.",
                tier=1,
                agent=AGENT_NAMES[0],
                lens="skeptic",
                session_id="session-1",
            )
            marker = store.record_citation(**citation)
            self.assertEqual(store.record_citation(**citation), marker)
            self.assertRegex(marker, r"^\[citation:[0-9a-f]{64}\]$")
            self.assertEqual(len(store.citations()), 1)

            with self.assertRaisesRegex(ValueError, "does not occur"):
                store.record_citation(**{**citation, "quote": "Invented words."})
            binary = store.store(
                Document(
                    url="https://example.com/file.pdf",
                    content_type="application/pdf",
                    body=b"%PDF-1.4 test",
                    fetched_at=now_iso(),
                )
            )
            with self.assertRaisesRegex(ValueError, "cannot be cited"):
                store.record_citation(
                    **{**citation, "source_id": binary["source_sha256"]}
                )

            query = dict(
                session_id="session-1",
                agent=AGENT_NAMES[0],
                lens="skeptic",
                query="public building standard",
            )
            store.record_query(**query)
            store.record_query(**query)
            self.assertEqual(len(load_jsonl(run_dir / "sources" / "queries.jsonl")), 1)


class Layer3ChecksTests(unittest.TestCase):
    def test_fabricated_complete_run_passes_every_derived_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            checks = run_checks(run_dir)
            recorded = load_json(run_dir / "run.json")["checks"]

            self.assertTrue(all(ok for _, _, ok, _ in checks))
            self.assertEqual(recorded["run"], len(checks))
            self.assertEqual(recorded["passed"], len(checks))
            self.assertEqual(recorded["failed"], 0)
            self.assertEqual(len(list((run_dir / "lenses").glob("*/*.md"))), 70)
            self.assertEqual(len(list((run_dir / "research").glob("*.md"))), 14)

    def test_unknown_answer_citation_fails_marker_and_answer_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            answer = run_dir / "research" / f"{slug(AGENT_NAMES[0])}.md"
            answer.write_text(
                f"Unsupported answer [citation:{'0' * 64}]\n",
                encoding="utf-8",
            )
            failures = [label for _, label, ok, _ in run_checks(run_dir) if not ok]

            self.assertTrue(any("marker" in label.lower() for label in failures))
            self.assertTrue(any("answered mission" in label.lower() for label in failures))


class Layer3ResumeTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _state() -> dict:
        files = {
            f"/lenses/{lens}/first.md": {"content": f"{lens} report\n"}
            for lens in LENSES
        }
        files["/answer.md"] = {"content": "Final answer\n"}
        return {
            "files": files,
            "structured_response": {"status": "cannot_be_answered", "reason": "No evidence."},
        }

    async def test_completed_checkpoint_commits_without_another_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            mission, definition = load_inputs(run_dir)[0]
            run["missions"][slug(mission["agent"])]["status"] = "running"

            class Graph:
                async def aget_state(self, _):
                    return SimpleNamespace(values=Layer3ResumeTests._state(), next=())

                async def ainvoke(self, *_args, **_kwargs):
                    raise AssertionError("completed checkpoint must not be invoked")

            await _run_one(
                Graph(), run_dir, run, mission, definition, object(), retry_failed=False
            )
            self.assertEqual(
                load_json(run_dir / "run.json")["missions"][slug(mission["agent"])]["status"],
                "complete",
            )

    async def test_retry_failed_uses_a_clean_attempt_thread(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            mission, definition = load_inputs(run_dir)[0]
            record = run["missions"][slug(mission["agent"])]
            record["status"] = "failed"
            seen = {}

            class Graph:
                async def aget_state(self, config):
                    seen["thread"] = config["configurable"]["thread_id"]
                    return SimpleNamespace(values={}, next=())

                async def ainvoke(self, value, **_kwargs):
                    self.value = value
                    return Layer3ResumeTests._state()

            graph = Graph()
            await _run_one(
                graph, run_dir, run, mission, definition, object(), retry_failed=True
            )
            self.assertEqual(record["attempt"], 2)
            self.assertEqual(
                seen["thread"], mission_thread_id(run["run_id"], mission["agent"], 2)
            )
            self.assertIsNotNone(graph.value)


if __name__ == "__main__":
    unittest.main()
