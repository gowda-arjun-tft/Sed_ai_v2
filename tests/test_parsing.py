import json
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.claims import context_from_claim_block, load_claims
from ML.deep_research.layer2.factsheet import fact_blocks, piece_body
from ML.deep_research.layer2.pipeline.create_run import create_run
from ML.deep_research.layer2.pipeline.split_fact_sheet import split_fact_sheet
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.progress import read_progress
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH

from tests.common import CLAIMS_INPUT


class ParsingTests(unittest.TestCase):
    def test_planner_has_frozen_roster(self):
        _, agents = load_planner(PLANNER_PATH)
        self.assertEqual([agent["name"] for agent in agents], AGENT_NAMES)

    def test_create_run_and_split_are_lossless(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fact_sheet = root / "claims.json"
            fact_sheet.write_text(json.dumps(CLAIMS_INPUT), encoding="utf-8")
            run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
            split_fact_sheet(run_dir)

            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            rows = read_progress(run_dir)
            routed = [
                block
                for path in (run_dir / "pieces").glob("p*.md")
                for block in fact_blocks(piece_body(path))
            ]
            self.assertEqual(run["split_mode"], "claims")
            self.assertEqual(run["input_file"], "claims.json")
            self.assertEqual(run["input"]["claims"], 2)
            self.assertNotIn("fact_sheet", run)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(routed), 2)
            self.assertEqual(
                [context_from_claim_block(block)["claim"] for block in routed],
                CLAIMS_INPUT["claims"],
            )

    def test_context_preserves_black_box_claim_and_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claims.json"
            path.write_text(json.dumps(CLAIMS_INPUT), encoding="utf-8")
            run_dir = create_run(path, PLANNER_PATH, Path(temporary) / "runs")
            split_fact_sheet(run_dir)
            piece = next((run_dir / "pieces").glob("p*.md"))
            context = context_from_claim_block(fact_blocks(piece_body(piece))[0])
            self.assertEqual(context["claim"], CLAIMS_INPUT["claims"][0])
            self.assertEqual(context["input_pointer"], "/claims/0")

    def test_top_level_claim_list_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claims.json"
            path.write_text(json.dumps(CLAIMS_INPUT["claims"]), encoding="utf-8")
            claims, pointer_base = load_claims(path)
            self.assertEqual(claims, CLAIMS_INPUT["claims"])
            self.assertEqual(pointer_base, "")

    def test_markdown_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fact_sheet.md"
            path.write_text("## Old Markdown input", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"\.json file"):
                create_run(path, PLANNER_PATH, Path(temporary) / "runs")


if __name__ == "__main__":
    unittest.main()
