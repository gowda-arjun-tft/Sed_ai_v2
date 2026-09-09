import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain.agents.structured_output import ProviderStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from ML.deep_research.layer2.ML.agent import Layer2Response, create_stage_agent, response_value
from ML.deep_research.layer2.ML.context import InputBudget, InputSizeError, estimate
from ML.deep_research.layer2.ML.harness import build_model
from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.ML.evidence_backend import EvidenceBackend
from ML.deep_research.layer2.backend.settings import STAGES, PROMPTS_DIR, PROMPT_FILES
from tests.layer2_fixtures import FakeStages, new_run


class HarnessTests(unittest.TestCase):
    def test_actual_native_graph_tool_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            for stage in STAGES:
                graph = create_stage_agent(run, stage)
                bound = graph.nodes["tools"].bound if "tools" in graph.nodes else None
                tools = set(getattr(bound, "tools_by_name", getattr(bound, "_tools_by_name", {})))
                expected = set() if stage in {"understanding", "design", "distribution"} else {"ls", "glob", "grep", "read_file"}
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
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            guard = InputBudget(run, policy, "instructions", {})
            messages = [HumanMessage(content="job", id="input"),
                        AIMessage(content="", id="a1", tool_calls=[
                            {"name": "read_file", "args": {}, "id": "call-1"}]),
                        ToolMessage(content=body, tool_call_id="call-1", id="result-1"),
                        AIMessage(content="", id="a2", tool_calls=[
                            {"name": "read_file", "args": {}, "id": "call-2"}]),
                        ToolMessage(content="latest", tool_call_id="call-2", id="result-2")]
            with patch("ML.deep_research.layer2.ML.context.get_config", return_value={"configurable": {"thread_id": "test"}}):
                update = guard.before_model({"messages": messages}, None)
            self.assertEqual([m.id for m in update["messages"][:-1]], ["a1", "result-1"])
            import json
            archived = next((run / "_internal/trace/history").rglob("*.json"))
            self.assertEqual(json.loads(archived.read_text(encoding="utf-8")), [m.model_dump(mode="json") for m in messages[1:3]])
            backend = EvidenceBackend(run, history=True, thread="test")
            self.assertTrue(backend.ls("/").entries)
            self.assertIn(body, "".join(text for _, text in backend.documents()))
            self.assertEqual(list(EvidenceBackend(run, history=True, thread="other").documents()), [])

    def test_virtual_projection_never_mounts_host_or_other_runs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            run = new_run(Path(tmp))
            with patch("ML.deep_research.layer2.ML.agent.create_deep_agent") as create:
                create_stage_agent(run, "observations")
            middleware = create.call_args.kwargs["middleware"][0]
            self.assertEqual([t.name for t in middleware.tools], ["ls", "read_file", "glob", "grep"])
            self.assertEqual(type(create.call_args.kwargs["backend"]).__name__, "CompositeBackend")

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
        self.assertIn("all scheduled observation groups", prompts["catalogue"])
        self.assertIn("do not create or settle domains again", prompts["assignments"].lower())
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
            self.assertIn("definition", prompts[stage])
            self.assertIn("page", prompts[stage])
        for text in ("concise factual wording", "every unique detail", "alternative figures",
                     "not exclusively in source", "Do not return separate means or applicability fields",
                     "qualifications within fact", "complete fact when new_content"):
            self.assertIn(text, prompts["distribution"])
        self.assertNotIn('"means":', prompts["distribution"])
        self.assertNotIn('"applicability":', prompts["distribution"])
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
                for stage in ("understanding", "design", "catalogue", "distribution"):
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

    def test_read_facts_groups_detail_with_four_prompt_owned_fields(self):
        prompt = (PROMPTS_DIR / PROMPT_FILES["understanding"]).read_text(encoding="utf-8")
        example = json.loads(next(line for line in prompt.splitlines() if line.startswith('{"profile":')))
        self.assertEqual(set(example), {"profile", "evidence"})
        self.assertEqual(set(example["evidence"][0]), {"fact", "relationships", "contradictions", "source"})
        self.assertEqual(example["evidence"][0]["source"], ["91cb80fc", "aa1760d4"])
        for instruction in (
            "same subject and topic", "Keep unrelated subjects separate",
            "Reduce repeated structure, not factual detail", "do not target an entry count or word limit",
            "respective periods, scopes or versions", "not a separate applicability field",
            "add information beyond fact", "otherwise []", "without resolving them",
            "do not automatically constitute contradictions", "copied exactly as a list",
            "Use [] when none are supplied", "Never invent IDs", "only if present in the source",
            "filenames, source-window references, offsets or commentary",
            "within these four fields", "substantive document dates and references",
        ):
            self.assertIn(instruction, prompt)
        self.assertNotIn("source locators", prompt)
        self.assertNotIn("Explain decisions", prompt)

    def test_understanding_values_reach_storage_and_design_without_repair(self):
        grouped = {
            "profile": "Bâtiment A: historical records; annex proposed.",
            "evidence": [{
                "fact": "Bâtiment A measured 1,200 m² in 2006; another 2006 record says 1,250 m². "
                        "A 50 m² annex was proposed in 2025; installation is unconfirmed.",
                "relationships": ["The annex proposal identifies Bâtiment A as its host building."],
                "contradictions": ["The two 2006 records disagree on area; the cause is unresolved."],
                "source": ["91cb80fc", "aa1760d4"],
            }, {"fact": "Ownership is unconfirmed.", "relationships": [],
                "contradictions": [], "source": []}],
        }
        for response in (grouped, {}, {"unexpected": {"values": [None, "漢字", 17]}}):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                run, fake = new_run(Path(tmp)), FakeStages()
                original_factory = fake.factory

                def factory(path, stage, checkpointer=None):
                    graph = original_factory(path, stage, checkpointer)
                    if stage != "understanding":
                        return graph

                    async def invoke(value, config):
                        await graph.ainvoke(value, config)
                        return {"structured_response": Layer2Response(root=response)}

                    return RunnableLambda(invoke)

                with patch.object(fake, "factory", side_effect=factory):
                    fake.run(run)
                    before = len(fake.calls)
                    fake.run(run)
                self.assertEqual(len(fake.calls), before)
                self.assertEqual(sum(stage == "understanding" for stage, _, _ in fake.calls), 1)
                raw = next((run / "_internal/trace/responses/understanding").rglob("response.json"))
                self.assertEqual(json.loads(raw.read_text(encoding="utf-8")), response)
                stored = list(EvidenceStore(run).rows("understanding"))
                self.assertEqual([row["value"] for row in stored], [response])
                design = next(data for stage, data, _ in fake.calls if stage == "design")
                self.assertEqual([row["value"] for row in design["subject"]], [response])
                record = json.loads((run / "run.json").read_text(encoding="utf-8"))
                self.assertEqual(record["status"], "complete")
                self.assertTrue(all(job["attempt"] == 1 for job in record["jobs"].values()))
