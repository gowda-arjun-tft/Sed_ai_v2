from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer3.contracts import RESEARCHER_NAME, ResearchContext, SearchHit
from ML.deep_research.layer3.mission import load_research_input
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.pipeline.run_checks import run_checks
from ML.deep_research.layer3.research_tools import _search, make_research_tools
from ML.deep_research.layer3.settings import DOMAIN_NAMES, HARNESS_NAME, SCHEMA_VERSION
from ML.deep_research.layer3.sources import SourceStore
from tests.common import create_complete_l3_run, create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(create_complete_run(root), root / "l3-runs", public_input_confirmed=True)


class Layer3SchemaTests(unittest.TestCase):
    def test_schema_eight_has_only_domain_researchers_and_synthesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")

        self.assertEqual(run["schema_version"], SCHEMA_VERSION)
        self.assertEqual(run["harness"], HARNESS_NAME)
        self.assertEqual(run["skill"]["path"], "inputs/prompts/SKILL.md")
        self.assertEqual(set(run["prompt_hashes"]), {"synthesis.md"})
        self.assertEqual(
            run["context_management"]["applies_to"],
            "domain_researcher",
        )
        self.assertEqual(set(run["execution"]), {"domains", "final"})
        self.assertEqual(list(run["execution"]["domains"]), list(DOMAIN_NAMES))
        self.assertTrue(
            all(item["stage"] == "researcher" for item in run["execution"]["domains"].values())
        )
        self.assertEqual(run["limits"]["transient_retries"], 3)
        self.assertNotIn("output_tokens_per_model_call", run["limits"])

    def test_research_input_remains_eight_isolated_assignments(self):
        with tempfile.TemporaryDirectory() as temporary:
            assignments = load_research_input(_new_l3(Path(temporary)))
        self.assertEqual([item["name"] for item in assignments], list(DOMAIN_NAMES))
        self.assertTrue(
            all(item["mission"].startswith(f"# {item['name']}") for item in assignments)
        )


class Layer3EvidenceTests(unittest.TestCase):
    def test_researcher_tools_are_only_search_and_read(self):
        self.assertEqual(
            {tool.name for tool in make_research_tools(RESEARCHER_NAME)},
            {"search_web", "read_source"},
        )
        self.assertFalse(hasattr(SourceStore(Path("unused")), "record_citation"))

    def test_identical_queries_share_cache_across_callers(self):
        class Retriever:
            calls = 0

            async def search(self, _query, **_kwargs):
                self.calls += 1
                return [SearchHit("hit", "https://example.com", "Example")]

        with tempfile.TemporaryDirectory() as temporary:
            context = ResearchContext(Path(temporary), DOMAIN_NAMES[0], "thread", Retriever())

            async def exercise():
                return await asyncio.gather(
                    _search(context, "same query", "first-caller"),
                    _search(context, "same query", "second-caller"),
                )

            first, second = asyncio.run(exercise())
            calls = context.retriever.calls

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)


class Layer3ChecksTests(unittest.TestCase):
    def test_fabricated_schema_eight_run_has_true_operational_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            checks = run_checks(run_dir)
        self.assertTrue(all(ok for _, _, ok, _ in checks))

    def test_optional_checks_do_not_change_run_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["status"] = "complete"
            write_json(run_dir / "run.json", run)
            run_checks(run_dir)
            status = load_json(run_dir / "run.json")["status"]
        self.assertEqual(status, "complete")


if __name__ == "__main__":
    unittest.main()
