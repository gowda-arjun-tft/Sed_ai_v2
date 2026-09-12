"""Document deduplication, enrichment, SDK recovery and non-mutating historical checks."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.publication import ObjectMembers
from ML.deep_research.layer3.document_records import REGISTRY_PATH, research_usable
from ML.deep_research.layer3.document_uploads import run_writer, upload_documents
from ML.deep_research.layer3.source_publication import publish
from tests.document_upload_fixtures import PDF, UploadHTTP, entry, prepared
from tests.layer3_fixtures import snapshot


class DocumentUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_run_all_continues_new_runs_but_not_legacy_source_only_runs(self):
        from ML.deep_research.layer3.cli import run_all
        for enabled in (True, False):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as tmp:
                run, fake = await prepared(Path(tmp), [[entry()]])
                record = load_json(run / "run.json")
                record.pop("research")  # Historical preparation capability remains unchanged.
                write_json(run / "run.json", record)
                if not enabled:
                    record = load_json(run / "run.json")
                    record.pop("document_uploads")
                    write_json(run / "run.json", record)
                http = UploadHTTP()
                with http.offline(), patch("ML.deep_research.layer3.cli.run_research", side_effect=fake.run):
                    await run_all(run)
                self.assertEqual(len(http.creates), int(enabled))
                self.assertEqual(len(fake.calls), 1)

    async def test_successful_upload_survives_receipt_save_interruption(self):
        import ML.deep_research.layer3.document_uploads as module
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp), [[entry()]])
            http = UploadHTTP()
            real_write = module.write_json
            crashed = False

            def interrupt(path, data):
                nonlocal crashed
                if path.name == "document_uploads.json" and any(
                    item.get("status") == "complete" for item in data.get("files", {}).values()
                ):
                    crashed = True
                if crashed:
                    raise OSError("simulated process disk failure")
                real_write(path, data)

            with patch.object(module, "write_json", side_effect=interrupt), self.assertRaises(OSError):
                await http.run(run)
            self.assertEqual(len(http.creates), 1)
            record = await http.run(run)
            self.assertEqual(len(http.creates), 1)
            self.assertEqual(record["status"], "complete")

    async def test_url_and_byte_duplicates_upload_once_and_preserve_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = entry("https://docs.example/alias.pdf")
            webpage = entry("https://docs.example/page", False)
            run, fake = await prepared(Path(tmp), [[entry(), webpage], [entry(), other]])
            raw_before = snapshot(run / "_internal/trace/responses")
            http = UploadHTTP()
            record = await http.run(run)
            self.assertEqual(len(http.creates), 1)
            self.assertEqual(len(http.downloads), 2)
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["document_uploads"]["counts"]["candidate_entries"], 3)
            for domain in record["domains"]:
                rows = load_json(run / domain["output_path"])["sources"]
                for row in rows:
                    self.assertEqual(row["access"], "partial")
                    self.assertEqual(row["access_note"], "Summary only")
                    self.assertEqual(row["upload"], row["document"])
                    self.assertEqual(row["file_id"], "file-offline1" if row["document"] else None)
                    self.assertEqual(row["upload_status"], "uploaded" if row["document"] else "not_applicable")
                self.assertIn('\n  "sources": [\n', (run / domain["output_path"]).read_text(encoding="utf-8"))
            self.assertEqual(raw_before, snapshot(run / "_internal/trace/responses"))
            await http.run(run)
            publish(run)
            self.assertEqual(len(http.creates), 1)
            self.assertEqual(len(http.downloads), 2)
            self.assertTrue(list((run / "_internal/trace/presentation_history").rglob("*.json")))
            self.assertFalse(list(run.rglob("*.pdf")))

    async def test_failure_preserves_siblings_and_retry_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = "https://docs.example/failure.pdf"
            run, _ = await prepared(Path(tmp), [[entry(bad), entry()]])
            http = UploadHTTP()
            http.documents[bad] = (403, b"PRIVATE_BODY", {})
            record = await http.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["discovery_status"], "complete")
            rows = load_json(run / record["domains"][0]["output_path"])["sources"]
            self.assertFalse(rows[0]["upload"])
            self.assertEqual(rows[0]["upload_status"], "failed")
            self.assertTrue(rows[1]["upload"])
            http.documents.pop(bad)
            await http.run(run)
            self.assertEqual(http.downloads.count(bad), 1)
            record = await http.run(run, retry_failed=True)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(http.creates), 1)
            log = (run / "run.log").read_text(encoding="utf-8")
            self.assertIn("document_failed", log)
            for private in ("https://", "PRIVATE_BODY", "offline-key", "Summary only"):
                self.assertNotIn(private, log)

    async def test_lost_response_recovers_by_remote_hash_without_reupload(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp), [[entry()]])
            http = UploadHTTP()
            http.fail_create = "lost_response"
            record = await http.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(http.creates), 1)  # SDK retry is disabled on create.
            row = load_json(run / record["domains"][0]["output_path"])["sources"][0]
            self.assertEqual(row["upload_status"], "uncertain")
            http.fail_create = None
            record = await http.run(run, retry_failed=True)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(http.creates), 1)
            self.assertIn(("GET", "/v1/files/file-offline1/content"), http.api_calls)

    async def test_uncertain_missing_or_mismatching_remote_file_is_not_retried(self):
        for state in ("missing", "different_bytes", "duplicate"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                run, _ = await prepared(Path(tmp), [[entry()]])
                http = UploadHTTP()
                http.fail_create = "lost_response"
                await http.run(run)
                info, body = http.files["file-offline1"]
                if state == "missing":
                    http.files.clear()
                elif state == "different_bytes":
                    http.files["file-offline1"] = (info, b"x" * len(body))
                else:
                    http.files["file-other"] = ({**info, "id": "file-other"}, body)
                record = await http.run(run, retry_failed=True)
                self.assertEqual(len(http.creates), 1)
                self.assertEqual(record["document_uploads"]["status"], "partial")

    async def test_future_research_eligibility_uses_access_or_verified_upload(self):
        def row(**values):
            values.setdefault("url", "https://example.test/source")
            return ObjectMembers(values.items())

        self.assertTrue(research_usable(row(document=True, access="failed",
                                             upload_status="uploaded", file_id="file-1")))
        self.assertFalse(research_usable(row(document=True, access="readable",
                                              upload_status="failed", file_id=None)))
        self.assertFalse(research_usable(row(document=True, access="readable",
                                              upload_status="uncertain", file_id=None)))
        self.assertTrue(research_usable(row(document=False, access="readable",
                                             upload_status="not_applicable", file_id=None)))
        self.assertTrue(research_usable(row(document=None, access="partial",
                                             upload_status="not_applicable", file_id=None)))
        self.assertFalse(research_usable(row(document=False, access="blocked",
                                              upload_status="not_applicable", file_id=None)))
        self.assertFalse(research_usable(row(document=1, access="readable",
                                              upload_status="not_applicable", file_id=None)))
        self.assertFalse(research_usable(ObjectMembers([
            ("document", False), ("access", "readable"),
            ("upload_status", "not_applicable"), ("file_id", None),
        ])))

    async def test_deleted_successful_file_is_not_reported_as_uploaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp))
            http = UploadHTTP()
            await http.run(run)
            http.files.clear()
            record = await http.run(run, retry_failed=True)
            self.assertEqual(len(http.creates), 1)
            for domain in record["domains"]:
                row = load_json(run / domain["output_path"])["sources"][0]
                self.assertFalse(row["upload"])
                self.assertEqual(row["upload_status"], "failed")

    async def test_cancelled_upload_keeps_intent_releases_writer_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp), [[entry()]])
            http = UploadHTTP()
            http.gate = asyncio.Event()
            task = asyncio.create_task(http.run(run))
            for _ in range(100):
                if http.creates:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(len(http.creates), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(load_json(run / REGISTRY_PATH)["status"], "interrupted")
            http.gate = None
            record = await http.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(http.creates), 1)

    async def test_rejected_upload_can_retry_but_never_repeats_source_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, fake = await prepared(Path(tmp), [[entry()]])
            http = UploadHTTP()
            http.fail_create = "reject"
            await http.run(run)
            await http.run(run)
            self.assertEqual(len(http.creates), 1)
            record = load_json(run / "run.json")
            self.assertEqual(load_json(run / record["domains"][0]["output_path"])["sources"][0]["upload_status"],
                             "failed")
            http.fail_create = None
            await http.run(run, retry_failed=True)
            self.assertEqual(len(http.creates), 2)
            self.assertEqual(len(fake.calls), 1)

    async def test_prior_run_opt_in_and_historical_or_consent_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp))
            record = load_json(run / "run.json")
            record.pop("document_uploads")
            write_json(run / "run.json", record)
            http = UploadHTTP()
            await http.run(run)
            self.assertTrue(load_json(run / "run.json")["document_uploads"]["policy"]["enabled"])
            for change in ({"schema_version": 8}, {"public_input_confirmed": False}):
                write_json(run / "run.json", {**record, **change})
                before = snapshot(run)
                with self.assertRaises(ValueError):
                    await http.run(run)
                self.assertEqual(before, snapshot(run))

    async def test_native_file_writer_lock_and_missing_auth_precede_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp))
            with run_writer(run):
                with self.assertRaisesRegex(RuntimeError, "active writer"):
                    with run_writer(run):
                        self.fail("second writer entered")
            before = snapshot(run)
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), self.assertRaises(RuntimeError):
                await upload_documents(run)
            self.assertEqual(before, snapshot(run))

    async def test_publication_failure_rebuilds_from_successful_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp), [[entry()]])
            http = UploadHTTP()
            with patch("ML.deep_research.layer3.document_uploads.publish", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    await http.run(run)
            self.assertEqual(load_json(run / REGISTRY_PATH)["counts"]["uploaded_files"], 1)
            self.assertEqual(load_json(run / "run.json")["status"], "failed")
            await http.run(run)
            self.assertEqual(len(http.creates), 1)
