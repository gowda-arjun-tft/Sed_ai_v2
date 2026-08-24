import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.cli import split_fact_sheet
from ML.deep_research.layer2.create_run import RUN_SUBDIRS, create_run
from ML.deep_research.layer2.fs import load_json
from ML.deep_research.layer2.settings import (
    CHUNK_ENCODING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SEPARATORS,
    CHUNK_SIZE_TOKENS,
    LAYER2_SCHEMA_VERSION,
    MAX_CHUNK_CONCURRENCY,
    PLANNER_PATH,
)
from tests.common import FACT_SHEET


class InputAndChunkingTests(unittest.TestCase):
    def test_small_fact_sheet_is_one_chunk(self):
        self.assertEqual(split_fact_sheet(FACT_SHEET), [FACT_SHEET.rstrip()])

    def test_one_hundred_thousand_tokens_make_three_overlapping_chunks(self):
        import tiktoken

        encoding = tiktoken.get_encoding(CHUNK_ENCODING)
        token = encoding.encode(" property")[0]
        text = encoding.decode([token] * 100_000)
        chunks = split_fact_sheet(text)
        sizes = [len(encoding.encode(chunk)) for chunk in chunks]
        self.assertEqual(len(chunks), 3)
        self.assertLessEqual(max(sizes), CHUNK_SIZE_TOKENS)
        self.assertGreater(sizes[-1], CHUNK_OVERLAP_TOKENS)

    def test_markdown_heading_is_preferred_as_a_chunk_boundary(self):
        text = "## First\n" + "alpha " * 30_000 + "\n## Second\n" + "beta " * 30_000
        chunks = split_fact_sheet(text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[1].startswith("## Second\n"))

    def test_run_folder_records_schema_and_chunk_policy_without_output_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fact_sheet.md"
            source.write_text(FACT_SHEET, encoding="utf-8")
            run_dir = create_run(source, PLANNER_PATH, root / "runs")
            record = load_json(run_dir / "run.json")

        self.assertEqual(
            tuple(RUN_SUBDIRS), ("inputs", "chunks", "missions", "mission_md")
        )
        self.assertEqual(run_dir.parent.parent, root / "runs")
        self.assertEqual(run_dir.parent.name, record["run_group"])
        self.assertIn("fact-sheet", run_dir.parent.name)
        self.assertRegex(run_dir.name, r"^L2_\d{8}_\d{6}_[0-9a-f]{4}$")
        self.assertEqual(record["schema_version"], LAYER2_SCHEMA_VERSION)
        self.assertEqual(record["chunking"]["size_tokens"], CHUNK_SIZE_TOKENS)
        self.assertEqual(record["chunking"]["overlap_tokens"], CHUNK_OVERLAP_TOKENS)
        self.assertEqual(record["chunking"]["max_concurrency"], MAX_CHUNK_CONCURRENCY)
        self.assertEqual(record["chunking"]["separators"], list(CHUNK_SEPARATORS))
        self.assertEqual(record["limits"]["provider_max_retries"], 3)
        self.assertNotIn("output_tokens_per_model_call", record["limits"])
        self.assertNotIn("summarization_trigger_tokens", record["limits"])

    def test_nonempty_markdown_does_not_require_a_heading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fact_sheet.md"
            source.write_text("plain text", encoding="utf-8")
            run_dir = create_run(source, PLANNER_PATH, root / "runs")
            self.assertEqual(
                (run_dir / "inputs" / "fact_sheet.md").read_text(), "plain text"
            )

    def test_same_input_is_grouped_and_same_named_inputs_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "property-a" / "fact_sheet.md"
            second = root / "property-b" / "fact_sheet.md"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_text(FACT_SHEET, encoding="utf-8")
            second.write_text(FACT_SHEET, encoding="utf-8")
            first_run = create_run(first, PLANNER_PATH, root / "runs")
            repeated_run = create_run(first, PLANNER_PATH, root / "runs")
            second_run = create_run(second, PLANNER_PATH, root / "runs")

        self.assertEqual(first_run.parent, repeated_run.parent)
        self.assertNotEqual(first_run, repeated_run)
        self.assertNotEqual(first_run.parent, second_run.parent)


if __name__ == "__main__":
    unittest.main()
