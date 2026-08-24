import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ML.deep_research.layer2.agent import Layer2Response, domain_key
from ML.deep_research.layer2.cli import main, merge_chunks, run_all, write_missions
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.fs import load_json, slug, write_json
from ML.deep_research.layer2.mission_markdown import render_mission_markdown
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH
from ML.deep_research.layer2.usage import UsageCallback, summarize_usage
from tests.common import FACT_SHEET


def _batch(label: str):
    return {
        domain_key(name): {
            "mission": f"mission-{label}-{index}",
            "context": [{"section": "S", "fact": label, "means": "M"}],
        }
        for index, name in enumerate(AGENT_NAMES)
    }


def _wrapped_batch(label: str):
    batch = _batch(label)
    return {
        "missions": [
            {"agent": name, **batch[domain_key(name)]}
            for name in AGENT_NAMES
        ]
    }


def _named_batch(label: str):
    batch = _batch(label)
    return {name: batch[domain_key(name)] for name in AGENT_NAMES}


def _result(label: str):
    return {"structured_response": Layer2Response(root=_batch(label))}


class ParallelRunnerTests(unittest.TestCase):
    def _run(self, root: Path) -> Path:
        source = root / "fact_sheet.md"
        source.write_text(FACT_SHEET, encoding="utf-8")
        return create_run(source, PLANNER_PATH, root / "runs")

    def test_merge_appends_chunk_order_and_keeps_overlap_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            merge_chunks(run_dir, [_batch("same"), _batch("same")])
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")
            markdown = run_dir / "mission_md" / f"{slug(AGENT_NAMES[0])}.md"
            self.assertTrue(markdown.is_file())
        self.assertEqual(mission["mission"], "mission-same-0\n\nmission-same-0")
        self.assertEqual([item["fact"] for item in mission["context"]], ["same", "same"])
        self.assertNotIn("where", mission["context"][0])

    def test_mission_markdown_groups_exact_sections_without_rewriting(self):
        mission = {
            "agent": "Test domain",
            "mission": "Use every supplied fact.",
            "context": [
                {
                    "section": "Smoke extraction",
                    "fact": "Exact A line 1\nExact A line 2",
                    "means": "Meaning A line 1\nMeaning A line 2",
                },
                {"section": "Garage", "fact": "Exact B", "means": ""},
                {"section": "Smoke extraction", "fact": "", "means": "Meaning C"},
                {"section": "", "fact": "Exact D", "means": "Meaning D"},
            ],
        }
        markdown = render_mission_markdown(mission)

        self.assertEqual(markdown, render_mission_markdown(mission))
        self.assertEqual(
            markdown,
            """# Test domain

## Mission

Use every supplied fact.

## Smoke extraction

- Exact A line 1
  Exact A line 2 [Meaning A line 1
  Meaning A line 2]
- [Meaning C]

## Garage

- Exact B []

## Unsectioned

- Exact D [Meaning D]
""",
        )
        for removed in ("### Entry", "Fact:", "Means:"):
            self.assertNotIn(removed, markdown)

    def test_merge_accepts_wrapped_and_exact_domain_name_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            merge_chunks(run_dir, [_wrapped_batch("wrapped"), _named_batch("named")])
            mission = load_json(
                run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json"
            )
        self.assertEqual(
            mission["mission"], "mission-wrapped-0\n\nmission-named-0"
        )
        self.assertEqual(
            [item["fact"] for item in mission["context"]],
            ["wrapped", "named"],
        )

    def test_seven_chunks_run_with_at_most_five_concurrent_calls(self):
        class Graph:
            active = 0
            maximum = 0

            async def ainvoke(self, value, **_kwargs):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return _result(value["messages"][0]["content"][-1])

        graph = Graph()
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=list("1234567")),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=graph),
            ):
                asyncio.run(write_missions(run_dir))
            record = load_json(run_dir / "run.json")
        self.assertEqual(graph.maximum, 5)
        self.assertTrue(all(item["status"] == "complete" for item in record["chunking"]["chunks"]))

    def test_resume_reuses_schema_different_json_and_reruns_only_invalid_json(self):
        class Graph:
            calls = 0

            async def ainvoke(self, *_args, **_kwargs):
                self.calls += 1
                return _result("rerun")

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            write_json(run_dir / "chunks" / "chunk_0001.json", _batch("saved"))
            (run_dir / "chunks" / "chunk_0002.json").write_text("not json", encoding="utf-8")
            record = load_json(run_dir / "run.json")
            record["chunking"]["chunks"] = [
                {"index": 1, "file": "chunks/chunk_0001.json", "status": "complete", "error": ""},
                {"index": 2, "file": "chunks/chunk_0002.json", "status": "failed", "error": "old"},
            ]
            write_json(run_dir / "run.json", record)
            graph = Graph()
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=["one", "two"]),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=graph),
            ):
                asyncio.run(write_missions(run_dir))
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")
            record = load_json(run_dir / "run.json")

        self.assertEqual(graph.calls, 1)
        self.assertEqual([item["fact"] for item in mission["context"]], ["saved", "rerun"])
        self.assertEqual([item["attempt"] for item in record["chunking"]["chunks"]], [0, 1])

    def test_one_failed_chunk_does_not_block_available_missions(self):
        class Graph:
            async def ainvoke(self, value, **_kwargs):
                if "chunk 1" in value["messages"][0]["content"]:
                    raise RuntimeError("transport failed")
                return _result("available")

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=["one", "two"]),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=Graph()),
            ):
                asyncio.run(write_missions(run_dir))
            record = load_json(run_dir / "run.json")
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")

        self.assertEqual([item["status"] for item in record["chunking"]["chunks"]], ["failed", "complete"])
        self.assertEqual(record["chunking"]["chunks"][0]["attempt"], 1)
        self.assertEqual(record["chunking"]["chunks"][0]["error_type"], "RuntimeError")
        self.assertEqual(record["chunking"]["chunks"][0]["error"], "transport failed")
        self.assertEqual(record["chunking"]["result"], "partial")
        self.assertEqual(
            record["chunking"]["summary"],
            {"total": 2, "completed": 1, "failed": 1},
        )
        self.assertEqual(mission["mission"], "mission-available-0")

    def test_resume_retries_only_failed_chunk_with_a_new_attempt(self):
        callbacks = []

        class FirstGraph:
            async def ainvoke(self, value, **kwargs):
                callbacks.append(kwargs["config"]["callbacks"][0].thread_id)
                if "chunk 1" in value["messages"][0]["content"]:
                    raise RuntimeError("temporary")
                return _result("saved")

        class ResumeGraph:
            calls = 0

            async def ainvoke(self, _value, **kwargs):
                self.calls += 1
                callbacks.append(kwargs["config"]["callbacks"][0].thread_id)
                return _result("recovered")

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=["one", "two"]),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=FirstGraph()),
            ):
                asyncio.run(write_missions(run_dir))
            resumed = ResumeGraph()
            with (
                patch("ML.deep_research.layer2.cli.split_fact_sheet", return_value=["one", "two"]),
                patch("ML.deep_research.layer2.cli.create_chunk_agent", return_value=resumed),
            ):
                asyncio.run(write_missions(run_dir))
            record = load_json(run_dir / "run.json")
            mission = load_json(run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")

        self.assertEqual(resumed.calls, 1)
        self.assertEqual(callbacks, ["chunk-0001-attempt-1", "chunk-0002-attempt-1", "chunk-0001-attempt-2"])
        self.assertEqual([item["attempt"] for item in record["chunking"]["chunks"]], [2, 1])
        self.assertEqual(record["chunking"]["result"], "complete")
        self.assertEqual([item["fact"] for item in mission["context"]], ["recovered", "saved"])

    def test_partial_cli_reports_failure_and_returns_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            record = load_json(run_dir / "run.json")
            record["chunking"].update(
                result="partial",
                summary={"total": 1, "completed": 0, "failed": 1},
                chunks=[{
                    "index": 1, "file": "chunks/chunk_0001.json", "status": "failed",
                    "attempt": 2, "error_type": "APIConnectionError", "error": "connection failed",
                }],
            )
            write_json(run_dir / "run.json", record)
            output = io.StringIO()
            with (
                patch.dict("os.environ", {"OPENAI_API_KEY": "test"}),
                patch("ML.deep_research.layer2.cli.run_all"),
                contextlib.redirect_stdout(output),
            ):
                result = main(["--resume", str(run_dir)])

        self.assertEqual(result, 0)
        self.assertIn("published partial missions", output.getvalue())
        self.assertIn("Chunk 1 attempt 2: APIConnectionError: connection failed", output.getvalue())
        self.assertIn(f'.\\run.ps1 -Resume "{run_dir.resolve()}"', output.getvalue())

    def test_normal_run_does_not_execute_or_stamp_optional_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._run(Path(temporary))
            with (
                patch.dict("os.environ", {"OPENAI_API_KEY": "test"}),
                patch(
                    "ML.deep_research.layer2.cli.write_missions",
                    new=AsyncMock(return_value={"model_calls": 1}),
                ),
                patch("ML.deep_research.layer2.cli.run_checks") as checks,
            ):
                usage = run_all(run_dir)
            record = load_json(run_dir / "run.json")

        checks.assert_not_called()
        self.assertEqual(usage, {"model_calls": 1})
        self.assertEqual(record["status"], "complete")
        self.assertNotIn("checks", record)

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

    def test_malformed_usage_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "usage.jsonl").write_text(
                'not json\n{"input_tokens": 12, "output_tokens": 3}\n',
                encoding="utf-8",
            )
            summary = summarize_usage(run_dir)
        self.assertEqual(summary["model_calls"], 1)
        self.assertEqual(summary["input_tokens"], 12)


if __name__ == "__main__":
    unittest.main()
