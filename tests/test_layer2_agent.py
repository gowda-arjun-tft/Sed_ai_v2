import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ML.deep_research.layer2.ML.context import InputSizeError, estimate, messages, request_options
from ML.deep_research.layer2.ML.harness import build_model
from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.settings import MODULE_DIR, PROMPTS_DIR, PROMPT_FILES
from ML.deep_research.layer2.backend.windows import token_count
from tests.layer2_fixtures import FakeStages, domain_plan, new_run, section


class DirectCallTests(unittest.TestCase):
    def test_native_json_and_web_payload_and_actual_fake_dispatch_match_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            request = messages("Return JSON.", {"evidence": "Offline."})
            with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch(
                "socket.socket.connect", side_effect=AssertionError("network disabled"),
            ):
                model = build_model("high")
                for stage in ("metadata", "design", "distribution"):
                    options = request_options(stage, record)
                    payload = model._get_request_payload(request, **options)
                    self.assertNotIn("max_output_tokens", payload)
                    if stage == "distribution":
                        self.assertEqual(payload["text"]["format"], {"type": "json_object"})
                    if stage == "design":
                        self.assertNotIn("response_format", options)
                        self.assertNotIn("response_format", payload)
                        self.assertNotIn("format", payload.get("text", {}))
                        self.assertEqual(payload["tools"], [{"type": "web_search", "search_context_size": "medium"}])
                        self.assertEqual(payload["tool_choice"], "auto")
                        self.assertEqual(payload["include"], ["web_search_call.action.sources"])
                        self.assertEqual(payload["text"]["verbosity"], "medium")
                    else:
                        self.assertNotIn("tools", payload)
                        if stage == "metadata":
                            self.assertNotIn("text", payload)
            fake = FakeStages()
            fake.run(run)
            record = load_json(run / "run.json")
            for key, options in fake.options:
                expected = request_options(key.split("/")[0], record)
                self.assertEqual(options, expected)
            for stage, request, key in fake.calls:
                self.assertEqual(record["jobs"][key]["input_estimate"],
                                 estimate(request, 8_000, request_options(stage, record)))

    def test_search_controls_are_frozen_and_bound_only_to_designer(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            record["web_search"].update(context_size="high", verbosity="low")
            write_json(run / "run.json", record)
            self.assertEqual(request_options("metadata", record), {})
            self.assertEqual(request_options("distribution", record),
                             {"response_format": {"type": "json_object"}})
            design = request_options("design", record)
            self.assertNotIn("response_format", design)
            self.assertEqual(design["tools"], [{"type": "web_search", "search_context_size": "high"}])
            self.assertEqual(design["text"], {"verbosity": "low"})
            del record["web_search"]["verbosity"]
            self.assertNotIn("text", request_options("design", record))

    def test_designer_web_limit_preserves_oversized_metadata_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.outputs["metadata"] = " x" * 129_000
            with self.assertRaises(InputSizeError):
                fake.run(run)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual((run / "asset_metadata.md").read_text(), fake.outputs["metadata"])
            record = load_json(run / "run.json")
            self.assertEqual(record["jobs"]["design/000001"]["input_ceiling"], 128_000)

    def test_native_web_actions_sources_annotations_and_usage_saved_not_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            actions = [{"type": "web_search_call", "id": "ws-offline", "status": "completed",
                        "action": {"type": "search", "query": "PRIVATE_WEB_QUERY",
                                   "sources": [{"url": "https://example.org/PRIVATE_SOURCE"}]}}]
            fake.outputs["design"] = AIMessage(
                content=domain_plan("Operations", "Ownership"),
                additional_kwargs={"tool_outputs": actions, "annotations": [{"citation": "PRIVATE_CITATION"}]},
                usage_metadata={"input_tokens": 40, "output_tokens": 20, "total_tokens": 60},
                response_metadata={"status": "completed"},
            )
            fake.run(run)
            record = load_json(run / "run.json")
            row = record["jobs"]["design/000001"]
            saved = load_json((run / row["response_path"]).with_name("provider_message.json"))
            self.assertEqual(saved["additional_kwargs"]["tool_outputs"], actions)
            self.assertEqual(saved["usage_metadata"]["total_tokens"], 60)
            self.assertEqual(row["web_search_actions"], 1)
            self.assertEqual(record["usage"]["model_calls"], 3)
            self.assertEqual(record["usage"]["total_tokens"], 90)
            log = (run / "run.log").read_text()
            for private in ("PRIVATE_WEB_QUERY", "PRIVATE_SOURCE", "PRIVATE_CITATION"):
                self.assertNotIn(private, log)
            self.assertIn("designer_web_actions job=design/000001 count=1", log)
            fake.run(run)
            self.assertEqual(len(fake.calls), 3)
            (run / row["response_path"]).unlink()
            fake.fail.add("design")
            fake.run(run)
            failed = load_json(run / "run.json")["jobs"]["design/000001"]
            self.assertNotIn("web_search_actions", failed)
            self.assertIn("designer_web_actions job=design/000001 count=None", (run / "run.log").read_text())

    def test_real_model_builder_has_no_bound_tools_format_or_output_cap(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch(
            "socket.socket.connect", side_effect=AssertionError("network disabled"),
        ):
            model = build_model("high")
            payload = model._get_request_payload([SystemMessage(content="Instructions"), HumanMessage(content="Evidence")])
        self.assertEqual(payload["model"], "gpt-5.6-luna")
        self.assertEqual(payload["reasoning"]["effort"], "high")
        self.assertFalse(payload["store"])
        self.assertEqual(model.max_retries, 3)
        for key in ("tools", "text", "response_format", "max_output_tokens", "previous_response_id"):
            self.assertNotIn(key, payload)

    def test_sequential_carry_forward_and_single_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 22, size=10)
            fake = FakeStages()
            fake.run(run)
            windows = load_json(run / "run.json")["source_windows"]
            self.assertEqual(len(fake.calls), windows * 2 + 1)
            self.assertEqual([s for s, _, _ in fake.calls],
                             ["metadata"] * windows + ["design"] + ["distribution"] * windows)
            cumulative = ""
            for stage, request, _ in fake.calls:
                self.assertEqual(len(request), 2)
                self.assertIsInstance(request[0], SystemMessage)
                self.assertIsInstance(request[1], HumanMessage)
                if stage == "metadata":
                    self.assertEqual(section(request, "previous_metadata"), cumulative)
                    cumulative += section(request, "new_content")
                    self.assertNotIn("<domain_plugin>", request[1].content)
                    self.assertNotIn("<requirements>", request[1].content)
                elif stage == "design":
                    self.assertEqual(section(request, "asset_metadata"), cumulative)
                    self.assertNotIn("<new_content>", request[1].content)
                else:
                    self.assertEqual(section(request, "asset_metadata"), cumulative)
                    self.assertEqual(section(request, "domain_plan"), domain_plan("Operations", "Ownership"))
            self.assertEqual((run / "asset_metadata.md").read_text(), " x" * 22)

    def test_no_sqlite_activity_or_retired_agent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            with patch("sqlite3.connect", side_effect=AssertionError("SQLite is retired in Layer 2")):
                FakeStages().run(run)
            self.assertFalse(list(run.rglob("*.sqlite*")))
            self.assertTrue(list(run.rglob("response.json")))
            for name in ("ML/agent.py", "ML/evidence_backend.py", "backend/evidence.py", "backend/stages.py"):
                self.assertFalse((MODULE_DIR / name).exists())

    def test_actual_plain_messages_accounted_and_exceptional_input_logged(self):
        values = messages("System\n", {"new_content": '"Text"\n医院'})
        self.assertEqual(estimate(values, 200), sum(token_count(m.content) for m in values) + 264)
        self.assertIn('"Text"\n医院', values[1].content)
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            record["context_policy"]["target_tokens"] = 1
            write_json(run / "run.json", record)
            fake = FakeStages()
            fake.run(run)
            record = load_json(run / "run.json")
            for stage, request, key in fake.calls:
                self.assertEqual(record["jobs"][key]["input_estimate"],
                                 estimate(request, 8_000, request_options(stage, record)))
            self.assertIn("reason=complete mandatory context", (run / "run.log").read_text())

    def test_unfit_input_stops_safely_without_dispatch_or_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            record["context_policy"]["maximum_tokens"] = 10
            write_json(run / "run.json", record)
            fake = FakeStages()
            with self.assertRaises(InputSizeError):
                fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertEqual(load_json(run / "run.json")["status"], "failed")
            self.assertTrue((run / "_internal/trace/routing_issues.json").exists())

    def test_provider_capacity_is_separate_from_application_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.model_profile = {"max_input_tokens": 5}
            with self.assertRaises(InputSizeError):
                fake.run(run)
            self.assertFalse(fake.calls)

    def test_prompt_contracts_and_subject_fixtures(self):
        prompts = {k: (PROMPTS_DIR / v).read_text() for k, v in PROMPT_FILES.items()}
        self.assertEqual(set(prompts), {"metadata", "design", "distribution"})
        for word in ("complete updated", "aliases", "counterparties", "uncertainties", "not mandatory headings"):
            self.assertIn(word, prompts["metadata"])
        self.assertNotIn("requirements", prompts["metadata"])
        self.assertNotIn("plugin", prompts["metadata"])
        for word in ("baseline responsibilities", "domain_id", "supplied context", "web_search"):
            self.assertIn(word, prompts["design"])
        for word in ("exceptions", "responsible party", "overlap-only", "multi-domain", "scope"):
            self.assertIn(word, prompts["distribution"])
        for word in ("no quota", "positive research responsibilities", "Stop once", "Search may be unnecessary"):
            self.assertIn(word, prompts["design"])
        for word in ("notice periods", "genuinely identical", "no relevant new content", "domain IDs",
                     "complete research-relevant meanings", "separate consequences", "cost basis",
                     "comparable subject, party, scope and time", "return no intermediate inventory",
                     "entry-count or word limit", "Shared identity/context need not be repeated",
                     "Rule with two consequences", "Whole versus component estimate"):
            self.assertIn(word, prompts["distribution"])
        plugin = (MODULE_DIR / "plugins/real_estate.md").read_text()
        requirements = (MODULE_DIR.parents[2] / "inputs/requirement.md").read_text()
        self.assertNotIn("## Exclusions", requirements)
        self.assertNotIn("## Deferred to a later round", requirements)
        for word in ("valuation", "ESG", "CapEx", "employment", "interest rates"):
            self.assertIn(word.casefold(), plugin.casefold())
            self.assertIn(word.casefold(), requirements.casefold())
        for label, content in {
            "property": "Clinic A in Bonn; solar system proposed, not installed.",
            "stock": "Issuer A, ordinary shares; manufacturing in France.",
            "bond": "Issuer B, EUR bond due 2030; secured repayment structure.",
            "insurance": "Insurer C covers the vessel for 2026, excluding war damage.",
            "mixed": "Issuer owns Clinic A; portfolio also holds Bond B. Separate subjects.",
        }.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp), text=content, plugin=f"# {label} research\nScope of {label}.")
                fake = FakeStages()
                fake.run(run)
                design = next(request for stage, request, _ in fake.calls if stage == "design")
                self.assertEqual(section(design, "asset_metadata"), content)
                self.assertEqual(section(design, "domain_plugin"), f"# {label} research\nScope of {label}.")

    def test_provider_incomplete_text_is_saved_not_used_as_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.outputs["metadata"] = AIMessage(content="Received partial text", response_metadata={"status": "incomplete"})
            fake.run(run)
            record = load_json(run / "run.json")
            row = record["jobs"]["metadata/000001"]
            self.assertEqual((run / row["response_path"]).read_text(), "Received partial text")
            self.assertEqual(row["error_type"], "IncompleteResponseError")
            self.assertEqual(len(fake.calls), 1)

    def test_large_completed_metadata_is_retained_when_next_input_cannot_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 11, size=10)
            record = load_json(run / "run.json")
            record["context_policy"]["maximum_tokens"] = 10_000
            write_json(run / "run.json", record)
            fake = FakeStages()
            fake.outputs["metadata/000001"] = " x" * 12_000
            with self.assertRaises(InputSizeError):
                fake.run(run)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual((run / "asset_metadata.md").read_text(), " x" * 12_000)
            self.assertIn("workflow_incomplete", (run / "_internal/trace/routing_issues.json").read_text())
