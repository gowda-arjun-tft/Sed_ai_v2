import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from ML.deep_research.layer2.agent import domain_key, response_schema
from ML.deep_research.layer2.cli import main, merge_chunks, write_missions
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.fs import load_json, slug, write_json
from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH
from ML.deep_research.layer2.usage import UsageCallback, summarize_usage
from tests.common import FACT_SHEET


def _batch(schema, label: str):
    return schema.model_validate(
        {
            domain_key(name): {
                "mission": f"mission-{label}-{index}",
                "context": [{"section": "S", "fact": label, "means": "M"}],
            }
            for index, name in enumerate(AGENT_NAMES)
        }
    )


class ParallelRunnerTests(unittest.TestCase):
    def _run(self, root: Path) -> Path:
        source = root / "fact_sheet.md"
        source.write_text(FACT_SHEET, encoding="utf-8")
        return create_run(source, PLANNER_PATH, root / "runs")

    def test_merge_appends_chunk_order_and_keeps_overlap_duplicates(self):
        _, definitions = load_planner(PLANNER_PATH)
        schema = response_schema(definitions)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            merge_chunks(run_dir, [_batch(schema, "same"), _batch(schema, "same")])
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")
        self.assertEqual(mission["mission"], "mission-same-0\n\nmission-same-0")
        self.assertEqual([item["fact"] for item in mission["context"]], ["same", "same"])
        self.assertNotIn("where", mission["context"][0])

    def test_seven_chunks_run_with_at_most_five_concurrent_calls(self):
        _, definitions = load_planner(PLANNER_PATH)
        schema = response_schema(definitions)

        class Graph:
            active = 0
            maximum = 0

            async def ainvoke(self, value, **_kwargs):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return {"structured_response": _batch(schema, value["messages"][0]["content"][-1])}

        graph = Graph()
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=list("1234567")),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=(graph, schema)),
            ):
                asyncio.run(write_missions(run_dir))
            record = load_json(run_dir / "run.json")
        self.assertEqual(graph.maximum, 5)
        self.assertTrue(all(item["status"] == "complete" for item in record["chunking"]["chunks"]))

    def test_resume_reuses_valid_chunk_and_reruns_invalid_json(self):
        _, definitions = load_planner(PLANNER_PATH)
        schema = response_schema(definitions)

        class Graph:
            calls = 0

            async def ainvoke(self, *_args, **_kwargs):
                self.calls += 1
                return {"structured_response": _batch(schema, "rerun")}

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            write_json(run_dir / "chunks" / "chunk_0001.json", _batch(schema, "saved").model_dump())
            (run_dir / "chunks" / "chunk_0002.json").write_text("not json", encoding="utf-8")
            graph = Graph()
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=["one", "two"]),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=(graph, schema)),
            ):
                asyncio.run(write_missions(run_dir))
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")

        self.assertEqual(graph.calls, 1)
        self.assertEqual([item["fact"] for item in mission["context"]], ["saved", "rerun"])

    def test_legacy_resume_is_rejected_clearly(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            record = load_json(run_dir / "run.json")
            record.pop("schema_version")
            write_json(run_dir / "run.json", record)
            with self.assertRaises(SystemExit) as caught:
                main(["--resume", str(run_dir)])
        self.assertEqual(caught.exception.code, 2)


class UsageRecordTests(unittest.TestCase):
    def test_concurrent_callback_records_and_sums_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            callback = UsageCallback(run_dir, "chunk-0001")
            run_id = uuid4()
            callback.on_chat_model_start({}, [], run_id=run_id, metadata={})
            message = SimpleNamespace(
                name=None,
                usage_metadata={
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "total_tokens": 1500,
                    "input_token_details": {"cache_read": 400},
                    "output_token_details": {"reasoning": 200},
                },
            )
            callback.on_llm_end(
                SimpleNamespace(generations=[[SimpleNamespace(message=message)]]),
                run_id=run_id,
            )
            rows = [json.loads(line) for line in (run_dir / "usage.jsonl").read_text().splitlines()]
            summary = summarize_usage(run_dir)
        self.assertEqual(rows[0]["thread_id"], "chunk-0001")
        self.assertEqual(summary["input_tokens"], 1200)
        self.assertEqual(summary["reasoning_output_tokens"], 200)


if __name__ == "__main__":
    unittest.main()
