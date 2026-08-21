import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from ML.deep_research.layer2.agent import (
    ContextEntry,
    chunk_request,
    create_chunk_agent,
    domain_key,
    response_schema,
    structured_value,
    system_prompt,
)
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.harness import build_model
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH
from tests.common import FACT_SHEET


class StructuredHarnessTests(unittest.TestCase):
    def _run(self, root: Path) -> Path:
        sheet = root / "fact_sheet.md"
        sheet.write_text(FACT_SHEET, encoding="utf-8")
        return create_run(sheet, PLANNER_PATH, root / "runs")

    def test_graph_exposes_no_tools_or_implicit_subagents(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
                graph, _ = create_chunk_agent(self._run(Path(temporary)))
        tools = set()
        if "tools" in graph.nodes:
            bound = graph.nodes["tools"].bound
            tools = set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {})))
        self.assertEqual(tools, set())
        self.assertIsNone(graph.checkpointer)
        self.assertFalse(any("summar" in name.casefold() for name in graph.nodes))

    def test_schema_has_exactly_eight_required_domain_buckets(self):
        _, definitions = load_planner(PLANNER_PATH)
        schema = response_schema(definitions)
        self.assertEqual(set(schema.model_fields), {domain_key(name) for name in AGENT_NAMES})
        self.assertEqual(ContextEntry.model_json_schema()["properties"].keys(), {"section", "fact", "means"})
        self.assertNotIn("where", str(schema.model_json_schema()).casefold())

    def test_provider_has_no_application_output_cap(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            model = build_model()
        self.assertIsNone(model.max_tokens)
        self.assertEqual(model.reasoning_effort, "max")
        self.assertFalse(model.store)
        self.assertEqual(model.max_retries, 2)

    def test_prompt_and_request_keep_roster_separate_from_chunk_data(self):
        _, definitions = load_planner(PLANNER_PATH)
        prompt = system_prompt(definitions)
        self.assertIn("<domain_definitions>", prompt)
        self.assertIn(AGENT_NAMES[-1], prompt)
        request = chunk_request("## Input\ntext", 2, 3)
        self.assertIn("chunk 2 of 3", request)
        self.assertIn("<fact_sheet_chunk>", request)

    def test_structured_value_accepts_only_the_provider_schema(self):
        _, definitions = load_planner(PLANNER_PATH)
        schema = response_schema(definitions)
        valid = {
            domain_key(name): {"mission": "", "context": []}
            for name in AGENT_NAMES
        }
        parsed = structured_value({"structured_response": valid}, schema)
        self.assertIsInstance(parsed, schema)
        with self.assertRaises(ValidationError):
            structured_value({"structured_response": {}}, schema)


if __name__ == "__main__":
    unittest.main()
