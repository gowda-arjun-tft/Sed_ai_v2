import asyncio
import shutil
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
from ML.deep_research.layer2.backend.settings import STAGES, PROMPTS_DIR, PROMPT_FILES
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
        prompts = {stage: (PROMPTS_DIR / PROMPT_FILES[stage]).read_text(encoding="utf-8") for stage in STAGES}
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
        self.assertIn("Put unique factual detail in evidence", prompts["understanding"])
        self.assertIn("not replace evidence extraction", prompts["understanding"])
        self.assertIn('Return {"observations": []}', prompts["observations"])
        self.assertIn("Inspect every supplied fact", prompts["observations"])
        self.assertIn("Do not restate correct unchanged placements", prompts["observations"])
        self.assertIn("one explicit entry for every supplied fact", prompts["assignments"])
        self.assertIn("reason only for changed, disputed or unresolved", prompts["assignments"])
        self.assertIn("initial_assignment for comparison", prompts["assignments"])
        self.assertIn("Do not repeat fact bodies", prompts["assignments"])
        for stage in ("observations", "assignments"):
            self.assertIn("when supplied inline; otherwise read all", prompts[stage])
        for text in ("concise factual wording", "every unique detail", "alternative figures",
                     "not exclusively in source", "means only for additional supported interpretation",
                     "return an empty string", "complete fact when new_content"):
            self.assertIn(text, prompts["distribution"])
        for stage in ("design", "catalogue"):
            self.assertIn("concise research duties and boundaries", prompts[stage])
            self.assertIn("Do not repeat asset inventories", prompts[stage])
            self.assertIn("reason and evidence_refs", prompts[stage])

    def test_prompt_changes_only_reach_new_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompts = root / "prompts"
            shutil.copytree(PROMPTS_DIR, prompts)
            with patch("ML.deep_research.layer2.backend.create_run.PROMPTS_DIR", prompts):
                old = new_run(root)
                snapshots = {name: (old / "_internal/inputs/prompts" / (name + ".md")).read_bytes()
                             for name in STAGES}
                old_metadata = (old / "run.json").read_bytes()
                for stage in ("design", "catalogue", "distribution"):
                    path = prompts / PROMPT_FILES[stage]
                    path.write_text(path.read_text(encoding="utf-8") + "\nNew test revision.\n", encoding="utf-8")
                new = new_run(root)
            self.assertEqual((old / "run.json").read_bytes(), old_metadata)
            from ML.deep_research.layer2.backend.fs import load_json, sha256
            metadata = load_json(new / "run.json")
            for stage in STAGES:
                name = "prompts/" + stage + ".md"
                self.assertEqual((old / "_internal/inputs" / name).read_bytes(), snapshots[stage])
                fresh = new / "_internal/inputs" / name
                self.assertEqual(fresh.read_bytes(), (prompts / PROMPT_FILES[stage]).read_bytes())
                self.assertEqual(metadata["inputs"][name]["sha256"], sha256(fresh))
