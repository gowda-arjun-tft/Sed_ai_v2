from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ML.deep_research.layer2.fs import write_json
from ML.deep_research.layer3.contracts import Document
from ML.deep_research.layer3.document_extraction import (
    ensure_document_job,
    extraction_kind,
    extraction_policy,
    process_pass_through,
    render_document,
)
from ML.deep_research.layer3.document_worker import process_document_job
from ML.deep_research.layer3.sources import SourceStore


def _run(root: Path, *, full_tokens: int = 16_000) -> Path:
    run_dir = root / "run"
    run_dir.mkdir()
    write_json(
        run_dir / "run.json",
        {
            "document_extraction": {
                "policy_version": 1,
                "backend": "local_docling",
                "ocr_engine": "easyocr",
                "ocr_languages": ["de", "en"],
                "max_document_bytes": 50 * 1024 * 1024,
                "max_pdf_pages": 2_000,
                "pdf_batch_pages": 25,
                "full_response_token_threshold": full_tokens,
                "max_requested_pages": 30,
                "max_find_hits": 40,
                "worker_heartbeat_seconds": 1,
                "worker_stale_seconds": 2,
            }
        },
    )
    return run_dir


def _store(run_dir: Path, content_type: str, body: bytes, url: str) -> dict:
    return SourceStore(run_dir).store(
        Document(url=url, content_type=content_type, body=body, fetched_at="2026-08-25T00:00:00Z")
    )


