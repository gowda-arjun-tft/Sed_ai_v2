"""Native request, attribution, source prompt and operational-only failure checks."""

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import BadRequestError

from ML.deep_research.layer2.ML.context import estimate
from ML.deep_research.layer2.ML.harness import build_model
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer3.pipeline.create_run import local_path
from ML.deep_research.layer3.source_finder import prepare, request_options
from ML.deep_research.layer3.settings import PROMPTS_DIR, SOURCE_SUGGESTION_PATH
from tests.layer3_fixtures import FakeFinder, new_run, snapshot


class SourceRequestTests(unittest.TestCase):
    def test_real_native_payload_requires_search_without_output_schema_or_cap(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ", {"OPENAI_API_KEY": "offline-test"}
        ), patch("socket.socket.connect", side_effect=AssertionError("No network")):
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            model = build_model("high")
            request, _, count, ceiling = prepare(run, record, record["domains"][0], model.profile)
            options = request_options(record)
            payload = model._get_request_payload(request, **options)
            self.assertEqual(payload["model"], "gpt-5.6-luna")
            self.assertEqual(payload["reasoning"]["effort"], "high")
            self.assertEqual(payload["tool_choice"], {"type": "web_search"})
            self.assertEqual(payload["tools"], [{"type": "web_search", "search_context_size": "medium",
                                                "external_web_access": True}])
            self.assertEqual(payload["text"], {"verbosity": "low"})
            self.assertFalse(payload["store"])
            self.assertNotIn("response_format", payload)
            self.assertNotIn("max_output_tokens", payload)
            self.assertEqual(count, estimate(request, 8000, options))
            self.assertEqual(ceiling, 128_000)
            _, _, _, small = prepare(run, record, record["domains"][0], {"max_input_tokens": 50})
            self.assertEqual(small, 50)

    def test_snapshot_prompt_requires_access_attempts_and_guidance_is_generic(self):
        prompt = (PROMPTS_DIR / "source_finder.md").read_text(encoding="utf-8")
        for text in ("attempt to open every proposed URL", "snippet", "exact document URL",
                     "readable", "partial", "blocked", "failed", "null", "not private",
                     "not instructions", "empty sources list"):
            self.assertIn(text, prompt)
        guide = SOURCE_SUGGESTION_PATH.read_text(encoding="utf-8")
        for text in ("municipal/local", "state/regional", "national", "company",
                     "central banks", "local language", "secondary", "not automatically"):
            self.assertIn(text, guide)
        self.assertNotIn("Bad Homburg", guide)
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            self.assertEqual((run / "_internal/inputs/prompts/source_finder.md").read_text(encoding="utf-8"),
                             prompt)

    def test_input_and_option_versions_change_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            first = prepare(run, record, record["domains"][0], {})[1]
            record["web_search"]["verbosity"] = "high"
            second = prepare(run, record, record["domains"][0], {})[1]
            self.assertNotEqual(first, second)
            self.assertNotEqual(second, prepare(run, record, record["domains"][1], {})[1])


class SourceTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_actions_and_usage_are_saved_while_logs_exclude_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            record = await fake.run(run)
            self.assertEqual(record["usage"]["model_calls"], 2)
            self.assertEqual(record["usage"]["input_tokens"], 200)
            for entry in record["jobs"].values():
                trace = load_json(local_path(run, entry["response_path"]).with_name("provider_message.json"))
                self.assertEqual(trace["additional_kwargs"]["tool_outputs"][0]["action"]["type"], "open_page")
                self.assertEqual(entry["web_actions"], {"open_page": 1})
            text = (run / "run.log").read_text(encoding="utf-8")
            for event in ("job_dispatched", "queued_seconds", "response_saved", "publication_finished", "run_finished"):
                self.assertIn(event, text)
            for private in ("https://", "PRIVATE", "医院", "Official municipal"):
                self.assertNotIn(private, text)
            await fake.run(run)
            self.assertEqual(load_json(run / "run.json")["usage"]["model_calls"], 2)

    async def test_completed_response_is_saved_while_other_jobs_are_outstanding(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            hold = asyncio.Event()
            fake.hold = {"source_finder/000002": hold}
            task = asyncio.create_task(fake.run(run))
            try:
                for _ in range(150):
                    record = load_json(run / "run.json")
                    entry = record["jobs"].get("source_finder/000001", {})
                    if entry.get("status") == "complete":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(entry["status"], "complete")
                self.assertTrue(local_path(run, entry["response_path"]).is_file())
                self.assertFalse(task.done())
            finally:
                hold.set()
                await task

    async def test_http_error_has_safe_identifiers_and_traceback_without_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            original = fake.ainvoke
            async def fail(request, config, **kwargs):
                if config["metadata"]["lc_agent_name"].endswith("1"):
                    response = httpx.Response(400, headers={"x-request-id": "req-safe"},
                                              request=httpx.Request("POST", "https://example.test"))
                    raise BadRequestError("PRIVATE_ERROR_BODY", response=response,
                                          body={"code": "invalid_request_error", "param": "tools",
                                                "message": "PRIVATE_ERROR_BODY"})
                return await original(request, config, **kwargs)
            with patch.object(fake, "ainvoke", side_effect=fail):
                await fake.run(run)
            text = (run / "run.log").read_text(encoding="utf-8")
            for value in ("400", "invalid_request_error", "req-safe", "frames="):
                self.assertIn(value, text)
            self.assertNotIn("PRIVATE_ERROR_BODY", text)

    async def test_progress_task_and_logging_handlers_are_cleaned_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            fake.delays = {f"source_finder/{i:06d}": 0.02 for i in (1, 2)}
            stopped = asyncio.Event()
            async def progress(logger, stage, pending, starts, started):
                try:
                    logger.info("waiting_for_provider stage=%s pending=%s", stage, sorted(pending))
                    await asyncio.Event().wait()
                finally:
                    stopped.set()
            with patch("ML.deep_research.layer3.source_runner.waiting_progress", side_effect=progress):
                await fake.run(run)
            self.assertTrue(stopped.is_set())
            self.assertIn("waiting_for_provider", (run / "run.log").read_text(encoding="utf-8"))
            logger = logging.getLogger(f"cdi.layer2.{(run / 'run.log').resolve()}")
            self.assertEqual(logger.handlers, [])
