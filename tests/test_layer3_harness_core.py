from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer3.contracts import LENS_NAMES, VERIFIER_NAME
from ML.deep_research.layer3.llm import (
    _subagents,
    build_layer3_model,
    create_domain_coordinator_harness,
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

    def test_coordinator_has_only_task_and_synthesis_has_no_tools(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ):
            run_dir = _new_l3(Path(temporary))
            coordinator = create_domain_coordinator_harness(run_dir)
            synthesis = create_synthesis_harness(run_dir)
            task = coordinator.nodes["tools"].bound.tools_by_name["task"]

        self.assertEqual(_tools(coordinator), {"task"})
        self.assertEqual(_tools(synthesis), set())
        self.assertNotIn("general-purpose", task.description)
        for name in (*LENS_NAMES, VERIFIER_NAME):
            self.assertIn(f"- {name}:", task.description)
        for forbidden in ("search_web", "read_source", "run_python", "execute"):
            self.assertNotIn(forbidden, _tools(coordinator))

    def test_implicit_summarization_and_tool_call_repair_are_disabled(self):
        from deepagents.profiles.harness.harness_profiles import _get_harness_profile
        from ML.deep_research.layer2.harness import configure_harness
        from ML.deep_research.layer3.settings import MODEL_SPEC

        configure_harness()
        profile = _get_harness_profile(MODEL_SPEC)
        self.assertEqual(
            profile.excluded_middleware,
            frozenset({"SummarizationMiddleware", "PatchToolCallsMiddleware"}),
        )

    def test_each_fixed_subagent_has_only_two_evidence_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            specs = _subagents(run_dir)

        self.assertEqual([spec["name"] for spec in specs], [*LENS_NAMES, VERIFIER_NAME])
        for spec in specs:
            self.assertEqual({tool.name for tool in spec["tools"]}, {"search_web", "read_source"})
            self.assertNotIn("task", {tool.name for tool in spec["tools"]})

    def test_fixed_subagents_are_domain_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _new_l3(Path(temporary))
            specs = _subagents(run_dir)

        for spec in specs:
            self.assertNotIn(DOMAIN_NAMES[0], spec["system_prompt"])


if __name__ == "__main__":
    unittest.main()
