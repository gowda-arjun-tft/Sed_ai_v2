import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.agent import _partition_chunk
from ML.deep_research.layer2.cli import _split_run_fact_sheet, split_fact_sheet
from ML.deep_research.layer2.create_run import RUN_SUBDIRS, create_run
from ML.deep_research.layer2.fs import load_json, write_json
from ML.deep_research.layer2.settings import (
    CHUNK_ENCODING,
    CHUNK_INPUT_PARTITIONING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    CHUNK_STRATEGY,
    LAYER2_SCHEMA_VERSION,
    LEGACY_CHUNK_SEPARATORS,
    MAX_CHUNK_CONCURRENCY,
    PLANNER_PATH,
)
from tests.common import FACT_SHEET


class InputAndChunkingTests(unittest.TestCase):
    def test_small_fact_sheet_is_one_chunk(self):
        self.assertEqual(split_fact_sheet(FACT_SHEET), [FACT_SHEET])

    def test_one_hundred_thousand_tokens_make_two_fixed_chunks(self):
        import tiktoken

        encoding = tiktoken.get_encoding(CHUNK_ENCODING)
        token = encoding.encode(" property")[0]
        text = encoding.decode([token] * 100_000)
        chunks = split_fact_sheet(text)
        sizes = [len(encoding.encode(chunk)) for chunk in chunks]
        encoded = [encoding.encode(chunk) for chunk in chunks]
        self.assertEqual(sizes, [60_000, 50_000])
        self.assertEqual(
            encoded[0][-CHUNK_OVERLAP_TOKENS:],
            encoded[1][:CHUNK_OVERLAP_TOKENS],
        )

    def test_markdown_headings_do_not_change_fixed_boundaries(self):
        import tiktoken

        encoding = tiktoken.get_encoding(CHUNK_ENCODING)
        text = "## First\n" + "alpha " * 30_000 + "\n## Second\n" + "beta " * 30_000
        chunks = split_fact_sheet(text)
        self.assertEqual(len(chunks), 2)
        expected = encoding.encode(text)
        self.assertEqual(encoding.encode(chunks[0]), expected[:60_000])
        self.assertEqual(encoding.encode(chunks[1]), expected[50_000:])

    def test_final_chunk_stops_without_a_redundant_tail(self):
        import tiktoken

        encoding = tiktoken.get_encoding(CHUNK_ENCODING)
        token = encoding.encode(" property")[0]
        text = encoding.decode([token] * 701_133)
        chunks = split_fact_sheet(text)
        encoded = [encoding.encode(chunk) for chunk in chunks]
        sizes = [len(tokens) for tokens in encoded]
        self.assertEqual(sizes, [60_000] * 13 + [51_133])
        self.assertEqual(sum(sizes), 831_133)
        for index, chunk in enumerate(chunks, start=1):
            overlap, new = _partition_chunk(
                chunk, index, CHUNK_ENCODING, CHUNK_OVERLAP_TOKENS
            )
            self.assertEqual(
                encoding.encode(overlap + new), encoded[index - 1]
            )
            if index == 1:
                self.assertEqual(overlap, "")
            else:
                self.assertEqual(
                    encoding.encode(overlap), encoded[index - 2][-10_000:]
                )

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
        self.assertEqual(record["chunking"]["strategy"], CHUNK_STRATEGY)
        self.assertEqual(
            record["chunking"]["input_partitioning"], CHUNK_INPUT_PARTITIONING
        )
        self.assertEqual(record["chunking"]["size_tokens"], CHUNK_SIZE_TOKENS)
        self.assertEqual(record["chunking"]["overlap_tokens"], CHUNK_OVERLAP_TOKENS)
        self.assertEqual(record["chunking"]["stride_tokens"], 50_000)
        self.assertEqual(record["chunking"]["max_concurrency"], MAX_CHUNK_CONCURRENCY)
        self.assertNotIn("separators", record["chunking"])
        self.assertEqual(record["limits"]["provider_max_retries"], 3)
        self.assertNotIn("output_tokens_per_model_call", record["limits"])
        self.assertNotIn("summarization_trigger_tokens", record["limits"])

    def test_existing_schema_two_run_uses_its_legacy_frozen_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fact_sheet.md"
            text = "## First\n" + "alpha " * 300 + "\n## Second\n" + "beta " * 300
            source.write_text(text, encoding="utf-8")
            run_dir = create_run(source, PLANNER_PATH, root / "runs")
            record = load_json(run_dir / "run.json")
            record["chunking"].update(
                size_tokens=400,
                overlap_tokens=40,
                separators=list(LEGACY_CHUNK_SEPARATORS),
            )
            record["chunking"].pop("strategy")
            record["chunking"].pop("input_partitioning")
            record["chunking"].pop("stride_tokens")
            write_json(run_dir / "run.json", record)

            chunks = _split_run_fact_sheet(run_dir)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(any(chunk.startswith("## Second\n") for chunk in chunks[1:]))

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
