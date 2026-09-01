import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain.agents.structured_output import ProviderStrategy
from pydantic import ValidationError

from ML.deep_research.layer2.agent import (
    Layer2Response,
    _partition_chunk,
    chunk_request,
    create_chunk_agent,
    response_value,
    system_prompt,
)
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.harness import build_model
from ML.deep_research.layer2.settings import (
    AGENT_NAMES,
    CHUNK_ENCODING,
    CHUNK_OVERLAP_TOKENS,
    PLANNER_PATH,
)
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
        self.assertEqual(strategy.schema_spec.json_schema["properties"], {})
        self.assertTrue(strategy.schema_spec.json_schema["additionalProperties"])

    def test_provider_strategy_binds_the_permissive_schema_without_a_model_call(self):
        strategy = ProviderStrategy(Layer2Response, strict=False)
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            model = build_model("medium")
            bound = model.bind_tools([], **strategy.to_model_kwargs())

        response_format = bound.kwargs["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertEqual(response_format["json_schema"]["schema"]["properties"], {})

    def test_prompt_and_request_keep_roster_separate_from_chunk_data(self):
        prompt = system_prompt(PLANNER_PATH)
        self.assertIn("<routing_contract>", prompt)
        self.assertIn("# Inputs and authority", prompt)
        self.assertIn(AGENT_NAMES[-1], prompt)
        self.assertIn('"missions": [', prompt)
        self.assertIn("Produce domain context only", prompt)
        self.assertIn("Do not reproduce", prompt)
        self.assertIn("completes, changes, contradicts or materially", prompt)
        self.assertIn("qualifies information", prompt)
        self.assertNotIn('"mission":', prompt)
        self.assertNotIn('"domains":', prompt)
        self.assertNotIn("write questions", prompt.casefold())
        request = chunk_request(
            "## Input\ntext", 2, 3, CHUNK_ENCODING, CHUNK_OVERLAP_TOKENS
        )
        self.assertIn('<fact_sheet_chunk index="2" total="3">', request)
        self.assertIn("<overlap_context>", request)
        self.assertIn("<new_content>", request)
        self.assertNotIn("Return one JSON object", request)

    def test_overlap_aware_request_labels_exact_source_parts(self):
        import tiktoken

        encoding = tiktoken.get_encoding(CHUNK_ENCODING)
        token = encoding.encode(" property")[0]
        chunk = encoding.decode([token] * 60_000)
        overlap, new = _partition_chunk(chunk, 2, CHUNK_ENCODING, 10_000)
        self.assertEqual(len(encoding.encode(overlap)), 10_000)
        self.assertEqual(len(encoding.encode(new)), 50_000)
        self.assertEqual(encoding.encode(overlap + new), encoding.encode(chunk))

        request = chunk_request(
            chunk,
            2,
            14,
            CHUNK_ENCODING,
            10_000,
        )
        self.assertIn("<overlap_context>", request)
        self.assertIn("<new_content>", request)

    def test_first_overlap_aware_request_marks_everything_as_new(self):
        overlap, new = _partition_chunk("first source", 1, CHUNK_ENCODING, 10_000)
        self.assertEqual(overlap, "")
        self.assertEqual(new, "first source")

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
