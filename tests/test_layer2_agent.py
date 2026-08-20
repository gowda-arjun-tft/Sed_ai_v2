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

    def test_no_middleware_wraps_the_model(self):
        """No call ceilings, no tool-call ceilings, no retry policy."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                graph = create_mission_agent(run_dir)
            names = [type(item).__name__ for item in graph.nodes.values()]
        self.assertNotIn("ModelCallLimitMiddleware", names)
        self.assertNotIn("ToolCallLimitMiddleware", names)

    def test_recursion_limit_lifts_the_langgraph_default(self):
        """25 is LangGraph's default and would kill a real run mid-way."""
        self.assertGreater(RECURSION_LIMIT, 25)


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

    def test_both_helpers_bring_their_own_prompt(self):
        """Subagents never inherit system_prompt."""
        helpers = {item["name"]: item for item in subagents()}
        self.assertEqual(set(helpers), {"slice-reader", "mission-writer"})
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
