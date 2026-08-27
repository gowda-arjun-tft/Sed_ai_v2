from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ML.deep_research.layer2.fs import load_json, write_json
from ML.deep_research.layer2.settings import REPO_ROOT
from ML.deep_research.layer3.cli import _parser, run_all
from ML.deep_research.layer3.document_supervisor import _run_worker
from ML.deep_research.layer3.pipeline.create_run import create_run
from ML.deep_research.layer3.providers import from_run
from ML.deep_research.layer3.runner import run_research
from tests.common import create_complete_run


class DocumentExtractionPolicyTests(unittest.TestCase):
    def test_pdf_batch_range_does_not_set_a_whole_document_limit(self):
        class Converter:
            def convert(self, _path, **kwargs):
                self.kwargs = kwargs
                document = SimpleNamespace(
                    pages={1: object()},
                    export_to_dict=lambda: {},
                    export_to_markdown=lambda **_kwargs: "page 1",
                )
                return SimpleNamespace(
                    status=SimpleNamespace(value="success"), errors=[], document=document
                )

        from ML.deep_research.layer3.document_worker import _convert_docling

        converter = Converter()
        _convert_docling(converter, Path("unused.pdf"), (1, 25))
        self.assertEqual(converter.kwargs, {"page_range": (1, 25)})

    def test_docling_page_keys_remain_original_page_numbers(self):
        class Converter:
            def convert(self, _path, **_kwargs):
                document = SimpleNamespace(
                    pages={5: object(), 7: object()},
                    export_to_dict=lambda: {},
                    export_to_markdown=lambda page_no: f"page {page_no}",
                )
                return SimpleNamespace(
                    status=SimpleNamespace(value="partial_success"),
                    errors=[],
                    document=document,
                )

        from ML.deep_research.layer3.document_worker import _convert_docling

        pages, _payload, _warnings = _convert_docling(
            Converter(), Path("unused.pdf"), (5, 7)
        )

        self.assertEqual(pages, {5: "page 5", 7: "page 7"})

    def _new_run(self, root: Path, **options) -> Path:
        return create_run(
            create_complete_run(root),
            root / "l3",
            public_input_confirmed=True,
            **options,
        )

    def test_new_run_freezes_document_extraction_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._new_run(Path(temporary), ocr_languages="DE,en,de")
            run = load_json(run_dir / "run.json")
            documents_created = (run_dir / "sources" / "documents").is_dir()

        self.assertEqual(run["schema_version"], 7)
        self.assertEqual(
            run["document_extraction"],
            {
                "policy_version": 1,
                "backend": "local_docling",
                "ocr_engine": "easyocr",
                "ocr_languages": ["de", "en"],
                "max_document_bytes": 50 * 1024 * 1024,
                "max_pdf_pages": 2_000,
                "pdf_batch_pages": 25,
                "full_response_token_threshold": 16_000,
                "max_requested_pages": 30,
                "max_find_hits": 40,
                "worker_heartbeat_seconds": 10,
                "worker_stale_seconds": 60,
            },
        )
        self.assertTrue(documents_created)

    def test_ocr_language_input_is_small_and_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "at least one OCR language"):
                self._new_run(root, ocr_languages=" , ")
            with self.assertRaisesRegex(ValueError, "invalid OCR language"):
                self._new_run(root, ocr_languages="de,not a code")

        args = _parser().parse_args(
            ["--research", "runs/L2_example", "--ocr-languages", "de,en"]
        )
        self.assertEqual(args.ocr_languages, "de,en")

    def test_schema_seven_run_without_policy_still_resumes(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._new_run(Path(temporary))
            run = load_json(run_dir / "run.json")
            run.pop("document_extraction")
            write_json(run_dir / "run.json", run)
            resume = AsyncMock()
            with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch(
                "ML.deep_research.layer3.cli.run_research", resume
            ):
                asyncio.run(run_all(run_dir))

        resume.assert_awaited_once_with(run_dir, retry_failed=False)

    def test_worker_launcher_runs_on_a_selector_loop(self):
        class Process:
            pid = 123
            returncode = 0

            def communicate(self):
                return b"", b""

        policy = type("Policy", (), {"worker_heartbeat_seconds": 1, "worker_stale_seconds": 2})()
        loop = asyncio.SelectorEventLoop()
        try:
            with tempfile.TemporaryDirectory() as temporary, patch(
                "ML.deep_research.layer3.document_supervisor._worker_process",
                return_value=Process(),
            ):
                loop.run_until_complete(_run_worker(Path(temporary), "a" * 64, policy))
        finally:
            loop.close()

    def test_preflight_failure_stops_before_retriever_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._new_run(Path(temporary))
            preflight = AsyncMock(side_effect=RuntimeError("Docling unavailable"))
            with (
                patch("ML.deep_research.layer3.runner.preflight_document_worker", preflight),
                patch("ML.deep_research.layer3.runner.from_run") as retriever,
                self.assertRaisesRegex(RuntimeError, "Docling unavailable"),
            ):
                asyncio.run(run_research(run_dir))

        preflight.assert_awaited_once_with(run_dir)
        retriever.assert_not_called()

    def test_retriever_uses_frozen_limit_and_legacy_runs_keep_legacy_limit(self):
        with patch(
            "ML.deep_research.layer3.providers.openai_search.OpenAISearchRetriever"
        ) as retriever:
            from_run(
                {
                    "provider": "online",
                    "document_extraction": {
                        "policy_version": 1,
                        "max_document_bytes": 123,
                    },
                },
                Path("new-run"),
            )
            self.assertEqual(retriever.call_args.kwargs["max_document_bytes"], 123)

            from_run({"provider": "online"}, Path("legacy-run"))
            self.assertIsNone(retriever.call_args.kwargs["max_document_bytes"])

    def test_notebook_exposes_ocr_control_and_portable_source_path(self):
        notebook = json.loads(
            (REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8")
        )
        text = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook["cells"]
        )

        self.assertIn('LAYER3_OCR_LANGUAGES = "de,en"', text)
        self.assertIn("ocr_languages=selected_ocr_languages", text)
        self.assertIn('LAYER3_SOURCE_RUN_PATH = r""', text)
        self.assertIn("L3_RUN = create_layer3_run(", text)
        self.assertNotIn('rglob("L3_*")', text)


if __name__ == "__main__":
    unittest.main()
