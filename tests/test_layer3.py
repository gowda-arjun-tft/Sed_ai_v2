"""Current source-discovery creation, preservation and historical rejection."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.domain_decider.backend.fs import load_json, write_json
from ML.deep_research.research_module.backend.run_checks import run_checks
from ML.deep_research.research_module.backend.settings import HARNESS_NAME, SCHEMA_VERSION
from tests.layer3_fixtures import FakeFinder, new_run, snapshot


class Layer3SchemaTests(unittest.TestCase):
    def test_schema_nine_discovers_dynamic_domains_without_research_or_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            for count in (1, 3, 10):
                run = new_run(Path(tmp) / str(count), [f"domain-{i}" for i in range(count)])
                record = load_json(run / "run.json")
                self.assertEqual(record["schema_version"], SCHEMA_VERSION)
                self.assertEqual(record["harness"], HARNESS_NAME)
                self.assertEqual(len(record["domains"]), count)
                self.assertEqual(record["max_concurrency"], 5)
                self.assertEqual(record["reasoning_effort"], "high")
                self.assertEqual(record["provider_max_retries"], 3)
                self.assertNotIn("execution", record)
                self.assertNotIn("context_management", record)
                self.assertFalse(list(run.rglob("*.sqlite*")))
                self.assertFalse((run / "research").exists())
                self.assertFalse((run / "inputs/planner_prompt.md").exists())

    def test_publication_and_checks_do_not_grade_content_or_mutate_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeFinder()
            fake.outputs["source_finder/000001"] = '{"unexpected": {"医院": [1, null]}}'
            fake.outputs["source_finder/000002"] = ""
            asyncio.run(fake.run(run))
            before = snapshot(run)
            checks = run_checks(run)
            self.assertEqual(before, snapshot(run))
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
            self.assertEqual(len(list((run / "sources").glob("*.json"))), 1)
            self.assertTrue(all(ok for _, _, ok, _ in checks))
            self.assertIn("unreadable_json", (run / "README.md").read_text(encoding="utf-8"))
            asyncio.run(fake.run(run, retry_failed=True))
            self.assertEqual(len(fake.calls), 2)

    def test_historical_checks_reject_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            write_json(run / "run.json", {"schema_version": 8})
            before = snapshot(run)
            with self.assertRaisesRegex(ValueError, "read-only"):
                run_checks(run)
            self.assertEqual(before, snapshot(run))
