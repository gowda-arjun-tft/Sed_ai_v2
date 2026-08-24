from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from ML.deep_research.layer2.fs import load_json, write_json
from ML.deep_research.layer3.contracts import Document, ResearchContext
from ML.deep_research.layer3.llm import _subagents
from ML.deep_research.layer3.memory import (
    EVICTED_SOURCE_PLACEHOLDER,
    CdiResearchSummarization,
    context_policy,
    evidence_eviction,
    research_summarization,
)
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.research_tools import _read
from tests.common import create_complete_run


def _new_l3(root: Path) -> Path:
    return create_run(
        create_complete_run(root),
        root / "l3",
        public_input_confirmed=True,
    )


def _policy(run_dir: Path):
    value = context_policy(run_dir)
    assert value is not None
    return value


def _names(spec: dict) -> list[str]:
    return [middleware.name for middleware in spec["middleware"]]


class ContextPolicyTests(unittest.TestCase):
    def test_new_run_records_early_compaction_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            policy = _policy(run_dir)
            recorded = load_json(run_dir / "run.json")["context_management"]

        self.assertEqual(policy.soft_target_tokens, 200_000)
        self.assertEqual(policy.eviction_trigger_tokens, 150_000)
        self.assertEqual(policy.emergency_eviction_trigger_tokens, 170_000)
        self.assertEqual(policy.summary_trigger_tokens, 170_000)
        self.assertEqual(policy.summary_keep_tokens, 70_000)
        self.assertIsNone(policy.summary_trim_tokens)
        self.assertEqual(recorded["policy_version"], 1)

    def test_runtime_uses_frozen_run_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            with patch(
                "ML.deep_research.layer3.settings.EVICTION_TRIGGER_TOKENS",
                999,
            ):
                specs = _subagents(run_dir)

        eviction = specs[0]["middleware"][1]
        self.assertEqual(eviction.edits[0].trigger, 150_000)
        self.assertEqual([edit.clear_at_least for edit in eviction.edits], [0, 0])

    def test_unknown_policy_warns_and_disables_compaction_without_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            run["context_management"]["policy_version"] = 99
            write_json(run_dir / "run.json", run)
            with self.assertWarnsRegex(RuntimeWarning, "compaction is disabled"):
                specs = _subagents(run_dir)

        for spec in specs:
            self.assertEqual(_names(spec), ["FilesystemMiddleware"])

    def test_versionless_run_keeps_legacy_no_compaction_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            run = load_json(run_dir / "run.json")
            run.pop("context_management")
            write_json(run_dir / "run.json", run)
            specs = _subagents(run_dir)
            loaded_policy = context_policy(run_dir)

        self.assertIsNone(loaded_policy)
        for spec in specs:
            self.assertEqual(_names(spec), ["FilesystemMiddleware"])


class EarlyCompactionTests(unittest.IsolatedAsyncioTestCase):
    def test_emergency_eviction_clears_one_recent_oversized_source(self):
        source_id = "a" * 64
        messages = [
            AIMessage(
                content="",
                tool_calls=[{
                    "name": "read_source",
                    "args": {"url": "https://example.test/large"},
                    "id": "source-call",
                }],
            ),
            ToolMessage(
                content=f"SOURCE {source_id}\n\n" + "property evidence " * 90_000,
                tool_call_id="source-call",
            ),
        ]
        before = count_tokens_approximately(messages)

        with tempfile.TemporaryDirectory() as temporary:
            middleware = evidence_eviction(_policy(_new_l3(Path(temporary))))
        for edit in middleware.edits:
            edit.apply(messages, count_tokens=count_tokens_approximately)

        self.assertGreater(before, 200_000)
        self.assertLess(count_tokens_approximately(messages), 200_000)
        self.assertIn(EVICTED_SOURCE_PLACEHOLDER, messages[-1].content)
        self.assertIn(source_id, messages[-1].content)
        self.assertEqual(
            messages[0].tool_calls[0]["args"]["url"],
            "https://example.test/large",
        )

    async def test_summarizer_receives_the_complete_old_portion(self):
        seen = {}

        class CapturingModel:
            profile = {}
            _llm_type = "capturing-model"

            def with_retry(self):
                return self

            async def ainvoke(self, prompt, config=None):
                seen["prompt"] = prompt
                return SimpleNamespace(text="compact record")

        with tempfile.TemporaryDirectory() as temporary:
            policy = _policy(_new_l3(Path(temporary)))
        summarizer = research_summarization(CapturingModel(), object(), policy)
        messages = [
            HumanMessage(content="FIRST-UNIQUE-MARKER " + "old fact " * 6_000),
            HumanMessage(content="LAST-UNIQUE-MARKER"),
        ]
        result = await summarizer._acreate_summary(messages)

        self.assertEqual(result, "compact record")
        self.assertIn("FIRST-UNIQUE-MARKER", seen["prompt"])
        self.assertIn("LAST-UNIQUE-MARKER", seen["prompt"])
        self.assertIsNone(summarizer._lc_helper.trim_tokens_to_summarize)
        self.assertEqual(summarizer._lc_helper.trigger, ("tokens", 170_000))
        self.assertEqual(summarizer._lc_helper.keep, ("tokens", 70_000))

    def test_summary_wrapper_names_only_available_recovery(self):
        message = CdiResearchSummarization._build_new_messages_with_path(
            object(), "summary", "/conversation_history/session.md"
        )[0]

        self.assertIn("not available through your tools", message.content)
        self.assertIn("read_source", message.content)
        self.assertNotIn("should you need to refer back", message.content)

    async def test_read_source_reuses_the_stored_document(self):
        class Retriever:
            calls = 0

            async def fetch(self, url):
                self.calls += 1
                return Document(
                    url=url,
                    content_type="text/plain",
                    body=b"stored property evidence",
                    fetched_at="2026-08-24T00:00:00Z",
                )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            retriever = Retriever()
            context = ResearchContext(run_dir, "agent", "session", retriever)
            first = await _read(context, "https://example.test/source")
            second = await _read(context, "https://example.test/source")

        self.assertEqual(retriever.calls, 1)
        self.assertEqual(first, second)
        self.assertIn("stored property evidence", first)


if __name__ == "__main__":
    unittest.main()
