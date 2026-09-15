"""Every native request path uses selected frozen settings without live provider traffic."""

import json
import inspect
import httpx
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from ML.deep_research.domain_decider.ML.context import request_options
from ML.deep_research.domain_decider.ML.harness import build_model
from ML.deep_research.domain_decider.backend.fs import load_json
from ML.deep_research.domain_decider.backend.stage_settings import STAGES, generation_options, resolve_stage_settings, read_stage_settings
from ML.deep_research.research_module.ML.source_finder import request_options as source_options
from tests.layer2_fixtures import new_run
from ML.deep_research.domain_decider.backend.cli import main as domain_cli
from ML.deep_research.research_module.backend.cli import main as research_cli


class SDKDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_invocation_reaches_mock_http_transport(self):
        """Exercise the real async SDK boundary that rejected duplicate reasoning options."""
        requests = []

        def respond(request):
            """Capture only synthetic input and return a minimal provider response."""
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_offline", "object": "response", "created_at": 0,
                "model": "gpt-5.6-luna", "status": "completed", "error": None,
                "incomplete_details": None, "parallel_tool_calls": True,
                "tool_choice": "auto", "tools": [],
                "output": [{"type": "message", "id": "msg_offline", "status": "completed",
                            "role": "assistant", "content": [{"type": "output_text",
                            "text": "Offline metadata", "annotations": []}]}]})

        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), patch(
                "socket.socket.connect", side_effect=AssertionError("network")):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                model = build_model("high", http_async_client=client, max_retries=0)
                options = generation_options({"stage_settings": resolve_stage_settings()}, "metadata")
                result = await model.bind(**options).ainvoke([HumanMessage(content="Offline")])
                self.assertEqual(result.text, "Offline metadata")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["reasoning"], {"effort": "high", "summary": "auto"})
        self.assertNotIn("reasoning_effort", requests[0])


class StageSettingsTests(unittest.TestCase):
    def test_all_eight_requests_serialize_selected_options(self):
        """Inspect the installed adapter's actual wire payload, including search/JSON incompatibility."""
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), patch(
            "socket.socket.connect", side_effect=AssertionError("network")):
            run = new_run(Path(directory))
            record = load_json(run / "run.json")
            selected = {stage: {"reasoning": "max", "verbosity": "high"} for stage in STAGES}
            selected["summary"] = {"reasoning": "medium", "verbosity": "low"}
            selected["research_search"]["search_context"] = "high"
            record["stage_settings"] = resolve_stage_settings(selected)
            model = build_model("low")
            for stage in STAGES:
                options = (request_options(stage, record) if stage in {"metadata", "design", "distribution"}
                           else source_options(record, stage) if stage in {"source_discovery", "research_search"}
                           else generation_options(record, stage))
                payload = model._get_request_payload([HumanMessage(content="Offline input")], **options)
                inspect.signature(model.root_async_client.responses.create).bind(**payload)
                self.assertNotIn("reasoning_effort", payload)
                self.assertEqual(payload["reasoning"]["effort"], selected[stage]["reasoning"])
                self.assertEqual(payload["reasoning"]["summary"], "auto")
                self.assertEqual(payload["text"]["verbosity"], selected[stage]["verbosity"])
                self.assertNotIn("max_output_tokens", payload)
                if stage in {"design", "source_discovery", "research_search"}:
                    self.assertNotIn("format", payload["text"])
                else:
                    self.assertNotIn("tools", payload)
                if stage == "distribution":
                    self.assertEqual(payload["text"]["format"], {"type": "json_object"})

    def test_builder_preserves_legacy_effort_and_constructor_override(self):
        """Both historical defaults and agent constructor overrides produce valid SDK arguments."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}):
            for overrides, expected in (({}, {"effort": "max"}),
                                        ({"reasoning": {"effort": "medium", "summary": "auto"}},
                                         {"effort": "medium", "summary": "auto"})):
                model = build_model("max", **overrides)
                payload = model._get_request_payload([HumanMessage(content="Offline")])
                inspect.signature(model.root_async_client.responses.create).bind(**payload)
                self.assertEqual(payload["reasoning"], expected)
                self.assertNotIn("reasoning_effort", payload)

    def test_validation_legacy_override_and_summary_toggle(self):
        """Operational values fail explicitly; absent historical policy changes no old options."""
        resolved = resolve_stage_settings({"research": {"reasoning": "low"}, "reasoning_summaries": False},
                                          legacy={"research": {"reasoning": "max"}})
        options = generation_options({"stage_settings": resolved}, "research")
        self.assertEqual(options["reasoning"], {"effort": "low"})
        self.assertEqual(generation_options({}, "research"), {})
        for value in ({"unknown": {}}, {"summary": {"search_context": "high"}},
                      {"metadata": {"reasoning": True}}, {"reasoning_summaries": "true"}):
            with self.assertRaises(ValueError):
                resolve_stage_settings(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"research": {}, "research": {}}')
            with self.assertRaises(ValueError):
                read_stage_settings(path)

    def test_cli_settings_do_not_override_resume_or_mix_legacy_flags(self):
        """Reject creation controls before inspecting any selected historical run."""
        from contextlib import redirect_stderr
        from io import StringIO
        cases = [(domain_cli, ["--resume", "missing", "--stage-settings", "settings.json"]),
                 (domain_cli, ["missing", "--stage-settings", "settings.json", "--web-search-depth", "high"])]
        cases += [(research_cli, [flag, "missing", "--stage-settings", "settings.json"])
                  for flag in ("--resume-l3", "--check-only", "--upload-documents")]
        cases.append((research_cli, ["--research", "missing", "--stage-settings", "settings.json",
                                     "--web-search-depth", "high"]))
        with patch("socket.socket.connect", side_effect=AssertionError("network")), redirect_stderr(StringIO()):
            for main, args in cases:
                with self.assertRaises(SystemExit) as result:
                    main(args)
                self.assertEqual(result.exception.code, 2)
