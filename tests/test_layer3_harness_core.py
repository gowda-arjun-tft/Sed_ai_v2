from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer2.fs import slug
from ML.deep_research.layer3.contracts import ResearchContext, SearchHit
from ML.deep_research.layer3.llm import (
    build_layer3_model,
    create_domain_harness,
    create_reviewer_harness,
    create_synthesis_harness,
    final_text,
)
from ML.deep_research.layer3.providers.openai_search import OpenAISearchRetriever
from ML.deep_research.layer3.research_tools import (
    make_research_tools,
    partial_report_path,
    read_partial_report,
)
from ML.deep_research.layer3.settings import DOMAIN_NAMES
from ML.deep_research.layer3.sources import load_jsonl


def _graph_model(graph):
    closure = graph.nodes["model"].bound.func.__closure__ or ()
    return next(
        cell.cell_contents
        for cell in closure
        if hasattr(cell.cell_contents, "reasoning_effort")
    )


class Layer3ModelAndSurfaceTests(unittest.TestCase):
    def test_synthesis_reads_plain_markdown_without_a_schema_wrapper(self):
        self.assertEqual(
            final_text({"messages": [AIMessage(content="# Decision\n\nProceed.")]}),
            "# Decision\n\nProceed.",
        )

    def test_every_harness_model_is_low_with_request_resilience(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
            model = build_layer3_model()
        self.assertEqual(model.reasoning_effort, "low")
        self.assertEqual(model.request_timeout, 600.0)
        self.assertEqual(model.max_retries, 2)

    def test_direct_harnesses_expose_only_their_required_tools(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}),
            patch(
                "ML.deep_research.layer3.llm.domain_system_prompt",
                return_value="domain",
            ),
            patch(
                "ML.deep_research.layer3.llm.reviewer_system_prompt",
                return_value="reviewer",
            ),
            patch(
                "ML.deep_research.layer3.llm.synthesis_system_prompt",
                return_value="synthesis",
            ),
        ):
            domain = create_domain_harness(Path("unused"), DOMAIN_NAMES[0])
            reviewer = create_reviewer_harness(Path("unused"))
            synthesis = create_synthesis_harness(Path("unused"))

        self.assertEqual(
            set(domain.nodes["tools"].bound.tools_by_name),
            {"read_file", "search_web", "read_source", "cite", "append_report"},
        )
        for graph in (reviewer, synthesis):
            self.assertEqual(set(graph.nodes["tools"].bound.tools_by_name), {"read_file"})
        for graph in (domain, reviewer, synthesis):
            self.assertFalse(
                any("ModelCallLimitMiddleware" in name for name in graph.nodes)
            )
            self.assertEqual(_graph_model(graph).reasoning_effort, "low")


class ProgressiveReportTests(unittest.TestCase):
    def test_append_is_scoped_durable_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            domain = DOMAIN_NAMES[0]
            context = ResearchContext(run_dir, domain, "attempt-1", None)
            runtime = SimpleNamespace(context=context)
            append = next(
                tool for tool in make_research_tools(domain) if tool.name == "append_report"
            )

            first = append.func(
                fragment_id="authority__one",
                markdown="# First\n",
                runtime=runtime,
            )
            replay = append.func(
                fragment_id="authority__one",
                markdown="# First\n",
                runtime=runtime,
            )
            conflict = append.func(
                fragment_id="authority__one",
                markdown="# Changed\n",
                runtime=runtime,
            )

            expected = run_dir / "domains" / f"{slug(domain)}.partial.md"
            self.assertEqual(partial_report_path(run_dir, domain), expected)
            self.assertEqual(read_partial_report(run_dir, domain), "# First\n")
            self.assertEqual(len(load_jsonl(run_dir / "usage.jsonl")), 1)

            second_runtime = SimpleNamespace(
                context=ResearchContext(run_dir, domain, "attempt-2", None)
            )
            second = append.func(
                fragment_id="authority__one",
                markdown="# Retry\n",
                runtime=second_runtime,
            )
            self.assertEqual(read_partial_report(run_dir, domain), "# Retry\n")
            self.assertEqual(
                read_partial_report(run_dir, domain, "attempt-1"),
                "# First\n",
            )
            self.assertEqual(
                read_partial_report(run_dir, domain, "attempt-2"),
                "# Retry\n",
            )
            self.assertEqual(len(load_jsonl(run_dir / "usage.jsonl")), 2)

        self.assertEqual(first, "Report fragment saved.")
        self.assertEqual(replay, "Report fragment already saved.")
        self.assertIn("different content", conflict)
        self.assertEqual(second, "Report fragment saved.")


class SearchContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_client_keeps_request_timeout_and_retries(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}),
        ):
            retriever = OpenAISearchRetriever(Path(temporary))
        self.assertEqual(retriever.client.timeout, 600)
        self.assertEqual(retriever.client.max_retries, 2)

    async def test_search_returns_publisher_and_snippet_and_uses_low(self):
        seen = {}

        class Responses:
            async def create(self, **kwargs):
                seen.update(kwargs)
                return SimpleNamespace(
                    usage=None,
                    model_dump=lambda **_: {
                        "output": [
                            {
                                "content": [
                                    {
                                        "text": "Useful result summary.",
                                        "annotations": [
                                            {
                                                "type": "url_citation",
                                                "url": "https://authority.example/record",
                                                "title": "Official record",
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    },
                )

        retriever = object.__new__(OpenAISearchRetriever)
        retriever.run_dir = Path("unused")
        retriever.client = SimpleNamespace(responses=Responses())
        with patch(
            "ML.deep_research.layer3.providers.openai_search.record_search_usage"
        ):
            hits = await retriever.search("official record", actor=DOMAIN_NAMES[0])

        self.assertEqual(seen["reasoning"], {"effort": "low"})
        self.assertEqual(
            seen["tools"], [{"type": "web_search", "search_context_size": "low"}]
        )
        self.assertFalse(seen["store"])
        self.assertEqual(hits[0].publisher, "authority.example")
        self.assertEqual(hits[0].snippet, "Useful result summary.")

    async def test_agent_receives_every_search_hit_field(self):
        class Retriever:
            async def search(self, *_args, **_kwargs):
                return [
                    SearchHit(
                        hit_id="hit-1",
                        title="Registry entry",
                        url="https://registry.example/item",
                        publisher="Registry Authority",
                        snippet="The relevant retained snippet.",
                    )
                ]

        with tempfile.TemporaryDirectory() as temporary:
            context = ResearchContext(
                Path(temporary), DOMAIN_NAMES[0], "session", Retriever()
            )
            runtime = SimpleNamespace(context=context)
            search = next(
                tool for tool in make_research_tools(DOMAIN_NAMES[0])
                if tool.name == "search_web"
            )
            result = await search.coroutine(
                query="registry entry",
                runtime=runtime,
            )

        for value in (
            "hit-1",
            "Registry entry",
            "https://registry.example/item",
            "Registry Authority",
            "The relevant retained snippet.",
        ):
            self.assertIn(value, result)


if __name__ == "__main__":
    unittest.main()
