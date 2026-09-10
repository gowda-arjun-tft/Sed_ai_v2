import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from openai import BadRequestError

from ML.deep_research.layer2.ML.context import request_options
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.run_log import (
    DispatchLog, log_failure, operational_logger, stop_progress, waiting_progress,
)

from tests.layer2_fixtures import FakeStages, new_run


class LoggingTests(unittest.TestCase):
    def test_api_rejection_diagnostics_and_four_metadata_responses_reused_after_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 34, size=10)
            fake = FakeStages()
            error = BadRequestError("PRIVATE_EXCEPTION_PAYLOAD", response=httpx.Response(
                400, request=httpx.Request("POST", "https://example.org/PRIVATE_URL"),
                headers={"x-request-id": "req_offline", "authorization": "PRIVATE_CREDENTIAL"}),
                body={"message": "Web Search cannot be used with JSON mode.",
                      "code": "invalid_request_error", "param": "response_format",
                      "input": "PRIVATE_SOURCE_SENTINEL"})

            def fail_design(messages, job):
                if job == "design/000001":
                    raise error

            def old_options(stage, record):
                options = request_options(stage, record)
                if stage == "design":
                    options["response_format"] = {"type": "json_object"}
                return options

            fake.on_call = fail_design
            with patch("ML.deep_research.layer2.backend.jobs.request_options", side_effect=old_options):
                fake.run(run)
            before = load_json(run / "run.json")
            self.assertEqual(before["source_windows"], 4)
            self.assertEqual(before["status"], "failed")
            self.assertEqual(len(fake.calls), 5)
            preserved = {p: p.read_bytes() for p in (run / "_internal/inputs").rglob("*") if p.is_file()}
            for job in before["jobs"].values():
                if job["stage"] == "metadata":
                    path = run / job["response_path"]
                    preserved[path] = path.read_bytes()
            log = (run / "run.log").read_text()
            for expected in ("http_status': 400", "invalid_request_error", "response_format",
                             "req_offline", "web_search_incompatible_with_json_mode", "frames="):
                self.assertIn(expected, log)
            for private in ("PRIVATE_EXCEPTION_PAYLOAD", "PRIVATE_URL", "PRIVATE_CREDENTIAL",
                            "PRIVATE_SOURCE_SENTINEL"):
                self.assertNotIn(private, log)
            fake.on_call = None
            fake.run(run)
            after = load_json(run / "run.json")
            self.assertEqual([stage for stage, _, _ in fake.calls[5:]], ["design"] + ["distribution"] * 4)
            self.assertEqual(after["status"], "complete")
            self.assertEqual(after["usage"]["model_calls"], 9)
            self.assertNotEqual(before["jobs"]["design/000001"]["fingerprint"],
                                after["jobs"]["design/000001"]["fingerprint"])
            for key, job in before["jobs"].items():
                if job["stage"] == "metadata":
                    self.assertEqual(job["fingerprint"], after["jobs"][key]["fingerprint"])
                    self.assertEqual(after["jobs"][key]["attempt"], 1)
            for path, original in preserved.items():
                self.assertEqual(path.read_bytes(), original)
            self.assertTrue((run / "domains/operations.md").is_file())

    def test_unknown_api_error_payload_and_unsafe_identifiers_are_not_logged(self):
        error = BadRequestError("PRIVATE_MESSAGE", response=httpx.Response(
            400, request=httpx.Request("POST", "https://example.org"),
            headers={"x-request-id": "sk-PRIVATE_SECRET"}),
            body={"message": "PRIVATE_BODY", "code": "PRIVATE CODE\nINJECTION",
                  "param": {"fact": "PRIVATE_FACT"}})
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            with operational_logger(run) as logger:
                log_failure(logger, "job_failed", error)
            log = (run / "run.log").read_text()
            self.assertIn("http_status': 400", log)
            self.assertIn("[redacted]", log)
            self.assertNotIn("PRIVATE", log)
            self.assertNotIn("web_search_incompatible_with_json_mode", log)

    def test_one_append_only_log_no_evidence_or_duplicate_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text="PRIVATE_SOURCE_SENTINEL")
            fake = FakeStages()
            fake.run(run)
            first = (run / "run.log").read_text(encoding="utf-8")
            fake.run(run)
            second = (run / "run.log").read_text(encoding="utf-8")
            self.assertTrue(second.startswith(first))
            self.assertEqual(second.count("run_started"), 1)
            self.assertEqual(second.count("run_resumed"), 1)
            self.assertNotIn("PRIVATE_SOURCE_SENTINEL", second)
            self.assertNotIn("offline-test", second)
            self.assertIn("job_complete", second)
            self.assertIn("frozen_policy", second)

    def test_safe_error_frames_and_direct_usage_attribution(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text="PRIVATE_SOURCE_SENTINEL")
            fake = FakeStages()
            fake.fail.add("distribution")
            fake.run(run)
            log = (run / "run.log").read_text()
            for private in ("PRIVATE_EXCEPTION_PAYLOAD", "PRIVATE_SOURCE_SENTINEL", "offline-test"):
                self.assertNotIn(private, log)
            for value in ("ConnectionError", "frames=", "request_id=", "attempt=", "elapsed=", "stage=distribution"):
                self.assertIn(value, log)
            record = load_json(run / "run.json")
            rows = [json.loads(s) for s in (run / "_internal/trace/usage.jsonl").read_text().splitlines()]
            self.assertEqual({row["actor"] for row in rows}, {"layer2-metadata", "layer2-design"})
            self.assertEqual(record["usage"]["model_calls"], 2)
            self.assertEqual(record["usage"]["total_tokens"], 30)

    def test_stage_dispatch_publication_and_reuse_timings_without_new_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            log = (run / "run.log").read_text()
            for stage in ("metadata", "design", "distribution"):
                self.assertIn(f"stage_started stage={stage}", log)
                self.assertIn(f"stage_finished stage={stage} completed=1 reused=0 failed=0 outstanding=0", log)
                self.assertIn(f"job_dispatched stage={stage}", log)
                self.assertIn(f"response_saved stage={stage}", log)
            for event in ("queued_seconds=", "dispatch_to_handled_seconds=", "publication_finished wall_seconds=",
                          "observed_transport_attempts=unavailable", "expected_jobs=3 reused_jobs=0 wall_seconds="):
                self.assertIn(event, log)
            fake.run(run)
            later = (run / "run.log").read_text()[len(log):]
            self.assertNotIn("job_dispatched", later)
            self.assertEqual(later.count("completed=1 reused=1 failed=0"), 3)
            self.assertEqual(len(fake.calls), 3)
            self.assertFalse(logging.getLogger(f"cdi.layer2.{(run / 'run.log').resolve()}").handlers)

    def test_native_dispatch_callback_counts_only_queue_time_and_ignores_payload(self):
        logger, starts = Mock(), {}
        callback = DispatchLog(logger, "design", "design/000001", 10, starts)
        with patch("ML.deep_research.layer2.backend.run_log.time.perf_counter", return_value=12):
            callback.on_chat_model_start({"secret": "PRIVATE"}, ["PRIVATE"])
        self.assertEqual(starts, {"design/000001": 12})
        self.assertEqual(logger.info.call_args.args[-1], 2)
        self.assertNotIn("PRIVATE", str(logger.info.call_args))

    def test_waiting_heartbeat_interval_and_cancellation_are_deterministic(self):
        async def exercise():
            logger, entered = Mock(), asyncio.Event()
            waits = []
            async def controlled_sleep(delay):
                waits.append(delay)
                if len(waits) > 1:
                    entered.set()
                    await asyncio.Future()
            with patch("ML.deep_research.layer2.backend.run_log.asyncio.sleep", side_effect=controlled_sleep):
                task = asyncio.create_task(waiting_progress(logger, "distribution", {"a", "b"}, {"a": 12}, 10))
                await entered.wait()
                await stop_progress(task)
            self.assertEqual(waits, [30, 30])
            self.assertTrue(task.cancelled())
            self.assertEqual(logger.info.call_count, 1)
            self.assertEqual(logger.info.call_args.args[2:4], (["a"], ["b"]))
        asyncio.run(exercise())

    def test_progress_task_is_joined_on_success_failure_and_cancelled_call(self):
        from ML.deep_research.layer2.backend.jobs import run_jobs
        from tests.layer2_fixtures import OfflineModel

        async def exercise(run, outcome):
            captured = []
            async def watch(*args):
                captured.append(asyncio.current_task())
                await asyncio.Future()
            fake = FakeStages()
            fake.delay = .001
            if outcome == "failure":
                fake.fail.add("metadata")
            if outcome == "cancel":
                def cancel_call(*args):
                    raise asyncio.CancelledError()
                fake.on_call = cancel_call
            with operational_logger(run) as logger, patch(
                "ML.deep_research.layer2.backend.jobs.waiting_progress", side_effect=watch
            ):
                try:
                    await run_jobs(run, OfflineModel(owner=fake), "metadata", [{"previous_metadata": "", "new_content": "X"}], {}, logger)
                except asyncio.CancelledError:
                    self.assertEqual(outcome, "cancel")
            self.assertEqual(len(captured), 1)
            self.assertTrue(captured[0].done())
        for outcome in ("success", "failure", "cancel"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                asyncio.run(exercise(new_run(Path(tmp)), outcome))
