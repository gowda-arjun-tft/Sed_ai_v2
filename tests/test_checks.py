import json
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.cli import main
from ML.deep_research.layer2.fs import load_json, slug
from ML.deep_research.layer2.report import run_checks
from ML.deep_research.layer2.settings import AGENT_NAMES

from tests.common import create_complete_run


class ReportTests(unittest.TestCase):
    def test_a_complete_run_passes_every_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            checks = run_checks(create_complete_run(Path(temporary)))
            self.assertEqual(sum(ok for _, _, ok, _ in checks), len(checks))

    def test_completed_run_remains_checkable(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            self.assertEqual(main(["--check-only", str(run_dir)]), 0)

    def test_a_missing_mission_fails_the_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            (run_dir / "missions" / f"{slug(AGENT_NAMES[3])}.json").unlink()
            checks = run_checks(run_dir)
            self.assertLess(sum(ok for _, _, ok, _ in checks), len(checks))
            self.assertEqual(load_json(run_dir / "run.json")["status"], "failed")

    def test_an_empty_locator_fails_the_report(self):
        """`where` is what Layer 3 traces a fact back through."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            path = run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json"
            mission = load_json(path)
            mission["context"][0]["where"] = ""
            path.write_text(json.dumps(mission), encoding="utf-8")
            checks = run_checks(run_dir)
            self.assertLess(sum(ok for _, _, ok, _ in checks), len(checks))

    def test_fact_counts_are_reported_but_never_gate(self):
        """Dropping every fact still passes. The number is for a human."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            path = run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json"
            mission = load_json(path)
            mission["context"] = []
            path.write_text(json.dumps(mission), encoding="utf-8")
            checks = run_checks(run_dir)
            self.assertEqual(sum(ok for _, _, ok, _ in checks), len(checks))
            facts = load_json(run_dir / "run.json")["facts"]
            self.assertEqual(facts["context_entries"], 0)
            self.assertGreater(facts["sheet_blocks"], 0)


if __name__ == "__main__":
    unittest.main()
