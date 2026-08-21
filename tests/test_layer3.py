from __future__ import annotations

import asyncio

import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ML.deep_research.layer2.agent import create_chunk_agent
from ML.deep_research.layer2.fs import atomic_write_text, load_json, now_iso, sha256, slug
from ML.deep_research.layer3.contracts import (
    Document,
    ResearchContext,
    ResearchOutcome,
    SearchHit,
)
from ML.deep_research.layer3.llm import (
    create_domain_harness,
    create_reviewer_harness,
    create_synthesis_harness,
)
from ML.deep_research.layer3.mission import load_research_input, stage_thread_id
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.pipeline.run_checks import run_checks
from ML.deep_research.layer3.research_tools import _search, make_research_tools
from ML.deep_research.layer3.runner import _run_stage, commit_outputs, run_research
from ML.deep_research.layer3.settings import (
    DOMAIN_NAMES,
    HARNESS_NAME,
    MODEL_INPUT_TOKEN_LIMIT,
    SCHEMA_VERSION,
)
from ML.deep_research.layer3.sources import SourceStore, load_jsonl
from tests.common import create_complete_l3_run, create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(create_complete_run(root), root / "l3-runs", public_input_confirmed=True)


def _tools(graph) -> set[str]:
    return set(graph.nodes["tools"].bound._tools_by_name)


