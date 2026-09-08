from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer3.contracts import RESEARCHER_NAME
from ML.deep_research.layer3.llm import (
    build_layer3_model,
    create_domain_researcher_harness,
    create_synthesis_harness,
    final_text,
)
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.settings import DOMAIN_NAMES
from tests.common import create_complete_run


def _tools(graph) -> set[str]:
    if "tools" not in graph.nodes:
        return set()
    bound = graph.nodes["tools"].bound
    return set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {})))


def _new_l3(root: Path, **options) -> Path:
    return create_run(
        create_complete_run(root),
        root / "l3",
        public_input_confirmed=True,
        **options,
    )


class Layer3HarnessSurfaceTests(unittest.TestCase):
    def test_plain_markdown_is_the_only_final_output_contract(self):
        state = {"messages": [AIMessage(content="# Decision\n\nProceed.")]}
        self.assertEqual(final_text(state), "# Decision\n\nProceed.")
        self.assertEqual(final_text({"messages": []}), "")

    def test_model_uses_run_reasoning_without_application_output_cap(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ):
            run_dir = _new_l3(Path(temporary), reasoning_effort="high")
            model = build_layer3_model(run_dir)
        self.assertEqual(model.reasoning_effort, "high")
        self.assertIsNone(model.max_tokens)
        self.assertFalse(model.store)
        self.assertEqual(model.request_timeout, 600.0)
        self.assertEqual(model.max_retries, 3)

    def test_researcher_has_only_evidence_tools_and_synthesis_has_none(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ):
            run_dir = _new_l3(Path(temporary))
            researcher = create_domain_researcher_harness(run_dir)
            synthesis = create_synthesis_harness(run_dir)

        self.assertEqual(_tools(researcher), {"search_web", "read_source"})
        self.assertEqual(_tools(synthesis), set())
        for forbidden in ("task", "run_python", "execute"):
            self.assertNotIn(forbidden, _tools(researcher))
        descriptions = {
            name: researcher.nodes["tools"].bound.tools_by_name[name].description
            for name in _tools(researcher)
        }
        self.assertIn("candidate sources", descriptions["search_web"])
        self.assertIn("canonical text", descriptions["read_source"])

    def test_implicit_summarization_and_tool_call_repair_are_disabled(self):
        from deepagents.profiles.harness.harness_profiles import _get_harness_profile
        from ML.deep_research.layer2.ML.harness import configure_harness
        from ML.deep_research.layer3.settings import MODEL_SPEC

        configure_harness()
        profile = _get_harness_profile(MODEL_SPEC)
        self.assertEqual(
            profile.excluded_middleware,
            frozenset({"SummarizationMiddleware", "PatchToolCallsMiddleware"}),
        )

    def test_researcher_identity_is_stable_and_prompt_is_domain_neutral(self):
        import deepagents

        captured = {}

        def record(**kwargs):
            captured.update(kwargs)
            return object()

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ), patch.object(deepagents, "create_deep_agent", record):
            run_dir = _new_l3(Path(temporary))
            create_domain_researcher_harness(run_dir)

        self.assertEqual(captured["name"], RESEARCHER_NAME)
        self.assertEqual(captured["subagents"], [])
        self.assertNotIn(DOMAIN_NAMES[0], captured["system_prompt"])


if __name__ == "__main__":
    unittest.main()
