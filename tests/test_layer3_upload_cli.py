"""Upload-only CLI dispatch and frozen policy without model or HTTP execution."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer3.cli import main
from tests.layer3_fixtures import new_run, snapshot


class UploadCLITests(unittest.TestCase):
    def test_upload_only_dispatches_exact_run_and_explicit_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            before = snapshot(run)
            with patch("ML.deep_research.layer3.cli.load_dotenv_key"), patch(
                "ML.deep_research.layer3.cli.upload_documents", new_callable=AsyncMock
            ) as upload, patch("ML.deep_research.layer3.cli.run_all", side_effect=AssertionError("No discovery")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--upload-documents", str(run), "--retry-failed"]), 0)
                upload.assert_awaited_once_with(run.resolve(), retry_failed=True)
            self.assertEqual(before, snapshot(run))
            policy = load_json(run / "run.json")["document_uploads"]["policy"]
            self.assertEqual(policy["purpose"], "user_data")
            self.assertEqual(policy["retention"], "until_deleted")

    def test_check_only_rejects_upload_action_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            before = snapshot(run)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--check-only", str(run), "--upload-documents", str(run)])
            self.assertEqual(before, snapshot(run))

    def test_powershell_exposes_the_same_upload_only_action(self):
        script = (Path(__file__).resolve().parents[1] / "run.ps1").read_text(encoding="utf-8")
        self.assertIn("[string]$UploadDocumentsL3", script)
        self.assertIn("@('--upload-documents', $UploadDocumentsL3)", script)