class Layer3HarnessTests(unittest.TestCase):
    def test_schema_five_run_has_progressive_stage_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            prompt_root = run_dir / "inputs" / "prompts"
            skill_hash = sha256(run_dir / run["skill"]["path"])
            evidence_exists = (run_dir / "evidence").exists()
            scout_prompt_exists = (prompt_root / "source_scout.md").exists()

        self.assertEqual(run["schema_version"], SCHEMA_VERSION)
        self.assertEqual(run["harness"], HARNESS_NAME)
        self.assertEqual(set(run["execution"]["domains"]), set(DOMAIN_NAMES))
        self.assertEqual(run["execution"]["review"]["stage"], "review")
        self.assertIsNone(run["execution"]["clarification"])
        self.assertEqual(run["model_context_window_tokens"], MODEL_INPUT_TOKEN_LIMIT)
        self.assertNotIn("input_tokens_per_model_call", run["limits"])
        self.assertNotIn("output_tokens_per_model_call", run["limits"])
        self.assertNotIn("agent_model_calls", run["limits"])
        self.assertNotIn("agent_timeout_seconds", run["limits"])
        self.assertNotIn("clarification_batches", run["limits"])
        self.assertFalse(evidence_exists)
        self.assertFalse(scout_prompt_exists)
        self.assertEqual(skill_hash, run["skill"]["sha256"])

    def test_research_input_contains_only_eight_isolated_assignments(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = load_research_input(_new_l3(Path(temporary)))
        self.assertEqual([item["name"] for item in payload], list(DOMAIN_NAMES))
        self.assertTrue(all(item["mission"]["agent"] == item["name"] for item in payload))

    def test_direct_graphs_have_only_their_required_tools_and_no_call_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                domain = create_domain_harness(run_dir, DOMAIN_NAMES[0])
                reviewer = create_reviewer_harness(run_dir)
                synthesis = create_synthesis_harness(run_dir)
                layer2, _ = create_chunk_agent(
                    Path(load_json(run_dir / "run.json")["source_l2"]["path"])
                )

        self.assertEqual(
            _tools(domain),
            {"read_file", "search_web", "read_source", "cite", "append_report"},
        )
        self.assertEqual(_tools(reviewer), {"read_file"})
        self.assertEqual(_tools(synthesis), {"read_file"})
        for graph in (domain, reviewer, synthesis):
            self.assertNotIn("task", _tools(graph))
            self.assertFalse(any("ModelCallLimitMiddleware" in name for name in graph.nodes))

        self.assertNotIn("tools", layer2.nodes)

    def test_atomic_commit_requires_all_outputs(self):
        reports = {name: f"{name} report" for name in DOMAIN_NAMES}
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            with self.assertRaisesRegex(ValueError, "eight"):
                commit_outputs(run_dir, {DOMAIN_NAMES[0]: "one"}, "review", "answer")
            self.assertFalse(any((run_dir / "domains").glob("*.md")))
            with self.assertRaisesRegex(ValueError, "do not match"):
                commit_outputs(run_dir, reports, "review", "answer")
            for name, report in reports.items():
                atomic_write_text(run_dir / "domains" / f"{slug(name)}.md", report)
            commit_outputs(run_dir, reports, "review", "answer")
            self.assertEqual(len(list((run_dir / "domains").glob("*.md"))), 8)
            self.assertEqual(
                (run_dir / "research" / "final.md").read_text(encoding="utf-8"),
                "answer",
            )


class Layer3EvidenceTests(unittest.TestCase):
    def test_four_tools_and_exact_idempotent_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            domain = DOMAIN_NAMES[0]
            self.assertEqual(
                {tool.name for tool in make_research_tools(domain)},
                {"search_web", "read_source", "cite", "append_report"},
            )
            store = SourceStore(run_dir)
            source = store.store(
                Document(
                    url="https://example.com/report",
                    content_type="text/html; charset=utf-8",
                    body=b"<p>Verified public fact.</p>",
                    fetched_at=now_iso(),
                )
            )
            citation = dict(
                source_id=source["source_sha256"], quote="Verified public fact.", tier=1,
                agent=domain, lens=domain, session_id="session-1",
            )
            marker = store.record_citation(**citation)
            self.assertEqual(store.record_citation(**citation), marker)
            with self.assertRaisesRegex(ValueError, "does not occur"):
                store.record_citation(**{**citation, "quote": "Invented words."})
            query = dict(session_id="s", agent=domain, lens=domain, query="same query")
            store.record_query(**query)
            store.record_query(**query)
            self.assertEqual(len(load_jsonl(run_dir / "sources" / "queries.jsonl")), 1)
            self.assertEqual(store.cache_path("same query"), store.cache_path("same   query"))

    def test_identical_queries_share_one_result_cache_across_domains(self):
        class Retriever:
            calls = 0

            async def search(self, _query, **_kwargs):
                self.calls += 1
                return [SearchHit("hit", "https://example.com", "Example")]

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            retriever = Retriever()

            async def exercise():
                first = ResearchContext(run_dir, DOMAIN_NAMES[0], "a", retriever)
                second = ResearchContext(run_dir, DOMAIN_NAMES[1], "b", retriever)
                return await _search(first, "same query", DOMAIN_NAMES[0]), await _search(
                    second, "same query", DOMAIN_NAMES[1]
                )

            first, second = asyncio.run(exercise())

        self.assertEqual(first, second)
        self.assertEqual(retriever.calls, 1)


class Layer3ChecksTests(unittest.TestCase):
    def test_fabricated_schema_five_run_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            checks = run_checks(run_dir)
        self.assertTrue(all(ok for _, _, ok, _ in checks))

    def test_unknown_final_citation_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            (run_dir / "research" / "final.md").write_text(
                f"Unsupported [citation:{'0' * 64}]", encoding="utf-8"
            )
            failures = [label for _, label, ok, _ in run_checks(run_dir) if not ok]
        self.assertTrue(any("marker" in label.lower() for label in failures))


class StageRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_checkpoint_is_reused_and_failed_retry_gets_new_thread(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            record = run["execution"]["domains"][DOMAIN_NAMES[0]]
            result = {
                "files": {"/report.md": {"content": "done"}},
                "structured_response": {"status": "answered", "reason": ""},
            }

            class Graph:
                calls = 0

                async def aget_state(self, _config):
                    return SimpleNamespace(values=result, next=())

                async def ainvoke(self, *_args, **_kwargs):
                    self.calls += 1
                    return result

            graph = Graph()
            await _run_stage(
                graph, run_dir, run, record, object(), {}, ResearchOutcome,
                __import__("asyncio").Lock(), retry_failed=False,
            )
            self.assertEqual(graph.calls, 0)
            old_thread = record["thread_id"]
            record["status"] = "failed"
            await _run_stage(
                graph, run_dir, run, record, object(), {}, ResearchOutcome,
                __import__("asyncio").Lock(), retry_failed=True,
            )
        self.assertEqual(record["attempt"], 2)
        self.assertNotEqual(record["thread_id"], old_thread)

    async def test_older_schema_resume_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            old_schema = SCHEMA_VERSION - 1
            run["schema_version"] = old_schema
            from ML.deep_research.layer2.fs import write_json

            write_json(run_dir / "run.json", run)
            from ML.deep_research.layer3.runner import run_research

            with self.assertRaisesRegex(ValueError, f"schema {old_schema}.*fresh Layer 3"):
                await run_research(run_dir)


if __name__ == "__main__":
    unittest.main()
