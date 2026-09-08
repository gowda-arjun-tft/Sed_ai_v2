import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain.agents.structured_output import ProviderStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ML.deep_research.layer2.ML.agent import Layer2Response, create_stage_agent, response_value
from ML.deep_research.layer2.ML.context import InputBudget, InputSizeError, estimate
from ML.deep_research.layer2.ML.harness import build_model
from ML.deep_research.layer2.backend.records import virtual_pages
from ML.deep_research.layer2.backend.settings import STAGES, PROMPTS_DIR
from tests.layer2_fixtures import new_run


class HarnessTests(unittest.TestCase):
    def test_actual_native_graph_tool_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            for stage in STAGES:
                graph = create_stage_agent(run, stage)
                bound = graph.nodes["tools"].bound if "tools" in graph.nodes else None
                tools = set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {})))
                expected = set() if stage in {"understanding", "distribution"} else {"ls", "glob", "grep", "read_file"}
                self.assertEqual(tools, expected)
                self.assertFalse(any("summar" in n.lower() for n in graph.nodes))

    def test_permissive_provider_and_unchanged_model(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            model = build_model("medium")
            bound = model.bind_tools([], **ProviderStrategy(Layer2Response, strict=False).to_model_kwargs())
        self.assertIsNone(model.max_tokens)
        self.assertEqual(model.max_retries, 3)
        self.assertEqual(model.reasoning_effort, "medium")
        schema = bound.kwargs["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"], {})
        self.assertTrue(schema["additionalProperties"])
        for value in [{}, {"odd": [None, 3, {"unknown": "yes"}]}]:
            self.assertEqual(response_value({"structured_response": Layer2Response(root=value)}), value)
        with self.assertRaises(ValueError):
            response_value({})

    def test_every_dispatch_counts_tools_and_schema(self):
        messages = [HumanMessage(content="hello")]
        plain = estimate(messages, "instructions", reserve=0)
        tools = [{"type": "function", "function": {"name": "read_file", "description": "extra " * 3000}}]
        full = estimate(messages, "instructions", tools, {"description": "schema " * 1000}, reserve=0)
        self.assertGreater(full, plain + 2000)
        policy = {"target_tokens": 100, "maximum_tokens": 200, "framing_reserve": 0}
        guard = InputBudget(Path("."), policy, "instructions", {})
        request = SimpleNamespace(messages=messages, system_message=HumanMessage(content="instructions"),
                                  tools=tools)
        with self.assertRaises(InputSizeError):
            guard.wrap_model_call(request, lambda _: self.fail("provider must not run"))
        with self.assertRaises(InputSizeError):
            asyncio.run(guard.awrap_model_call(request, lambda _: self.fail("provider must not run")))

    def test_old_tool_body_is_archived_exactly_with_tool_pairing(self):
        body = "evidence " * 3000
        policy = {"target_tokens": 100, "maximum_tokens": 250_000, "framing_reserve": 0}
        guard = InputBudget(Path("."), policy, "instructions", {})
        message = ToolMessage(content=body, tool_call_id="call-1", id="result-1")
        update = guard.before_model({"messages": [
            HumanMessage(content="job"), AIMessage(content="", tool_calls=[
                {"name": "read_file", "args": {}, "id": "call-1"}]),
            message, ToolMessage(content="latest", tool_call_id="call-2", id="result-2")
        ]}, None)
        self.assertEqual(update["messages"][0].id, "result-1")
        self.assertEqual(update["messages"][0].tool_call_id, "call-1")
        self.assertEqual(next(iter(update["files"].values()))["content"], body)

    def test_virtual_projection_never_mounts_host_or_other_runs(self):
        files = virtual_pages({"source": "same-run supplied evidence"})
        self.assertEqual(list(files), ["/evidence/source/000001.txt"])
        self.assertEqual(files["/evidence/source/000001.txt"], "same-run supplied evidence")
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with patch("ML.deep_research.layer2.ML.agent.create_deep_agent") as create:
                create_stage_agent(run, "design")
            middleware = create.call_args.kwargs["middleware"][0]
            self.assertEqual([t.name for t in middleware.tools], ["ls", "read_file", "glob", "grep"])
            self.assertEqual(type(create.call_args.kwargs["backend"]).__name__, "StateBackend")

    def test_frozen_prompts_own_evidence_and_review_contract(self):
        prompts = {stage: (PROMPTS_DIR / (stage + ".md")).read_text(encoding="utf-8") for stage in STAGES}
        for prompt in prompts.values():
            for text in ["untrusted evidence", "Approved alternative", "Unknown applicability",
                         "private chain-of-thought", "No web research"]:
                self.assertIn(text, prompt)
        self.assertIn("complete cross-boundary fact", prompts["understanding"])
        self.assertIn("ALL initial owners", prompts["assignments"])
        self.assertIn("not only Extra", prompts["assignments"])
        self.assertIn("stable domain_id", prompts["catalogue"])
        self.assertIn("ORIGINAL source", prompts["distribution"])
        self.assertIn("baseline responsibilities only from that plugin", prompts["design"])
        self.assertIn("no implicit industry or fixed roster", prompts["design"])
        self.assertIn("No review observations or final catalogue exist", prompts["design"])
        self.assertIn("final catalogue is settled later", prompts["observations"])
        self.assertIn("all saved observation pages", prompts["catalogue"])
        self.assertIn("do not create or settle domains again", prompts["assignments"])
        self.assertNotIn('"mission":', "".join(prompts.values()))