class DocumentArtifactTests(unittest.TestCase):
    def test_strong_pdf_suffix_overrides_generic_text_mime(self):
        from ML.deep_research.layer3.document_worker import _input_suffix

        self.assertEqual(
            extraction_kind("text/plain", "https://example.test/report.pdf"),
            "docling",
        )
        self.assertEqual(
            _input_suffix({"content_type": "application/pdf", "url": "https://example.test/wrong.docx"}),
            ".pdf",
        )
        self.assertEqual(
            _input_suffix({"content_type": "application/octet-stream", "url": "https://example.test/photo.jpeg"}),
            ".jpg",
        )
        self.assertEqual(extraction_kind("image/png", "https://example.test/image"), "docling")
        self.assertIsNone(extraction_kind("image/gif", "https://example.test/image"))

    def test_text_uses_same_manifest_and_supports_map_pages_and_find(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary), full_tokens=2)
            policy = extraction_policy(run_dir)
            assert policy is not None
            record = _store(
                run_dir,
                "text/plain",
                b"alpha\nneedle evidence\nsplit\nphrase\nomega\n",
                "https://example.test/a.txt",
            )
            manifest = ensure_document_job(run_dir, record, policy)
            self.assertEqual(manifest["kind"], "pass_through")
            process_pass_through(run_dir, record["source_sha256"])

            mapped = render_document(run_dir, record["source_sha256"], policy)
            page = render_document(run_dir, record["source_sha256"], policy, pages="1")
            found = render_document(run_dir, record["source_sha256"], policy, find="needle")
            split = render_document(
                run_dir, record["source_sha256"], policy, find="split phrase"
            )

        self.assertIn("Document map: 1 pages", mapped)
        self.assertIn("## Page 1", page)
        self.assertIn("needle evidence", found)
        self.assertIn("split phrase", split)

    def test_page_response_is_bounded_and_names_remaining_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary), full_tokens=20)
            policy = extraction_policy(run_dir)
            assert policy is not None
            source_id = "c" * 64
            root = run_dir / "sources" / "documents" / source_id
            for number in range(1, 4):
                (root / "pages").mkdir(parents=True, exist_ok=True)
                (root / "pages" / f"{number:04d}.md").write_text("evidence " * 20, encoding="utf-8")
            write_json(
                root / "manifest.json",
                {
                    "source_id": source_id,
                    "url": "https://example.test/large.pdf",
                    "status": "complete",
                    "total_pages": 3,
                },
            )
            result = render_document(run_dir, source_id, policy, pages="1-3")

        self.assertLess(len(result), 500)
        self.assertIn("CONTINUE", result)
        self.assertIn("pages='2,3'", result)

    def test_pdf_batches_resume_without_repeating_completed_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            policy = extraction_policy(run_dir)
            assert policy is not None
            record = _store(run_dir, "application/pdf", b"fake pdf", "https://example.test/a.pdf")
            ensure_document_job(run_dir, record, policy)
            calls: list[tuple[int, int]] = []

            def fail_second(_converter, _path, page_range):
                assert page_range is not None
                calls.append(page_range)
                if page_range[0] == 26:
                    raise RuntimeError("worker stopped")
                return (
                    {number: f"page {number}" for number in range(page_range[0], page_range[1] + 1)},
                    {"range": page_range},
                    [],
                )

            with (
                patch("ML.deep_research.layer3.document_worker._pdf_pages", return_value=52),
                patch("ML.deep_research.layer3.document_worker._docling_converter", return_value=object()),
                patch("ML.deep_research.layer3.document_worker._convert_docling", side_effect=fail_second),
                self.assertRaisesRegex(RuntimeError, "worker stopped"),
            ):
                process_document_job(run_dir, record["source_sha256"])

            calls.clear()

            def succeed(_converter, _path, page_range):
                assert page_range is not None
                calls.append(page_range)
                return (
                    {number: f"page {number}" for number in range(page_range[0], page_range[1] + 1)},
                    {"range": page_range},
                    [],
                )

            with (
                patch("ML.deep_research.layer3.document_worker._pdf_pages", return_value=52),
                patch("ML.deep_research.layer3.document_worker._docling_converter", return_value=object()) as converter,
                patch("ML.deep_research.layer3.document_worker._convert_docling", side_effect=succeed),
            ):
                result = process_document_job(run_dir, record["source_sha256"])

            self.assertEqual(calls, [(26, 50), (51, 52)])
            converter.assert_called_once_with(["de", "en"])
            self.assertEqual(result["status"], "complete")
            self.assertTrue((run_dir / "sources" / "documents" / record["source_sha256"] / "pages" / "0052.md").is_file())

    def test_pdf_page_limit_is_checked_before_docling_starts(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            policy = extraction_policy(run_dir)
            assert policy is not None
            record = _store(run_dir, "application/pdf", b"fake pdf", "https://example.test/huge.pdf")
            ensure_document_job(run_dir, record, policy)
            with (
                patch("ML.deep_research.layer3.document_worker._pdf_pages", return_value=2_001),
                patch("ML.deep_research.layer3.document_worker._docling_converter") as converter,
                self.assertRaisesRegex(RuntimeError, "2001 pages"),
            ):
                process_document_job(run_dir, record["source_sha256"])

        converter.assert_not_called()

    def test_missing_pdf_page_retries_only_that_page_and_publishes_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            policy = extraction_policy(run_dir)
            assert policy is not None
            record = _store(run_dir, "application/pdf", b"fake pdf", "https://example.test/partial.pdf")
            ensure_document_job(run_dir, record, policy)
            calls = []

            def partial(_converter, _path, page_range):
                calls.append(page_range)
                pages = {1: "page 1"} if page_range == (1, 2) else {}
                return pages, {"range": page_range}, ["page 2 failed"]

            with (
                patch("ML.deep_research.layer3.document_worker._pdf_pages", return_value=2),
                patch("ML.deep_research.layer3.document_worker._docling_converter", return_value=object()),
                patch(
                    "ML.deep_research.layer3.document_worker._convert_docling",
                    side_effect=partial,
                ),
            ):
                result = process_document_job(run_dir, record["source_sha256"])

            root = run_dir / "sources" / "documents" / record["source_sha256"]
            missing_text = (root / "pages" / "0002.md").read_text(encoding="utf-8")
            batch_exists = (root / "batches" / "0001-0002" / "docling.json").exists()
            rendered = render_document(run_dir, record["source_sha256"], policy)

        self.assertEqual(calls, [(1, 2), (2, 2), (2, 2)])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["result"], "partial")
        self.assertEqual(result["missing_pages"], [2])
        self.assertIn("Page unavailable", missing_text)
        self.assertIn("EXTRACTION PARTIAL", rendered)
        self.assertIn("Unavailable pages: 2", rendered)
        self.assertTrue(batch_exists)

    def test_docling_partial_status_returns_evidence_and_warning(self):
        document = SimpleNamespace(
            pages={1: object()},
            export_to_dict=lambda: {"partial": True},
            export_to_markdown=lambda **_kwargs: "page 1",
        )

        class Converter:
            def convert(self, *_args, **_kwargs):
                return SimpleNamespace(
                    status=SimpleNamespace(value="partial_success"),
                    errors=[SimpleNamespace(error_message="page failed")],
                    document=document,
                )

        from ML.deep_research.layer3.document_worker import _convert_docling

        pages, payload, warnings = _convert_docling(
            Converter(), Path("unused.pdf"), (1, 1)
        )

        self.assertEqual(pages, {1: "page 1"})
        self.assertEqual(payload, {"partial": True})
        self.assertEqual(warnings, ["page failed"])

    def test_zero_usable_pdf_pages_remains_a_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = _run(Path(temporary))
            policy = extraction_policy(run_dir)
            assert policy is not None
            record = _store(
                run_dir, "application/pdf", b"fake pdf", "https://example.test/empty.pdf"
            )
            ensure_document_job(run_dir, record, policy)
            empty = ({}, {"empty": True}, [])
            with (
                patch("ML.deep_research.layer3.document_worker._pdf_pages", return_value=2),
                patch("ML.deep_research.layer3.document_worker._docling_converter", return_value=object()),
                patch("ML.deep_research.layer3.document_worker._convert_docling", return_value=empty) as convert,
                self.assertRaisesRegex(RuntimeError, "no usable page text"),
            ):
                process_document_job(run_dir, record["source_sha256"])

        self.assertEqual(convert.call_count, 3)

if __name__ == "__main__":
    unittest.main()
