"""Context management for the looping direct domain researcher.

Two things are pinned here. First the framework assumptions the design rests on,
so a dependency bump fails loudly instead of silently dropping compaction.
Second the eviction behaviour itself, exercised directly on a synthetic message
list so it is proven without a model call.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from ML.deep_research.layer3.contracts import RESEARCHER_NAME
from ML.deep_research.layer3.llm import (
    build_layer3_model,
    create_domain_researcher_harness,
    create_synthesis_harness,
)
from ML.deep_research.layer3.memory import (
    EVICTED_SOURCE_PLACEHOLDER,
    CdiResearchSummarization,
    context_policy,
    evidence_eviction,
    research_summarization,
)
from tests.historical_layer3 import create_run
from ML.deep_research.layer3.settings import (
    EVICTION_KEEP_TOOL_RESULTS,
    EVICTION_TRIGGER_TOKENS,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_SPEC,
)
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


class FrameworkAssumptionTests(unittest.TestCase):
    """The design reuses framework internals; pin what it depends on."""

    def test_context_editing_is_available_from_langchain(self):
        from langchain.agents.middleware import (
            ClearToolUsesEdit,
            ContextEditingMiddleware,
        )

        edit = ClearToolUsesEdit(trigger=1, keep=0, exclude_tools=("search_web",))
        self.assertTrue(hasattr(edit, "apply"))
        self.assertTrue(hasattr(ContextEditingMiddleware, "awrap_model_call"))

    def test_summarization_base_class_is_available_from_deepagents(self):
        from deepagents.middleware import SummarizationMiddleware

        self.assertTrue(issubclass(CdiResearchSummarization, SummarizationMiddleware))

    def test_subclass_escapes_the_summarization_name_exclusion(self):
        """The whole design rests on this: the alias is not inherited.

        `configure_harness` excludes `SummarizationMiddleware` by name, and
        `create_deep_agent` re-applies that exclusion after merging caller
        middleware. A subclass reporting the alias would be dropped in silence.
        """
        from deepagents.middleware import SummarizationMiddleware
        from deepagents.backends import StateBackend

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ):
            run_dir = _new_l3(Path(temporary))
            model = build_layer3_model(run_dir)
            ours = research_summarization(model, StateBackend(), _policy(run_dir))
            theirs = SummarizationMiddleware(model, backend=StateBackend())

        self.assertEqual(theirs.name, "SummarizationMiddleware")
        self.assertEqual(ours.name, "CdiResearchSummarization")

    def test_compaction_survives_the_real_exclusion_filter(self):
        """Run the actual filter, not just the spec we hand in.

        `create_deep_agent` re-applies `excluded_middleware` after merging
        caller middleware, so a spec containing compaction proves nothing on its
        own. This drives the same filter with the same profile the run uses.
        """
        from deepagents._excluded_middleware import _apply_excluded_middleware
        from deepagents.backends import StateBackend
        from deepagents.middleware import SummarizationMiddleware
        from deepagents.profiles.harness.harness_profiles import _get_harness_profile
        from ML.deep_research.layer2.ML.harness import configure_harness

        configure_harness()
        profile = _get_harness_profile(MODEL_SPEC)

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ):
            run_dir = _new_l3(Path(temporary))
            model = build_layer3_model(run_dir)
            stack = [
                SummarizationMiddleware(model, backend=StateBackend()),
                evidence_eviction(_policy(run_dir)),
                research_summarization(model, StateBackend(), _policy(run_dir)),
            ]

        survivors = [
            middleware.name
            for middleware in _apply_excluded_middleware(stack, profile)
        ]

        # The framework's own default-configured summarizer is still stripped;
        # ours and the eviction pass are kept.
        self.assertEqual(
            survivors,
            ["ContextEditingMiddleware", "CdiResearchSummarization"],
        )

    def test_model_profile_still_reports_the_expected_window(self):
        """Thresholds are fractions of this; a shrunk window must fail here."""
        from langchain.chat_models import init_chat_model

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
            profile = init_chat_model(MODEL_SPEC, use_responses_api=True).profile

        self.assertIsInstance(profile, dict)
        self.assertEqual(profile.get("max_input_tokens"), MODEL_INPUT_TOKEN_LIMIT)


class ResearcherWiringTests(unittest.TestCase):
    def test_only_direct_researcher_gets_context_management(self):
        """Capture construction because a compiled graph hides its middleware."""
        import deepagents

        captured: list[dict] = []

        def record(**kwargs):
            captured.append(kwargs)
            return object()

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ), patch.object(deepagents, "create_deep_agent", record):
            run_dir = _new_l3(Path(temporary))
            create_domain_researcher_harness(run_dir)
            create_synthesis_harness(run_dir)

        self.assertEqual(len(captured), 2)
        researcher, synthesis = captured
        self.assertEqual(researcher["name"], RESEARCHER_NAME)
        self.assertEqual(
            [middleware.name for middleware in researcher["middleware"]],
            [
                "FilesystemMiddleware",
                "ContextEditingMiddleware",
                "CdiResearchSummarization",
            ],
        )
        self.assertEqual(
            {tool.name for tool in researcher["tools"]},
            {"search_web", "read_source"},
        )
        self.assertEqual(researcher["subagents"], [])
        self.assertEqual(
            [middleware.name for middleware in synthesis["middleware"]],
            ["FilesystemMiddleware"],
        )
        self.assertEqual(synthesis["tools"], [])
        self.assertEqual(synthesis["subagents"], [])


def _conversation(read_bodies: int) -> list:
    """Interleaved search and read turns, with oversized source bodies."""
    messages: list = [HumanMessage(content="Research this property.")]
    body = "Amtsgericht Bad Homburg cost table row. " * 900
    for index in range(read_bodies):
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_web",
                        "args": {"query": f"query {index}"},
                        "id": f"s{index}",
                    }
                ],
            )
        )
        messages.append(
            ToolMessage(content=f"HIT {index}\nURL https://example.test/{index}", tool_call_id=f"s{index}")
        )
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_source",
                        "args": {"url": f"https://example.test/{index}"},
                        "id": f"r{index}",
                    }
                ],
            )
        )
        messages.append(
            ToolMessage(content=f"SOURCE {index}\n\n{body}", tool_call_id=f"r{index}")
        )
    return messages


class EvictionBehaviourTests(unittest.TestCase):
    """Prove the mechanism on a synthetic history, with no model call."""

    def setUp(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = _policy(_new_l3(Path(temporary)))
        self.edit = evidence_eviction(policy).edits[0]
        self.messages = _conversation(read_bodies=24)
        self.before = count_tokens_approximately(self.messages)
        self.assertGreater(self.before, EVICTION_TRIGGER_TOKENS)

    def _apply(self, messages: list) -> None:
        self.edit.apply(messages, count_tokens=count_tokens_approximately)

    def test_below_the_trigger_nothing_is_touched(self):
        small = _conversation(read_bodies=1)
        self.assertLess(count_tokens_approximately(small), EVICTION_TRIGGER_TOKENS)
        original = [message.content for message in small]
        self._apply(small)
        self.assertEqual([message.content for message in small], original)

    def test_only_older_source_bodies_are_cleared(self):
        self._apply(self.messages)

        cleared = [
            message
            for message in self.messages
            if isinstance(message, ToolMessage)
            and str(message.content).startswith(EVICTED_SOURCE_PLACEHOLDER)
        ]
        self.assertTrue(cleared, "expected some source bodies to be cleared")

        # Search results are the map of what exists: never evicted.
        searches = [
            message
            for message in self.messages
            if isinstance(message, ToolMessage) and message.tool_call_id.startswith("s")
        ]
        self.assertTrue(all(message.content.startswith("HIT") for message in searches))

        # The most recent tool results stay intact.
        tool_messages = [m for m in self.messages if isinstance(m, ToolMessage)]
        for message in tool_messages[-EVICTION_KEEP_TOOL_RESULTS:]:
            self.assertNotEqual(message.content, EVICTED_SOURCE_PLACEHOLDER)

    def test_the_url_survives_so_the_source_can_be_re_read(self):
        self._apply(self.messages)

        calls = [
            call
            for message in self.messages
            if isinstance(message, AIMessage)
            for call in message.tool_calls
            if call["name"] == "read_source"
        ]
        self.assertTrue(calls)
        for call in calls:
            self.assertTrue(call["args"]["url"].startswith("https://example.test/"))

    def test_eviction_reclaims_context_and_is_idempotent(self):
        self._apply(self.messages)
        after_first = count_tokens_approximately(self.messages)
        self.assertLess(after_first, self.before)

        snapshot = [message.content for message in self.messages]
        self._apply(self.messages)
        self.assertEqual([message.content for message in self.messages], snapshot)


if __name__ == "__main__":
    unittest.main()
