"""The roster contract, the input checks, and the fact count.

Everything Layer 2 does in Python before and after the model. No model calls.
"""

import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.fs import load_json
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.report import fact_blocks
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH

from tests.common import FACT_SHEET


class PlannerTests(unittest.TestCase):
    def test_planner_has_frozen_roster(self):
        _, agents = load_planner(PLANNER_PATH)
        self.assertEqual([agent["name"] for agent in agents], AGENT_NAMES)


class InputValidationTests(unittest.TestCase):
    """These validate a human-supplied file, not anything a model produced."""

    def test_json_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "claims.json"
            path.write_text('{"claims": [{"value": 1}]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at least one ## heading"):
                create_run(path, PLANNER_PATH, root / "runs")

    def test_empty_fact_sheet_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "fact_sheet.md"
            path.write_text("   \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or empty"):
                create_run(path, PLANNER_PATH, root / "runs")

    def test_run_folder_holds_inputs_missions_and_staging(self):
        """No pieces/, no buckets/, no progress ledger.

        `staging/` is scratch space the agent may use when the sheet is too large
        to hold in one context. It is the agent's, not a pipeline stage.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "fact_sheet.md"
            fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            self.assertEqual(
                sorted(item.name for item in run_dir.iterdir() if item.is_dir()),
                ["inputs", "missions", "staging"],
            )
            self.assertFalse((run_dir / "progress.csv").exists())
            # Empty until the agent decides it needs it.
            self.assertEqual(list((run_dir / "staging").iterdir()), [])

    def test_the_run_record_takes_its_agent_count_from_the_roster(self):
        """Never a hardcoded 14 -- the roster is the single source."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "fact_sheet.md"
            fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            record = load_json(run_dir / "run.json")
        self.assertEqual(record["agent_count"], len(AGENT_NAMES))
        # The report is what turns this into "complete" or "failed".
        self.assertEqual(record["status"], "started")


class CountingTests(unittest.TestCase):
    """The report counts fact blocks. It never uses them to gate anything."""

    def test_fact_blocks_are_counted(self):
        self.assertEqual(len(fact_blocks(FACT_SHEET)), 3)

    def test_a_sheet_with_no_fact_blocks_counts_zero(self):
        self.assertEqual(fact_blocks("# Property\n\n## Summary\n\nPlain text.\n"), [])


if __name__ == "__main__":
    unittest.main()
