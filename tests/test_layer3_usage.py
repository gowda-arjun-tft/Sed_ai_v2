from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from langchain_core.messages import ToolMessage

from ML.deep_research.layer3.contracts import RESEARCHER_NAME
from tests.historical_layer3 import create_run
from ML.deep_research.layer3.pipeline.progress import model_turns, stage_event
from ML.deep_research.layer3.providers.openai_search import OpenAISearchRetriever
from ML.deep_research.layer3.settings import DOMAIN_NAMES
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
            model_record = next(item for item in records if item["phase"] == "model")
            self.assertEqual(model_record["operation"], "research")
            self.assertFalse(model_record["over_soft_target"])

    def test_summarization_and_compaction_are_observable_without_gating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = create_run(
                create_complete_run(root),
                root / "l3-runs",
                public_input_confirmed=True,
            )
            callback = UsageCallback(run_dir, "thread-summary")
            run_id = uuid4()
            callback.on_chat_model_start(
                {},
                [[
                    ToolMessage(
                        content="source pointer",
                        tool_call_id="source-1",
                        response_metadata={
                            "context_editing": {
                                "cleared": True,
                                "strategy": "clear_tool_uses",
                            }
                        },
                    ),
                    ToolMessage(
                        content="ordinary tool result",
                        tool_call_id="search-1",
                    ),
                ]],
                run_id=run_id,
                metadata={
                    "lc_agent_name": RESEARCHER_NAME,
                    "lc_source": "summarization",
                },
            )
            response = SimpleNamespace(
                generations=[[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            name=None,
                            usage_metadata={
                                "input_tokens": 210_000,
                                "output_tokens": 100,
                                "total_tokens": 210_100,
                            },
                        )
                    )
                ]]
            )
            callback.on_llm_end(response, run_id=run_id)
            record = load_jsonl(run_dir / "usage.jsonl")[0]
            summary = summarize_usage(run_dir)

        self.assertEqual(record["operation"], "summarization")
        self.assertEqual(record["compacted_source_results"], 1)
        self.assertTrue(record["over_soft_target"])
        self.assertEqual(record["soft_target_tokens"], 200_000)
        self.assertEqual(summary["summarization_calls"], 1)
        self.assertEqual(summary["over_soft_target_calls"], 1)
        self.assertEqual(summary["compacted_source_results"], 1)

    def test_attempt_sessions_remain_distinct_and_roll_up_to_one_thread(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = create_run(
                create_complete_run(root),
                root / "l3-runs",
                public_input_confirmed=True,
            )
            response = SimpleNamespace(
                generations=[[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            name=None,
                            usage_metadata={"input_tokens": 10, "total_tokens": 10},
                        )
                    )
                ]]
            )
            for attempt in (1, 2):
                callback = UsageCallback(run_dir, f"thread-1:attempt-{attempt}")
                model_run_id = uuid4()
                callback.on_chat_model_start(
                    {}, [], run_id=model_run_id, metadata={"agent": DOMAIN_NAMES[0]}
                )
                callback.on_llm_end(response, run_id=model_run_id)
                stage_event(
                    run_dir,
                    {
                        "thread_id": "thread-1",
                        "attempt": attempt,
                        "actor": DOMAIN_NAMES[0],
                    },
                    "stage_start",
                )
            records = load_jsonl(run_dir / "usage.jsonl")
            turns = model_turns(run_dir, "thread-1")
            summary = summarize_usage(run_dir)

        self.assertEqual(turns, 2)
        self.assertEqual(
            {item["session_id"] for item in records},
            {"thread-1:attempt-1", "thread-1:attempt-2"},
        )
        self.assertEqual(summary["total_tokens"], 20)

    def test_usage_accepts_direct_researcher_actor(self):
        self.assertEqual(RESEARCHER_NAME, "domain-researcher")


class Layer3SearchRequestTests(unittest.IsolatedAsyncioTestCase):
    def test_search_client_retries_transient_failures_three_times(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
            retriever = OpenAISearchRetriever(
                Path("unused"),
                reasoning_effort="low",
                context_size="low",
                verbosity="low",
            )

        self.assertEqual(retriever.client.max_retries, 3)

    async def test_search_uses_recorded_controls(self):
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
        retriever.reasoning_effort = "high"
        retriever.context_size = "medium"
        retriever.verbosity = "low"
        retriever.client = SimpleNamespace(responses=Responses())
        await retriever.search("official property record", actor=DOMAIN_NAMES[0])

        self.assertEqual(
            seen["tools"], [{"type": "web_search", "search_context_size": "medium"}]
        )
        self.assertEqual(seen["reasoning"], {"effort": "high"})
        self.assertEqual(seen["text"], {"verbosity": "low"})


if __name__ == "__main__":
    unittest.main()
