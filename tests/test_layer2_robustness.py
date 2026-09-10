import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.jobs import saved_text
from ML.deep_research.layer2.backend.runner import UnusableDomainPlanError
from tests.layer2_fixtures import FakeStages, new_run, published


class RecoveryTests(unittest.TestCase):
    def test_out_of_order_native_batching_saves_immediately_and_merges_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" 1 2 3 4 5 6 7 8 9 10 11 12", size=9)
            fake = FakeStages()
            fake.outputs.update({"distribution/000001": '{"D01":"First window contribution."}',
                                 "distribution/000002": '{"D01":"Second window contribution."}'})
            fake.delay = lambda key: .06 if key == "distribution/000001" else .002
            original = __import__("ML.deep_research.layer2.backend.jobs", fromlist=["write_json"]).write_json
            observed = []
            def observe(path, value):
                if path == run / "run.json" and value.get("jobs", {}).get("distribution/000002", {}).get("status") == "complete":
                    early = value["jobs"].get("distribution/000001", {}).get("status") != "complete"
                    observed.append(early)
                return original(path, value)
            with patch("ML.deep_research.layer2.backend.jobs.write_json", side_effect=observe):
                fake.run(run)
            self.assertTrue(any(observed))
            output = (run / "domains/operations.md").read_text()
            self.assertLess(output.index("First window"), output.index("Second window"))
            self.assertGreater(fake.peak, 1)
            self.assertLessEqual(fake.peak, 5)

    def test_frozen_concurrency_and_bounded_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 91, size=9)
            record = load_json(run / "run.json")
            record["chunking"]["max_concurrency"] = 2
            write_json(run / "run.json", record)
            from tests.layer2_fixtures import OfflineModel
            batch_sizes = []
            native = OfflineModel.abatch_as_completed
            async def batching(model, inputs, config=None, **kw):
                batch_sizes.append(len(inputs))
                async for value in native(model, inputs, config, **kw):
                    yield value
            fake = FakeStages()
            fake.delay = .005
            with patch.object(OfflineModel, "abatch_as_completed", batching):
                fake.run(run)
            self.assertEqual(fake.peak, 2)
            self.assertTrue(all(n <= 4 for n in batch_sizes))

    def test_resume_reuses_empty_and_unconventional_completed_markdown(self):
        for text in ("", "Unusual answer", '{"unexpected": [1, null]}'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp))
                fake = FakeStages()
                fake.outputs.update(metadata=text, distribution=text)
                fake.run(run)
                self.assertEqual(load_json(run / "run.json")["status"], "complete")
                fake.run(run)
                self.assertEqual(len(fake.calls), 3)
                self.assertTrue(load_json(run / "_internal/trace/routing_issues.json")["issues"])
                for row in load_json(run / "run.json")["jobs"].values():
                    if row["stage"] != "design":
                        self.assertEqual(saved_text(run / row["response_path"]), text)

    def test_unusable_completed_plan_stops_only_dependent_work_without_repair_on_resume(self):
        for text in ("", "Unusual answer", '{"unexpected": [1, null]}', '{"domains": []}'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp))
                fake = FakeStages()
                fake.outputs["design"] = text
                for _ in range(2):
                    with self.assertRaises(UnusableDomainPlanError):
                        fake.run(run)
                self.assertEqual([stage for stage, _, _ in fake.calls], ["metadata", "design"])
                record = load_json(run / "run.json")
                self.assertEqual(record["jobs"]["design/000001"]["status"], "complete")
                self.assertEqual(saved_text(run / record["jobs"]["design/000001"]["response_path"]), text)
                self.assertFalse((run / "domain_plan.json").exists())
                self.assertIn("No usable domain definitions", (run / "domain_plan.md").read_text())
                self.assertTrue((run / "asset_metadata.md").exists())

    def test_failed_sibling_is_only_retry_and_siblings_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 19, size=10)
            fake = FakeStages()
            fake.fail.add("distribution/000002")
            fake.run(run)
            first = load_json(run / "run.json")
            self.assertEqual(first["status"], "partial")
            self.assertTrue((run / "domains/operations.md").is_file())
            count = len(fake.calls)
            fake.fail.clear()
            fake.run(run)
            second = load_json(run / "run.json")
            self.assertEqual(len(fake.calls), count + 1)
            self.assertEqual(second["jobs"]["distribution/000002"]["attempt"], 2)
            self.assertEqual(second["status"], "complete")

    def test_metadata_or_design_failure_stops_dependent_calls(self):
        for stage in ("metadata", "design"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp), text=" x" * 19, size=10)
                fake = FakeStages()
                fake.fail.add(stage)
                fake.run(run)
                self.assertFalse(any(s == "distribution" for s, _, _ in fake.calls))
                self.assertEqual(load_json(run / "run.json")["status"], "failed")

    def test_upstream_recovery_invalidates_only_changed_dependencies_and_archives_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 19, size=10)
            fake = FakeStages()
            fake.run(run)
            before = load_json(run / "run.json")
            old_view = (run / "asset_metadata.md").read_bytes()
            missing = run / before["jobs"]["metadata/000002"]["response_path"]
            missing.unlink()
            fake.outputs["metadata/000002"] = "Changed metadata — uncertain use"
            count = len(fake.calls)
            fake.run(run)
            newcalls = [job for _, _, job in fake.calls[count:]]
            self.assertNotIn("metadata/000001", newcalls)
            self.assertIn("metadata/000003", newcalls)
            self.assertIn("design/000001", newcalls)
            self.assertIn("distribution/000001", newcalls)
            histories = list((run / "_internal/trace/presentation_history").rglob("asset_metadata.md"))
            self.assertTrue(any(path.read_bytes() == old_view for path in histories))
            old_design = run / before["jobs"]["design/000001"]["response_path"]
            self.assertTrue(old_design.exists())

    def test_saved_raw_response_survives_interrupted_metadata_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            from ML.deep_research.layer2.backend import jobs
            original = jobs.write_json
            interrupted = False
            def fail_commit(path, value):
                nonlocal interrupted
                if path == run / "run.json" and value.get("jobs", {}).get("metadata/000001", {}).get("status") == "complete" and not interrupted:
                    interrupted = True
                    raise KeyboardInterrupt()
                original(path, value)
            with patch.object(jobs, "write_json", side_effect=fail_commit):
                with self.assertRaises(KeyboardInterrupt):
                    fake.run(run)
            self.assertEqual(len(fake.calls), 1)
            fake.run(run)
            self.assertEqual(len(fake.calls), 3)

    def test_interrupt_after_raw_write_cannot_promote_provider_incomplete_content(self):
        from langchain_core.messages import AIMessage
        from ML.deep_research.layer2.backend import jobs
        for status in ("incomplete", "completed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp))
                fake = FakeStages()
                fake.outputs["metadata"] = AIMessage(content="Received text", response_metadata={"status": status})
                original = jobs.atomic_write_text
                def interrupt(path, text):
                    original(path, text)
                    raise KeyboardInterrupt()
                with patch.object(jobs, "atomic_write_text", side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        fake.run(run)
                fake.outputs.clear()
                fake.run(run)
                metadata_calls = [key for stage, _, key in fake.calls if stage == "metadata"]
                self.assertEqual(len(metadata_calls), 2 if status == "incomplete" else 1)

    def test_changed_frozen_inputs_fail_without_any_run_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            (run / "_internal/inputs/domain_plugin.md").write_text("Changed plugin")
            before = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}
            fake = FakeStages()
            with self.assertRaisesRegex(OSError, "frozen input"):
                fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertEqual(before, {p: p.read_bytes() for p in run.rglob("*") if p.is_file()})

    def test_interrupted_recovery_finds_unchanged_downstream_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=" x" * 19, size=10)
            fake = FakeStages()
            fake.run(run)
            old = load_json(run / "run.json")
            (run / old["jobs"]["metadata/000002"]["response_path"]).unlink()
            fake.fail.add("metadata/000002")
            fake.run(run)
            failed = load_json(run / "run.json")
            self.assertNotIn("design/000001", failed["jobs"])
            self.assertFalse((run / "domain_plan.json").exists())
            before = len(fake.calls)
            fake.fail.clear()
            fake.run(run)
            self.assertEqual([job for _, _, job in fake.calls[before:]], ["metadata/000002"])
            self.assertEqual(load_json(run / "run.json")["status"], "complete")

    def test_incomplete_provider_result_is_not_misread_after_interrupted_job_commit(self):
        from langchain_core.messages import AIMessage
        from ML.deep_research.layer2.backend import jobs

        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.outputs["metadata"] = AIMessage(content="Partial", response_metadata={"status": "incomplete"})
            original = jobs.write_json
            def fail_commit(path, value):
                if path == run / "run.json" and value.get("jobs", {}).get("metadata/000001", {}).get("error_type") == "IncompleteResponseError":
                    raise KeyboardInterrupt()
                original(path, value)
            with patch.object(jobs, "write_json", side_effect=fail_commit):
                with self.assertRaises(KeyboardInterrupt):
                    fake.run(run)
            fake.outputs.clear()
            fake.run(run)
            self.assertEqual([stage for stage, _, _ in fake.calls], ["metadata", "metadata", "design", "distribution"])
            self.assertTrue(any(p.read_text() == "Partial" for p in (run / "_internal/trace/responses").rglob("response.md")))
