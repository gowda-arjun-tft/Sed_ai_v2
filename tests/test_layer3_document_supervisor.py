from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ML.deep_research.layer2.fs import load_json, write_json
from ML.deep_research.layer3.contracts import Document, ResearchContext
from ML.deep_research.layer3.document_extraction import PendingDocument, manifest_path
from ML.deep_research.layer3.document_supervisor import process_document_interrupts
from ML.deep_research.layer3.research_tools import _read, make_research_tools

from tests.test_layer3_document_extraction import _run


class DocumentSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_bytes_reuse_extraction_but_report_the_requested_url(self):
        class Retriever:
            async def fetch(self, url):
                return Document(
                    url=url,
                    content_type="text/plain",
                    body=b"same retained evidence",
                    fetched_at="2026-08-25T00:00:00Z",
                )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            context = ResearchContext(run_dir, "agent", "session", Retriever())
            await _read(context, "https://first.example/evidence.txt")
            second = await _read(context, "https://second.example/evidence.txt")
            documents = list((run_dir / "sources" / "documents").iterdir())

        self.assertEqual(len(documents), 1)
        self.assertIn("URL https://second.example/evidence.txt", second)

    async def test_tool_rechecks_the_manifest_after_interrupt_resume(self):
        tool = next(item for item in make_research_tools("academic") if item.name == "read_source")
        context = ResearchContext(Path("unused"), "agent", "session", object())
        pending = PendingDocument("a" * 64, "https://example.test/a.pdf")
        with (
            patch(
                "ML.deep_research.layer3.research_tools._read",
                new=AsyncMock(side_effect=[pending, "ready evidence"]),
            ),
            patch(
                "ML.deep_research.layer3.research_tools.interrupt",
                return_value={"status": "complete"},
            ) as pause,
        ):
            result = await tool.coroutine(
                url=pending.url,
                runtime=SimpleNamespace(context=context),
                pages=None,
                find=None,
            )

        pause.assert_called_once_with(pending.payload())
        self.assertEqual(result, "ready evidence")

    async def test_supervisor_returns_terminal_resume_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "b" * 64
            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "pending", "error": ""},
            )

            async def finish(_run_dir, _source_id, *_args):
                manifest = load_json(manifest_path(run_dir, source_id))
                manifest["status"] = "complete"
                write_json(manifest_path(run_dir, source_id), manifest)

            interrupt = SimpleNamespace(
                id="interrupt-1",
                value={"type": "document_extraction", "source_id": source_id},
            )
            with patch(
                "ML.deep_research.layer3.document_supervisor._run_worker",
                side_effect=finish,
            ):
                result = await process_document_interrupts(run_dir, [interrupt])

        self.assertEqual(result["interrupt-1"]["status"], "complete")

    async def test_worker_failure_stops_after_three_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "d" * 64
            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "pending"},
            )
            item = SimpleNamespace(
                id="failure",
                value={"type": "document_extraction", "source_id": source_id},
            )
            with patch(
                "ML.deep_research.layer3.document_supervisor._run_worker",
                new=AsyncMock(side_effect=RuntimeError("process crashed")),
            ) as worker:
                result = await process_document_interrupts(run_dir, [item])
            manifest = load_json(manifest_path(run_dir, source_id))

        self.assertEqual(result["failure"]["status"], "failed")
        self.assertEqual(manifest["error"], "process crashed")
        self.assertEqual(manifest["attempt"], 3)
        self.assertEqual(worker.await_count, 3)

    async def test_failed_job_below_limit_retries_but_exhausted_job_does_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "c" * 64
            item = SimpleNamespace(
                id="retry",
                value={"type": "document_extraction", "source_id": source_id},
            )

            async def finish(_run_dir, _source_id, *_args):
                manifest = load_json(manifest_path(run_dir, source_id))
                manifest.update(status="complete", attempt=2)
                write_json(manifest_path(run_dir, source_id), manifest)

            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "failed", "attempt": 1},
            )
            with patch(
                "ML.deep_research.layer3.document_supervisor._run_worker",
                side_effect=finish,
            ) as worker:
                result = await process_document_interrupts(run_dir, [item])
            self.assertEqual(result["retry"]["status"], "complete")
            worker.assert_awaited_once()

            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "failed", "attempt": 3},
            )
            with patch(
                "ML.deep_research.layer3.document_supervisor._run_worker",
                new=AsyncMock(),
            ) as exhausted:
                result = await process_document_interrupts(run_dir, [item])

        self.assertEqual(result["retry"]["status"], "failed")
        exhausted.assert_not_awaited()

    async def test_live_worker_is_waited_for_before_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "e" * 64
            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "running", "worker_pid": 123},
            )

            async def finish(_run_dir, _source_id, *_args):
                manifest = load_json(manifest_path(run_dir, source_id))
                manifest["status"] = "complete"
                write_json(manifest_path(run_dir, source_id), manifest)

            item = SimpleNamespace(id="live", value={"type": "document_extraction", "source_id": source_id})
            with (
                patch("ML.deep_research.layer3.document_supervisor._pid_is_alive", side_effect=[True, False]),
                patch("ML.deep_research.layer3.document_supervisor._heartbeat_is_fresh", return_value=True),
                patch("ML.deep_research.layer3.document_supervisor.asyncio.sleep", new=AsyncMock()) as sleep,
                patch("ML.deep_research.layer3.document_supervisor._run_worker", side_effect=finish) as worker,
            ):
                result = await process_document_interrupts(run_dir, [item])

        sleep.assert_awaited_once()
        worker.assert_awaited_once()
        self.assertEqual(result["live"]["status"], "complete")

    async def test_stale_worker_is_terminated_before_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "f" * 64
            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "running", "worker_pid": 123, "attempt": 1},
            )

            async def finish(_run_dir, _source_id, *_args):
                manifest = load_json(manifest_path(run_dir, source_id))
                manifest["status"] = "complete"
                write_json(manifest_path(run_dir, source_id), manifest)

            item = SimpleNamespace(id="stale", value={"type": "document_extraction", "source_id": source_id})
            with (
                patch("ML.deep_research.layer3.document_supervisor._pid_is_alive", side_effect=[True, False]),
                patch("ML.deep_research.layer3.document_supervisor._heartbeat_is_fresh", return_value=False),
                patch("ML.deep_research.layer3.document_supervisor._terminate_pid", return_value=True) as terminate,
                patch("ML.deep_research.layer3.document_supervisor.asyncio.sleep", new=AsyncMock()),
                patch("ML.deep_research.layer3.document_supervisor._run_worker", side_effect=finish) as worker,
            ):
                result = await process_document_interrupts(run_dir, [item])

        terminate.assert_called_once_with(123)
        worker.assert_awaited_once()
        self.assertEqual(result["stale"]["status"], "complete")

    async def test_unstoppable_stale_worker_fails_without_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            source_id = "9" * 64
            write_json(
                manifest_path(run_dir, source_id),
                {"source_id": source_id, "status": "running", "worker_pid": 123},
            )
            item = SimpleNamespace(id="stale", value={"type": "document_extraction", "source_id": source_id})
            with (
                patch("ML.deep_research.layer3.document_supervisor._pid_is_alive", return_value=True),
                patch("ML.deep_research.layer3.document_supervisor._heartbeat_is_fresh", return_value=False),
                patch("ML.deep_research.layer3.document_supervisor._terminate_pid", return_value=False),
                patch("ML.deep_research.layer3.document_supervisor._run_worker", new=AsyncMock()) as worker,
            ):
                result = await process_document_interrupts(run_dir, [item])

        self.assertEqual(result["stale"]["status"], "failed")
        self.assertIn("could not be terminated", result["stale"]["error"])
        worker.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
