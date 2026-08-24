import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain.agents.structured_output import ProviderStrategy
from pydantic import ValidationError

from ML.deep_research.layer2.agent import (
    Layer2Response,
    chunk_request,
    create_chunk_agent,
    domain_key,
    response_value,
    system_prompt,
)
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.harness import build_model
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
                graph = create_chunk_agent(self._run(Path(temporary)))
        tools = set()
        if "tools" in graph.nodes:
            bound = graph.nodes["tools"].bound
            tools = set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {})))
        self.assertEqual(tools, set())
        self.assertIsNone(graph.checkpointer)
        self.assertFalse(any("summar" in name.casefold() for name in graph.nodes))

    def test_domain_keys_remain_stable(self):
        self.assertEqual(len({domain_key(name) for name in AGENT_NAMES}), 8)

    def test_provider_has_no_application_output_cap(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            model = build_model("medium")
        self.assertIsNone(model.max_tokens)
        self.assertEqual(model.reasoning_effort, "medium")
        self.assertFalse(model.store)
        self.assertEqual(model.max_retries, 3)
        self.assertNotIn("response_format", model.model_kwargs)

    def test_graph_uses_permissive_provider_structured_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch.dict("os.environ", {"OPENAI_API_KEY": "test"}),
                patch("deepagents.create_deep_agent") as create,
            ):
                create_chunk_agent(run_dir)

        strategy = create.call_args.kwargs["response_format"]
        self.assertIsInstance(strategy, ProviderStrategy)
        self.assertIs(strategy.schema, Layer2Response)
        self.assertFalse(strategy.schema_spec.strict)
        self.assertEqual(strategy.schema_spec.json_schema["type"], "object")
        self.assertTrue(strategy.schema_spec.json_schema["additionalProperties"])

    def test_prompt_and_request_keep_roster_separate_from_chunk_data(self):
        prompt = system_prompt(PLANNER_PATH)
        self.assertIn("<routing_contract>", prompt)
        self.assertIn("# Success criteria", prompt)
        self.assertIn("# Inputs and authority", prompt)
        self.assertIn(AGENT_NAMES[-1], prompt)
        self.assertIn("property-specific risk questions", prompt)
        self.assertIn("Do not restate a domain mandate", prompt)
        self.assertIn("empty mission and empty context", prompt)
        self.assertIn("or an empty string", prompt)
        self.assertNotIn("still receives a non-empty mission", prompt)
        request = chunk_request("## Input\ntext", 2, 3)
        self.assertIn('<fact_sheet_chunk index="2" total="3">', request)
        self.assertNotIn("Return one JSON object", request)

    def test_response_accepts_any_json_object_without_content_validation(self):
        value = {"unexpected": {"shape": True}}
        result = {"structured_response": Layer2Response(root=value)}
        self.assertEqual(response_value(result), value)
        self.assertEqual(response_value({"structured_response": Layer2Response(root={})}), {})
        with self.assertRaises(ValidationError):
            Layer2Response.model_validate([])
        with self.assertRaisesRegex(ValueError, "no structured JSON object"):
            response_value({})


if __name__ == "__main__":
    unittest.main()
