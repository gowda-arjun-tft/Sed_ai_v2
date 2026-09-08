import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.jobs import run_jobs
from ML.deep_research.layer2.backend.records import catalogue, read_ledger
from ML.deep_research.layer2.backend.run_log import operational_logger
from ML.deep_research.layer2.backend.windows import source_windows
from tests.layer2_fixtures import FakeStages, new_run, published


class RunnerTests(unittest.TestCase):
    def test_full_flow_distinct_plugins_and_exact_fact_publication(self):
        plugins = [
            ("# Real estate\n## Systems\n## Rights\n## Demand\n", 3),
            ("# Insurance\n## Underwriting\n## Claims\n", 2),
            ("# Stock market\n## Earnings\n## Capital structure\n## Trading liquidity\n", 3),
        ]
        for plugin, count in plugins:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp), plugin=plugin)
                fake = FakeStages()
                fake.run(run)
                self.assertEqual([s for s, *_ in fake.calls],
                                 ["understanding", "design", "distribution", "observations", "catalogue", "assignments"])
                self.assertEqual(load_json(run / "run.json")["status"], "complete")
                expected = [line[3:] for line in plugin.splitlines() if line.startswith("## ")]
                initial = load_json(run / "_internal/domains.json")["initial"]
                self.assertEqual([row["definition"]["name"] for row in initial], expected)
                for _, payload, _ in fake.calls:
                    self.assertEqual(payload["domain_plugin"], plugin)
                    self.assertEqual(payload["requirements"], "Preserve all facts and ownership.")
                final = load_json(run / "_internal/domains.json")["final"]
                self.assertEqual(len(final), count + 1)
                facts = read_ledger(run / "_internal/facts.jsonl")
                assignments = load_json(run / "_internal/assignments.json")["final"]
                self.assertEqual([f["fact_id"] for f in facts], [a["fact_id"] for a in assignments])
                self.assertTrue(all(a["domain_ids"] == [final[-1]["domain_id"]] for a in assignments))
                report = (run / "domains/additional-use.md").read_text(encoding="utf-8")
                self.assertIn("17.5 m²", report)
                self.assertIn("Approved alternative", report)
                self.assertFalse(list((run / "domains").glob("*.json")))
                self.assertEqual(len(facts), 2)
                self.assertEqual(load_json(run / "run.json")["coverage"]["unresolved_facts"], 0)
                self.assertEqual(len(fake.calls[-3][1]["facts"]), 2)  # existing owner AND Extra
                self.assertEqual(fake.calls[-3][1]["initial_catalogue"], initial)
                self.assertEqual(fake.calls[-1][1]["final_catalogue"], final)
                self.assertEqual([f["initial_assignment"]["domain_ids"] for f in fake.calls[-1][1]["facts"]],
                                 [["d0001"], []])
                self.assertEqual([f["body"] for f in fake.calls[-1][1]["facts"]], [f["body"] for f in facts])
                self.assertEqual(fake.calls[0][1]["new_content"], fake.calls[2][1]["new_content"])

    def test_unusual_objects_are_saved_without_retry_or_status_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.unusual.add("assignments")
            fake.run(run)
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
            self.assertEqual(load_json(run / "run.json")["coverage"]["unresolved_facts"], 2)
            self.assertIn("unusable_assignments", (run / "unresolved.md").read_text())
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])

    def test_failure_resume_same_thread_new_dependent_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.fail.add("distribution")
            fake.run(run)
            self.assertEqual(load_json(run / "run.json")["status"], "partial")
            before = load_json(run / "run.json")["jobs"]
            old_publication = published(run)
            fake.fail.clear()
            fake.calls.clear()
            fake.run(run)
            after = load_json(run / "run.json")["jobs"]
            self.assertEqual(after["distribution/000001"]["thread_id"], before["distribution/000001"]["thread_id"])
            self.assertEqual(after["distribution/000001"]["attempt"], 2)
            self.assertEqual([s for s, *_ in fake.calls][0], "distribution")
            self.assertNotEqual(after["catalogue/000001"]["thread_id"], before["catalogue/000001"]["thread_id"])
            self.assertTrue(old_publication.is_dir())
            self.assertEqual(load_json(run / "run.json")["status"], "complete")

    def test_all_windows_native_concurrency_and_partial_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ML.deep_research.layer2.backend.create_run.source_windows",
                       side_effect=lambda text: source_windows(text, 10, 2)):
                run = new_run(Path(tmp), text=" property" * 60)
            record = load_json(run / "run.json")
            record["chunking"]["max_concurrency"] = 2
            write_json(run / "run.json", record)
            fake = FakeStages()
            fake.delay = .01
            fake.fail.add(("distribution", "s000002"))
            fake.run(run)
            manifest = load_json(run / "_internal/trace/source/manifest.json")
            for stage in ["understanding", "distribution"]:
                self.assertEqual(sorted(d["source"]["source_id"] for s, d, _ in fake.calls if s == stage),
                                 [w["source_id"] for w in manifest])
            self.assertEqual(fake.peak, 2)
            self.assertGreater(load_json(run / "run.json")["coverage"]["recorded_facts"], 0)
            self.assertEqual(load_json(run / "run.json")["status"], "partial")

    def test_safe_ids_and_unusable_catalogues(self):
        initial, _ = catalogue({"domains": [{"name": "../../.env"}, {"name": "Same"}]})
        self.assertEqual([d["domain_id"] for d in initial], ["d0001", "d0002"])
        final, audit = catalogue({"domains": [
            {"domain_id": "d0001"}, {"domain_id": "d0001"},
            {"domain_id": "../secrets"}, {"domain_id": None, "name": "Addition"}, ["odd"]
        ]}, initial)
        self.assertEqual([d["domain_id"] for d in final], ["d0001", "d0003"])
        self.assertEqual(len(audit), 3)

    def test_native_out_of_order_completion_saves_immediately_and_returns_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))

            async def invoke(value, config):
                number = json.loads(value["messages"][0]["content"])["number"]
                if number == 0:
                    await asyncio.sleep(.15)
                    fast = load_json(run / "run.json")["jobs"]["understanding/000002"]
                    self.assertEqual(fast["status"], "complete")
                    self.assertEqual(load_json(run / fast["response_path"]), {"number": 1})
                return {"structured_response": {"number": number}}

            with operational_logger(run) as logger, patch(
                "ML.deep_research.layer2.backend.jobs.create_stage_agent", return_value=RunnableLambda(invoke),
            ):
                results = asyncio.run(run_jobs(run, "understanding", [{"number": 0}, {"number": 1}],
                                               {}, None, logger))
            self.assertEqual([row["value"]["number"] for row in results], [0, 1])

    def test_hash_protection_and_unreadable_response_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            record = load_json(run / "run.json")
            path = run / record["jobs"]["observations/000001"]["response_path"]
            path.write_text("unreadable")
            fake.calls.clear()
            fake.run(run)
            self.assertEqual([s for s, *_ in fake.calls], ["observations"])
            (run / "_internal/inputs/requirements.md").write_text("changed input")
            fake.calls.clear()
            with self.assertRaises(OSError):
                fake.run(run)
            self.assertEqual(fake.calls, [])
