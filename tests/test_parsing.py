import json
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.factsheet import context_from_block, fact_blocks, piece_body
from ML.deep_research.layer2.fs import read_text
from ML.deep_research.layer2.pipeline.create_run import create_run
from ML.deep_research.layer2.pipeline.split_fact_sheet import split_fact_sheet
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.progress import read_progress
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH

from tests.common import FACT_SHEET


class ParsingTests(unittest.TestCase):
    def test_planner_has_frozen_roster(self):
        _, agents = load_planner(PLANNER_PATH)
        self.assertEqual([agent["name"] for agent in agents], AGENT_NAMES)

    def test_create_run_and_split_are_lossless(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "fact_sheet.md"
            fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            split_fact_sheet(run_dir)

            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            rows = read_progress(run_dir)
            routed = [
                block
                for path in (run_dir / "pieces").glob("p*.md")
                for block in fact_blocks(piece_body(path))
            ]
            skipped = [
                block
                for path in (run_dir / "pieces" / "_skipped").glob("*.md")
                for block in fact_blocks(read_text(path))
            ]
            self.assertEqual(run["split_mode"], "facts")
            self.assertIn("fact_sheet", run)
            self.assertNotIn("input", run)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(routed), 2)
            self.assertEqual(len(skipped), 1)
            self.assertCountEqual(routed + skipped, fact_blocks(FACT_SHEET))

    def test_section_only_markdown_uses_section_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "fact_sheet.md"
            fact_sheet.write_text("# Property\n\n## Summary\n\nPlain text.\n", encoding="utf-8")
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            split_fact_sheet(run_dir)
            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run["split_mode"], "sections")
            self.assertEqual(len(read_progress(run_dir)), 1)

    def test_large_section_is_not_split_by_token_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "fact_sheet.md"
            large_value = "x" * 40000
            fact_sheet.write_text(
                "# Property\n\n## Large section\n\n### Large fact\n\n"
                f"**Evidence:** {large_value}\n"
                "**Source:** `large.pdf` — locator `p1`.\n"
                "**Interpretation:** One complete oversized fact.\n",
                encoding="utf-8",
            )
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            split_fact_sheet(run_dir)
            rows = read_progress(run_dir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["section"], "Large section")
            self.assertEqual(rows[0]["part"], "1/1")

    def test_json_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "claims.json"
            path.write_text('{"claims": [{"value": 1}]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at least one ## heading"):
                create_run(path, PLANNER_PATH, root / "runs")

    def test_context_transcription_uses_exact_source_fields(self):
        block = fact_blocks(FACT_SHEET)[0]
        context = context_from_block(block)
        self.assertEqual(context["section"], "Land-register reference")
        self.assertEqual(context["fact"], '"Sheet 2967"')
        self.assertIn("register.pdf", context["where"])
        self.assertIn(context["fact"], block)


if __name__ == "__main__":
    unittest.main()
