"""Real source runner with offline native-Runnable calls and failure/resume scenarios."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer3.pipeline.create_run import local_path
from ML.deep_research.layer3.source_publication import publish
from tests.layer3_fixtures import FakeFinder, new_run, snapshot, source_json


class SourceRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_domain_receives_three_complete_inputs_with_bounded_parallelism(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), [f"domain-{i}" for i in range(11)])
            before = snapshot(run / "_internal/inputs")
            fake = FakeFinder()
            fake.delays["source_finder/000001"] = 0.04
            record = await fake.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(fake.peak, 5)
            self.assertEqual(len(fake.calls), 11)
            self.assertNotEqual(fake.finished[0], "source_finder/000001")
            self.assertEqual(before, snapshot(run / "_internal/inputs"))
            by_key = {d["key"]: d for d in record["domains"]}
            for key, request, options in fake.calls:
                self.assertEqual(len(request), 2)
                for label in ("source_suggestions", "asset_metadata", "domain_context"):
                    self.assertIn(f"<{label}>", request[1].content)
                self.assertIn(local_path(run, by_key[key]["input_path"]).read_text(encoding="utf-8"), request[1].content)
                published = local_path(run, by_key[key]["output_path"]).read_text(encoding="utf-8")
                self.assertEqual(json.loads(published), json.loads(source_json()))
                self.assertIn('\n  "sources": [\n', published)
                self.assertEqual(options["tool_choice"], {"type": "web_search"})
            self.assertFalse((run / "research").exists())
            self.assertFalse(list(run.rglob("*.sqlite*")))

    async def test_failure_saves_siblings_and_retry_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["a", "b", "c"])
            fake = FakeFinder()
            key = "source_finder/000002"
            fake.failures.add(key)
            record = await fake.run(run)
            self.assertEqual(record["status"], "partial")
            self.assertEqual(record["publication"]["published_sources"], 2)
            await fake.run(run)
            self.assertEqual(len(fake.calls), 3)
            fake.failures.clear()
            record = await fake.run(run, retry_failed=True)
            self.assertEqual(len(fake.calls), 4)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["jobs"][key]["attempt"], 2)
            self.assertNotIn("PRIVATE_URL", (run / "run.log").read_text(encoding="utf-8"))
            self.assertIn("TimeoutError", (run / "run.log").read_text(encoding="utf-8"))

    async def test_unconventional_json_and_duplicates_are_preserved_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["a", "b", "c", "d"])
            fake = FakeFinder()
            for index, raw in enumerate(['{"sources":[],"sources":[{"医院":null}]}', "{}", "", "not JSON"], 1):
                fake.outputs[f"source_finder/{index:06d}"] = raw
            record = await fake.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["publication"]["published_sources"], 2)
            first = record["domains"][0]
            visible = local_path(run, first["output_path"]).read_text(encoding="utf-8")
            self.assertIn('\n  "sources": [],\n  "sources": [\n', visible)
            self.assertEqual(visible.count('"sources"'), 2)
            for key, raw in fake.outputs.items():
                self.assertEqual(local_path(run, record["jobs"][key]["response_path"]).read_text(encoding="utf-8"), raw)
            await fake.run(run, retry_failed=True)
            self.assertEqual(len(fake.calls), 4)

    async def test_oversized_domain_preserves_successful_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            from ML.deep_research.layer3.source_runner import prepare
            def oversized(run, record, domain, profile):
                request, fingerprint, count, ceiling = prepare(run, record, domain, profile)
                return request, fingerprint, ceiling + 1 if domain["key"].endswith("1") else count, ceiling
            with patch("ML.deep_research.layer3.source_runner.prepare", side_effect=oversized):
                record = await fake.run(run)
            self.assertEqual(record["status"], "partial")
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(record["jobs"]["source_finder/000001"]["error_type"], "InputSizeError")

    async def test_completed_response_recovered_after_run_record_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            record = await fake.run(run)
            record["jobs"] = {}
            write_json(run / "run.json", record)
            record = await fake.run(run)
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(record["status"], "complete")
            self.assertTrue(all(j["reused"] for j in record["jobs"].values()))

    async def test_frozen_input_tampering_rejected_before_log_or_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            path = run / "_internal/inputs/asset_metadata.md"
            path.write_text("Changed")
            before = snapshot(run)
            fake = FakeFinder()
            with self.assertRaisesRegex(ValueError, "Frozen"):
                await fake.run(run)
            self.assertFalse(fake.calls)
            self.assertEqual(before, snapshot(run))

    async def test_interrupted_calls_stop_and_resume_only_unfinished_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["a", "b", "c"])
            fake = FakeFinder()
            fake.hold = asyncio.Event()
            task = asyncio.create_task(fake.run(run))
            for _ in range(100):
                if fake.active == 3:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(fake.active, 3)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(fake.active, 0)
            self.assertEqual(load_json(run / "run.json")["status"], "interrupted")
            fake.hold = None
            record = await fake.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertFalse(any("waiting_progress" in repr(t.get_coro()) for t in asyncio.all_tasks()))

    async def test_incomplete_provider_output_is_preserved_and_only_retried_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["one"])
            fake = FakeFinder()
            key = "source_finder/000001"
            fake.outputs[key] = AIMessage(content='{"partial":', response_metadata={"status": "incomplete"})
            record = await fake.run(run)
            self.assertEqual(record["status"], "failed")
            self.assertEqual(local_path(run, record["jobs"][key]["response_path"]).read_text(encoding="utf-8"), '{"partial":')
            await fake.run(run)
            self.assertEqual(len(fake.calls), 1)
            fake.outputs[key] = source_json()
            await fake.run(run, retry_failed=True)
            self.assertEqual(len(fake.calls), 2)

    async def test_publication_rebuild_and_history_need_no_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            record = await fake.run(run)
            path = local_path(run, record["domains"][0]["output_path"])
            path.write_text("Old presentation\r\n", newline="")
            publish(run)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), json.loads(source_json()))
            history = list((run / "_internal/trace/presentation_history").rglob(path.name))
            self.assertEqual(history[0].read_bytes(), b"Old presentation\r\n")
            path.unlink()
            await fake.run(run)
            self.assertEqual(len(fake.calls), 2)
            self.assertTrue(path.is_file())

    async def test_publication_failure_is_operational_and_recovers_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            with patch("ML.deep_research.layer3.source_runner.publish", side_effect=OSError("PRIVATE_DISK")):
                with self.assertRaises(OSError):
                    await fake.run(run)
            self.assertEqual(load_json(run / "run.json")["status"], "failed")
            record = await fake.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(fake.calls), 2)

    async def test_trace_write_failure_never_resends_completed_content(self):
        from ML.deep_research.layer3.source_finder import write_json as persist
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["one"])
            fake = FakeFinder()
            def fail_trace(path, value):
                if path.name == "provider_message.json":
                    raise OSError("PRIVATE_DISK")
                return persist(path, value)
            with patch("ML.deep_research.layer3.source_finder.write_json", side_effect=fail_trace):
                record = await fake.run(run)
            self.assertEqual(record["status"], "failed")
            record = await fake.run(run, retry_failed=True)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(record["publication"]["published_sources"], 1)
            self.assertIn("provider_trace_unavailable", (run / "README.md").read_text(encoding="utf-8"))

    async def test_changed_request_versions_preserve_prior_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["one"])
            fake = FakeFinder()
            record = await fake.run(run)
            entry = next(iter(record["jobs"].values()))
            old_path = local_path(run, entry["response_path"])
            before = old_path.read_bytes()
            record["web_search"]["verbosity"] = "high"
            write_json(run / "run.json", record)
            record = await fake.run(run)
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(old_path.read_bytes(), before)
            self.assertNotEqual(next(iter(record["jobs"].values()))["fingerprint"], entry["fingerprint"])
