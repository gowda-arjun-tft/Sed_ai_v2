from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ML.deep_research.layer3.contracts import ResearchContext
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.providers.openai_search import OpenAISearchRetriever
from ML.deep_research.layer3.research_tools import _append_fragment
from ML.deep_research.layer3.settings import DOMAIN_NAMES, REASONING_EFFORT
from ML.deep_research.layer3.sources import load_jsonl
from ML.deep_research.layer3.usage import (
    UsageCallback,
    record_event,
    record_search_usage,
    summarize_usage,
)

from tests.common import create_complete_run


class Layer3UsageTests(unittest.TestCase):
    def test_model_and_search_usage_record_actor_phase_and_token_details(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = create_run(
                create_complete_run(root),
                root / "l3-runs",
                public_input_confirmed=True,
            )
            message = SimpleNamespace(
                name=DOMAIN_NAMES[0],
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "input_token_details": {"cache_read": 40},
                    "output_token_details": {"reasoning": 7},
                },
            )
            response = SimpleNamespace(
                generations=[[SimpleNamespace(message=message)]]
            )
            callback = UsageCallback(run_dir, "thread-1")
            model_run_id = uuid4()
            callback.on_chat_model_start(
                {}, [], run_id=model_run_id, metadata={"lc_agent_name": DOMAIN_NAMES[0]}
            )
            message.name = None
            callback.on_llm_end(response, run_id=model_run_id)
            record_search_usage(
                run_dir,
                SimpleNamespace(
                    id="search-1",
                    usage={
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "total_tokens": 12,
                        "input_tokens_details": {"cached_tokens": 3},
                        "output_tokens_details": {"reasoning_tokens": 1},
                    },
                ),
                DOMAIN_NAMES[1],
                "thread-2",
            )
            record_event(
                run_dir,
                event_id="published-domain-1",
                phase="report_publish",
                actor=DOMAIN_NAMES[0],
                session_id="thread-1",
                detail="domains/example.md",
            )

            records = load_jsonl(run_dir / "usage.jsonl")
            self.assertEqual(
                {item["phase"] for item in records},
                {"model", "web_search", "report_publish"},
            )
            self.assertTrue(
                all(item["actor"] and item["timestamp"] for item in records)
            )
            self.assertEqual(
                {item["actor"] for item in records},
                {DOMAIN_NAMES[0], DOMAIN_NAMES[1]},
            )
            self.assertEqual(
                {item["session_id"] for item in records}, {"thread-1", "thread-2"}
            )
            summary = summarize_usage(run_dir)
            self.assertEqual(summary["api_calls"], 2)
            self.assertEqual(summary["model_calls"], 1)
            self.assertEqual(summary["web_search_calls"], 1)
            self.assertEqual(summary["events"], 1)
            self.assertEqual(summary["cached_input_tokens"], 43)
            self.assertEqual(summary["reasoning_output_tokens"], 8)


    def test_progressive_append_records_one_replay_safe_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            context = ResearchContext(
                run_dir, DOMAIN_NAMES[0], "domain-thread", object()
            )
            _append_fragment(context, DOMAIN_NAMES[0], "finding-1", "Finding one.\n")
            _append_fragment(context, DOMAIN_NAMES[0], "finding-1", "Finding one.\n")

            records = load_jsonl(run_dir / "usage.jsonl")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["phase"], "report_progress")
            self.assertEqual(summarize_usage(run_dir)["api_calls"], 0)


class Layer3SearchRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_low_context_and_layer3_reasoning(self):
        seen = {}

        class Responses:
            async def create(self, **kwargs):
                seen.update(kwargs)
                return SimpleNamespace(
                    usage=None,
                    model_dump=lambda **_: {"output": []},
                )

        retriever = object.__new__(OpenAISearchRetriever)
        retriever.run_dir = Path("unused")
        retriever.client = SimpleNamespace(responses=Responses())
        await retriever.search("official property record", actor=DOMAIN_NAMES[0])

        self.assertEqual(
            seen["tools"], [{"type": "web_search", "search_context_size": "low"}]
        )
        self.assertEqual(seen["reasoning"], {"effort": REASONING_EFFORT})


if __name__ == "__main__":
    unittest.main()
