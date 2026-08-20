from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.fs import load_json, now_iso, read_text, slug
from ML.deep_research.layer3.cli import main
from ML.deep_research.layer3.contracts import Document, QuestionSet, SessionSpec
from ML.deep_research.layer3.mission import load_inputs
from ML.deep_research.layer3.pipeline.run_checks import run_checks
from ML.deep_research.layer3.register import add_sixth_row, read_rows, researcher_id
from ML.deep_research.layer3.research_tools import session_result_path
from ML.deep_research.layer3.retrieval import validate_public_url
from ML.deep_research.layer3.sessions import commit_session_result, second_round_path
from ML.deep_research.layer3.settings import AGENT_NAMES, LENSES
from ML.deep_research.layer3.sources import SourceStore, load_jsonl

from tests.common import create_complete_l3_run, create_complete_run


class Layer3PipelineTests(unittest.TestCase):
    def test_sqlite_checkpointer_and_harness_construct_without_api_call(self):
        import asyncio
        from typing import TypedDict

        from langgraph.graph import END, START, StateGraph
        from ML.deep_research.layer3.llm import create_research_agent
        from ML.deep_research.layer3.sessions import checkpoint_saver

        class CounterState(TypedDict):
            count: int

        builder = StateGraph(CounterState)
        builder.add_node("increment", lambda state: {"count": state["count"] + 1})
        builder.add_edge(START, "increment")
        builder.add_edge("increment", END)

        async def scenario(root: Path) -> None:
            config = {"configurable": {"thread_id": "durable-test-thread"}}
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}):
                async with checkpoint_saver(root) as saver:
                    graph = create_research_agent("skeptic", "", saver)
                    self.assertIn("tools", graph.get_graph().nodes)
                    counter = builder.compile(checkpointer=saver)
                    self.assertEqual((await counter.ainvoke({"count": 1}, config))["count"], 2)
                async with checkpoint_saver(root) as saver:
                    counter = builder.compile(checkpointer=saver)
                    self.assertEqual((await counter.aget_state(config)).values["count"], 2)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            asyncio.run(scenario(root))
            self.assertGreater((root / "checkpoints.sqlite3").stat().st_size, 0)

    def test_research_tools_complete_one_offline_evidence_round(self):
        import asyncio

        from langchain.tools import ToolRuntime

        from ML.deep_research.layer2.fs import text_hash
        from ML.deep_research.layer3.contracts import ResearchContext
        from ML.deep_research.layer3.providers.fixture import FixtureRetriever
        from ML.deep_research.layer3.research_tools import (
            cite,
            finish_round,
            read_source,
            search_web,
        )

        async def scenario(root: Path, run_dir: Path) -> None:
            query = "public building standard"
            url = "https://example.com/public-standard"
            fixtures = root / "tool-fixtures"
            (fixtures / "queries").mkdir(parents=True)
            (fixtures / "pages").mkdir()
            (fixtures / "queries" / f"{text_hash(query)}.json").write_text(
                json.dumps([{"url": url, "title": "Public standard"}]),
                encoding="utf-8",
            )
            (fixtures / "pages" / f"{text_hash(url)}.bin").write_bytes(
                b"<p>Verified public fact.</p>"
            )
            mission, _ = load_inputs(run_dir)[0]
            context = ResearchContext(
                run_dir=run_dir,
                agent=mission["agent"],
                lens="skeptic",
                round_name="first",
                session_id="tool-session",
                retriever=FixtureRetriever(fixtures),
            )
            state = {
                "messages": [],
                "query_count": 0,
            }

            def runtime(call_id: str):
                return ToolRuntime(
                    state=state,
                    context=context,
                    config={},
                    stream_writer=lambda _: None,
                    tool_call_id=call_id,
                    store=None,
                )

            def apply(command) -> None:
                state.update(
                    {key: value for key, value in command.update.items() if key != "messages"}
                )

            apply(await search_web.coroutine(query=query, runtime=runtime("search-1")))
            apply(await read_source.coroutine(url=url, runtime=runtime("read-1")))
            source_id = load_jsonl(run_dir / "sources" / "index.jsonl")[-1]["source_sha256"]
            marker = cite.func(
                source_id=source_id,
                exact_quote="Verified public fact.",
                tier="1",
                runtime=runtime("cite-1"),
            )
            apply(await search_web.coroutine(query=query, runtime=runtime("search-2")))
            apply(
                finish_round.func(
                    report=f"Verified result {marker}",
                    status="answered",
                    reason="",
                    runtime=runtime("finish-1"),
                )
            )
            self.assertTrue(session_result_path(run_dir, "tool-session").is_file())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = create_complete_l3_run(root)
            asyncio.run(scenario(root, run_dir))

    def test_fixture_run_builds_the_complete_run_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            checks = run_checks(run_dir)
            self.assertEqual(sum(ok for _, _, ok, _ in checks), len(checks))
            self.assertEqual(len(list((run_dir / "lenses").glob("*/*.md"))), 70)
            self.assertEqual(len(list((run_dir / "questions").glob("*/*.md"))), 70)
            self.assertEqual(len(list((run_dir / "research").glob("*.md"))), 14)
            self.assertEqual(len(read_rows(run_dir)), 84)
            self.assertTrue((run_dir / "checkpoints.sqlite3").is_file())

    def test_completed_layer3_run_remains_checkable(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            self.assertEqual(main(["--check-only", str(run_dir)]), 0)

    def test_public_fixture_cli_runs_without_api_key(self):
        from ML.deep_research.layer2.pipeline.run_checks import run_checks as run_l2_checks

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l2_run = create_complete_run(root)
            self.assertEqual(sum(ok for _, _, ok, _ in run_l2_checks(l2_run)), 19)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            with patch("ML.deep_research.layer3.cli.RUNS_DIR", root / "l3-runs"):
                self.assertEqual(
                    main(["--research", str(l2_run), "--fixtures", str(fixtures)]),
                    0,
                )
            runs = list((root / "l3-runs").glob("L3_*"))
            self.assertEqual(len(runs), 1)
            recorded = load_json(runs[0] / "run.json")["checks"]
            self.assertEqual(recorded["failed"], 0)
            self.assertEqual(recorded["passed"], recorded["run"])

    def test_second_round_is_written_beside_the_first_and_never_into_it(self):
        """The first round is never reopened, so it cannot be corrupted."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            mission, definition = load_inputs(run_dir)[0]
            lens = next(iter(LENSES))
            row = next(
                item
                for item in read_rows(run_dir)
                if item["row_id"] == researcher_id(mission["agent"], lens)
            )
            target = run_dir / "lenses" / slug(mission["agent"]) / f"{lens}.md"
            original = target.read_bytes()
            session_result_path(run_dir, row["second_thread_id"]).write_text(
                json.dumps(
                    {
                        "status": "cannot be answered",
                        "reason": "No new fixture evidence.",
                        "report": "No new fixture evidence.\n## Second round\n",
                    }
                ),
                encoding="utf-8",
            )
            spec = SessionSpec(
                agent=mission["agent"],
                lens=lens,
                round_name="second",
                thread_id=row["second_thread_id"],
                target=target,
                mission=mission,
                definition=definition,
                questions=("What changed?",),
            )
            commit_session_result(run_dir, spec)
            self.assertEqual(target.read_bytes(), original)
            second = second_round_path(target)
            self.assertTrue(second.is_file())
            # Stored byte for byte, heading and all.
            self.assertEqual(
                second.read_text(encoding="utf-8"),
                "No new fixture evidence.\n## Second round\n",
            )

    def test_sixth_row_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_l3_run(Path(temporary))
            run = load_json(run_dir / "run.json")
            first = add_sixth_row(run_dir, run["run_id"], AGENT_NAMES[0], "Engineer")
            second = add_sixth_row(run_dir, run["run_id"], AGENT_NAMES[0], "Engineer")
            self.assertEqual(first["row_id"], second["row_id"])
            self.assertEqual(
                sum(item["lens"] == "Engineer" for item in read_rows(run_dir)),
                1,
            )

    def test_question_set_has_no_field_for_attribution(self):
        """Attribution is prevented by shape, not by inspecting wording."""
        self.assertEqual(set(QuestionSet.model_fields), set(LENSES))


class Layer3EvidenceTests(unittest.TestCase):
    def test_citations_are_recorded_as_given_and_are_idempotent(self):
        """Nothing verifies a citation. It is stored exactly as supplied."""
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            store = SourceStore(run_dir)
            record = store.store(
                Document(
                    url="https://example.com/report",
                    content_type="text/html; charset=utf-8",
                    body=b"<html><script>ignore</script><p>Verified public fact.</p></html>",
                    fetched_at=now_iso(),
                )
            )
            values = dict(
                source_id=record["source_sha256"],
                quote="Verified public fact.",
                tier="1",
                agent=AGENT_NAMES[0],
                lens="skeptic",
                round_name="first",
                session_id="session-1",
            )
            marker = store.record_citation(**values)
            store.record_citation(**values)
            self.assertEqual(marker, f"[source:{record['source_sha256']}]")
            self.assertEqual(len(store.citations()), 1)

            # A quote absent from the page, an unusual grade, and a source with
            # no extracted text are all accepted without complaint.
            binary = store.store(
                Document(
                    url="https://example.com/file.pdf",
                    content_type="application/pdf",
                    body=b"%PDF-1.4 test",
                    fetched_at=now_iso(),
                )
            )
            store.record_citation(
                source_id=binary["source_sha256"],
                quote="a quote that appears nowhere in the source",
                tier="mixed provenance",
                agent=AGENT_NAMES[0],
                lens="skeptic",
                round_name="first",
                session_id="session-2",
            )
            self.assertEqual(len(store.citations()), 2)

    def test_query_log_replay_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SourceStore(Path(temporary))
            values = dict(
                session_id="s1",
                sequence=1,
                agent=AGENT_NAMES[0],
                lens="academic",
                query="public building standard",
            )
            store.record_query(**values)
            store.record_query(**values)
            records = load_jsonl(Path(temporary) / "sources" / "queries.jsonl")
            self.assertEqual(len(records), 1)

    def test_the_fetcher_still_refuses_internal_addresses(self):
        """The one guard kept: it protects the network, not the model.

        Nothing here constrains what the researcher may search for, quote or
        conclude. It stops the fetcher being pointed at infrastructure that is
        not on the public web.
        """
        with self.assertRaisesRegex(ValueError, "non-public"):
            validate_public_url("http://127.0.0.1/admin")
        with self.assertRaisesRegex(ValueError, "non-public"):
            validate_public_url("http://169.254.169.254/latest/meta-data/")


if __name__ == "__main__":
    unittest.main()
