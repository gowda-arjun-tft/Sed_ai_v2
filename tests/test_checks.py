import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.backend.cli import main
from ML.deep_research.layer2.backend.create_run import require_current
from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.report import run_checks
from ML.deep_research.layer2.backend.runner import run_all
from tests.layer2_fixtures import FakeStages, new_run


class ReportTests(unittest.TestCase):
    def test_current_checks_are_read_only_and_coverage_is_observational(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.unusual.add("assignments")
            fake.run(run)
            before = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}
            checks = run_checks(run)
            self.assertFalse(checks[-1][2])
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
            self.assertEqual(before, {p: p.read_bytes() for p in run.rglob("*") if p.is_file()})
            self.assertEqual(main(["--check-only", str(run)]), 1)
            self.assertEqual(before, {p: p.read_bytes() for p in run.rglob("*") if p.is_file()})

    def test_historical_resume_and_check_reject_without_mutation(self):
        for schema in [2, 3, 4]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_json(root / "run.json", {"schema_version": schema})
                before = (root / "run.json").read_bytes()
                for function in [require_current, run_all, run_checks]:
                    with self.assertRaisesRegex(ValueError, "schema 5"):
                        function(root)
                for option in ["--resume", "--check-only"]:
                    with self.assertRaises(SystemExit):
                        main([option, str(root)])
                self.assertEqual((root / "run.json").read_bytes(), before)
                self.assertFalse((root / "run.log").exists())
