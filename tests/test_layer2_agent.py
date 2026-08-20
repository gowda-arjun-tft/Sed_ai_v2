"""The agent is built with capabilities, not instructions.

These construct the graph and inspect it. No API call, no model turn.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.agent import (
    RECURSION_LIMIT,
    create_mission_agent,
    subagents,
    system_prompt,
)
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.python_tool import run_python_code
from ML.deep_research.layer2.settings import PLANNER_PATH

from tests.common import create_complete_run


class AgentSurfaceTests(unittest.TestCase):
    def test_the_agent_has_a_filesystem_python_and_delegation(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                graph = create_mission_agent(run_dir)
            tools = set(graph.nodes["tools"].bound.tools_by_name)

        # Reading the sheet, writing the missions, checking its own work,
        # and handing a mission to a subagent.
        for expected in ("read_file", "write_file", "ls", "glob", "grep", "run_python", "task"):
            self.assertIn(expected, tools, expected)

        # No tool that validates, rejects or scores what the agent produces.
        self.assertNotIn("append_to_bucket", tools)
        self.assertNotIn("mark_piece_done", tools)

    def test_no_ceiling_middleware_is_added(self):
        """`middleware=[]` adds no ceiling. It does not make the graph bare.

        The harness installs its own filesystem, subagent, summarisation and
        tool-call-repair middleware regardless, and those are what make the file
        tools and `task` exist. The earlier version of this test was named
        `test_no_middleware_wraps_the_model`, which claimed more than it checked.

        A ceiling would take away tool calls, so the absence is asserted where it
        would actually show: on the tool surface, and on the module namespace the
        agent is built from.
        """
        import ML.deep_research.layer2.agent as module

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                graph = create_mission_agent(run_dir)
            node_names = [type(item).__name__ for item in graph.nodes.values()]
            tools = set(graph.nodes["tools"].bound.tools_by_name)

        for ceiling in ("ModelCallLimitMiddleware", "ToolCallLimitMiddleware"):
            self.assertNotIn(ceiling, node_names, ceiling)
            self.assertNotIn(ceiling, dir(module), ceiling)
        # The harness's own middleware is what puts these here. Their presence is
        # the positive half of the claim: nothing was excluded either.
        for expected in ("read_file", "write_file", "task"):
            self.assertIn(expected, tools, expected)

    def test_no_helper_can_delegate_further(self):
        """Delegation is exactly one level deep, and the prompts must say so.

        `SubAgentMiddleware` is attached to the main agent only, so no subagent
        gets a `task` tool. `mission_writer.md` once told the writer it could
        "delegate the parts the same way the caller delegated to you" -- an
        instruction with no tool behind it.
        """
        from ML.deep_research.layer2.settings import PROMPTS_DIR

        for name in ("slice_reader.md", "mission_writer.md"):
            text = (PROMPTS_DIR / name).read_text(encoding="utf-8-sig").casefold()
            self.assertIn("cannot delegate", text, name)

    def test_the_prompt_names_the_explicit_general_purpose_helper(self):
        """Layer 2 keeps this helper even after Layer 3 disables the implicit one."""
        planner_text, _ = load_planner(PLANNER_PATH)
        prompt = system_prompt(Path("/tmp/run"), planner_text).casefold()
        self.assertIn("general-purpose", prompt)
        self.assertIn("no `task` tool", prompt)
        self.assertIn("general-purpose", {item["name"] for item in subagents()})

    def test_recursion_limit_lifts_the_real_langgraph_default(self):
        """Above the *installed* default, not the 25 the old docs claimed.

        Read from langgraph rather than restated, so a version bump that changes
        the default fails here instead of quietly making this assertion vacuous.
        """
        from langgraph._internal._config import DEFAULT_RECURSION_LIMIT

        self.assertGreater(RECURSION_LIMIT, DEFAULT_RECURSION_LIMIT)
        self.assertGreater(DEFAULT_RECURSION_LIMIT, 25, "the old comment said 25")


class PromptTests(unittest.TestCase):
    def test_the_prompt_carries_the_roster_and_the_real_run_path(self):
        planner_text, definitions = load_planner(PLANNER_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary).resolve()
            prompt = system_prompt(run_dir, planner_text)
        self.assertIn(str(run_dir), prompt)
        self.assertNotIn("{run_dir}", prompt)
        for definition in definitions:
            self.assertIn(definition["name"], prompt)

    def test_the_prompt_states_the_goal_without_prescribing_method(self):
        planner_text, _ = load_planner(PLANNER_PATH)
        prompt = system_prompt(Path("/tmp/run"), planner_text).casefold()
        self.assertIn("/run/inputs/fact_sheet.md", prompt)
        self.assertIn("/run/missions/", prompt)
        # None of the old machinery is described to the agent.
        for banned in ("progress.csv", "append_to_bucket", "mark_piece_done", "_unrouted"):
            self.assertNotIn(banned.casefold(), prompt, banned)

    def test_all_helpers_bring_their_own_prompt(self):
        """Subagents never inherit system_prompt."""
        helpers = {item["name"]: item for item in subagents()}
        self.assertEqual(
            set(helpers), {"slice-reader", "mission-writer", "general-purpose"}
        )
        for name, helper in helpers.items():
            self.assertTrue(helper["system_prompt"].strip(), name)
            self.assertTrue(helper["description"].strip(), name)

    def test_the_prompt_states_the_context_rule_and_measure_first(self):
        """The 20k rule is guidance to the agent, not a knife in the code."""
        planner_text, _ = load_planner(PLANNER_PATH)
        prompt = system_prompt(Path("/tmp/run"), planner_text).casefold()
        self.assertIn("20,000", prompt)
        self.assertIn("measure before you read", prompt)
        # Said plainly, because the failure mode is silent.
        self.assertIn("forgetting looks exactly like", prompt)
        # And it is guidance, not a limit: nothing truncates.
        self.assertIn("nothing does", prompt)

    def test_the_prompt_describes_summarisation_as_it_actually_behaves(self):
        """It keeps the recent tenth, not "the older half" as this once said.

        Read from the installed package rather than restated, so a change in the
        harness's defaults fails here instead of leaving the prompt quietly wrong.
        """
        import os as _os

        from deepagents.middleware.summarization import compute_summarization_defaults

        planner_text, _ = load_planner(PLANNER_PATH)
        prompt = system_prompt(Path("/tmp/run"), planner_text).casefold()

        with patch.dict(_os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
            from langchain.chat_models import init_chat_model

            from ML.deep_research.layer2.agent import configure_provider
            from ML.deep_research.layer2.settings import MODEL_SPEC, REASONING_EFFORT

            configure_provider()
            model = init_chat_model(
                MODEL_SPEC,
                reasoning_effort=REASONING_EFFORT,
                store=False,
                use_responses_api=True,
            )
        defaults = compute_summarization_defaults(model)

        self.assertEqual(defaults["trigger"], ("fraction", 0.85))
        self.assertEqual(defaults["keep"], ("fraction", 0.1))
        # The prompt must describe that, and must not claim it is half.
        self.assertIn("85%", prompt)
        self.assertIn("recent tenth", prompt)
        self.assertNotIn("compresses the older half", prompt)


class PythonToolTests(unittest.TestCase):
    def test_python_runs_and_returns_output(self):
        result = run_python_code("print(2 + 2)")
        self.assertTrue(result.ok)
        self.assertIn("4", result.stdout)

    def test_output_is_not_capped(self):
        result = run_python_code("print('x' * 60000)")
        self.assertTrue(result.ok)
        self.assertGreaterEqual(len(result.stdout), 60000)

    def test_a_failing_snippet_reports_rather_than_raises(self):
        result = run_python_code("raise SystemExit('nope')")
        self.assertFalse(result.ok)
        self.assertIn("nope", result.render())


if __name__ == "__main__":
    unittest.main()
