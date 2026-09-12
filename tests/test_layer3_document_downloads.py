"""Offline download safety, representation checks and lossless JSON projection."""

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from ML.deep_research.layer2.backend.fs import load_json, text_hash, write_json
from ML.deep_research.layer3.document_download import _download, document_extension, download_document
from ML.deep_research.layer3.document_records import REGISTRY_PATH, UPLOAD_POLICY, candidate
from ML.deep_research.layer3.source_publication import parse_json, pretty_json
from tests.document_upload_fixtures import PDF, UploadHTTP, entry, prepared
from tests.layer3_fixtures import FakeFinder, new_run, snapshot


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_validation_blocks_private_destinations_before_request(self):
        calls = []

        def respond(request):
            calls.append(str(request.url))
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/private.pdf"})

        def resolve(host, *args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 80))]

        with patch("socket.getaddrinfo", side_effect=resolve), patch(
            "socket.socket.connect", side_effect=AssertionError("Network disabled")
        ), tempfile.TemporaryFile() as handle:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                with self.assertRaisesRegex(ValueError, "unsafe_or_unresolvable"):
                    await _download(client, "https://docs.example/report.pdf", handle, 1000)
            self.assertEqual(len(calls), 1)

    async def test_declared_actual_empty_and_invalid_document_responses(self):
        cases = [({"Content-Length": "1001"}, PDF, 1000), ({}, PDF, 2), ({}, b"", 1000),
                 ({"Content-Type": "text/html"}, b"<html>blocked</html>", 1000),
                 ({"Content-Type": "application/pdf"}, b"<!DOCTYPE html>login", 1000),
                 ({"Content-Type": "application/pdf"}, b"not a PDF", 1000)]
        for headers, body, limit in cases:
            with self.subTest(headers=headers, limit=limit), tempfile.TemporaryFile() as handle:
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, headers=headers, content=body)
                )) as client:
                    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), self.assertRaises(ValueError):
                        await _download(client, "https://docs.example/a.pdf", handle, limit)

    async def test_partial_download_retry_discards_bytes_and_closes_temporary_handle(self):
        attempts = []

        class BrokenStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"partial " * 10000
                raise httpx.ReadTimeout("not logged")

        def respond(request):
            attempts.append(request)
            return httpx.Response(200, stream=BrokenStream()) if len(attempts) == 1 else httpx.Response(
                200, content=PDF, headers={"Content-Type": "application/pdf"})

        client_class = httpx.AsyncClient

        def client(**kwargs):
            return client_class(**kwargs, transport=httpx.MockTransport(respond))

        with patch("httpx.AsyncClient", side_effect=client), patch(
            "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]
        ):
            async with download_document("https://docs.example/a.pdf", UPLOAD_POLICY,
                                         logging.getLogger("offline.download")) as (handle, info):
                self.assertEqual(handle.read(), PDF)
                self.assertEqual(info["bytes"], len(PDF))
            self.assertTrue(handle.closed)
        self.assertEqual(len(attempts), 2)

    async def test_download_attempt_bound_and_supported_representations(self):
        http = UploadHTTP()
        url = "https://docs.example/a.pdf"
        http.documents[url] = (503, b"server unavailable", {})
        with http.offline(), self.assertRaises(httpx.HTTPStatusError):
            async with download_document(url, UPLOAD_POLICY, logging.getLogger("offline.download")):
                self.fail("unexpected document")
        self.assertEqual(len(http.downloads), 3)
        for body, mime, url, extension in (
            (PDF, "application/octet-stream", "https://e.test/download?id=3", ".pdf"),
            (b"a,b\n1,2", "text/csv", "https://e.test/report.csv", ".csv"),
            (b"{\\rtf1 some text}", "application/rtf", "https://e.test/report.rtf", ".rtf"),
        ):
            self.assertEqual(document_extension(io.BytesIO(body), mime, url), extension)

    async def test_ambiguous_and_unusual_sources_are_preserved_without_upload(self):
        raw = ('{"extra":1,"extra":2,"sources":['
               '{"url":"https://a.test/a.pdf","url":"https://b.test/b.pdf","document":true},'
               '{"url":"https://a.test/a.pdf","document":true,"document":false},'
               '{"document":1,"extra":{"医院":[1,null]}},'
               '{"document":null,"upload":true,"file_id":"file-forged"},7]}')
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["one"])
            fake = FakeFinder()
            fake.outputs["source_finder/000001"] = raw
            record = await fake.run(run)
            before = snapshot(run / "_internal/trace/responses")
            http = UploadHTTP()
            record = await http.run(run)
            result = (run / record["domains"][0]["output_path"]).read_text(encoding="utf-8")
            self.assertEqual(result.count('"extra":'), 3)
            self.assertEqual(result.count('"url":'), 3)
            self.assertEqual(result.count('"upload": false'), 4)
            self.assertEqual(result.count('"upload_status": "failed"'), 2)
            self.assertEqual(result.count('"upload_status": "not_applicable"'), 2)
            self.assertNotIn("file-forged", result)
            self.assertIn('"医院"', result)
            self.assertEqual(before, snapshot(run / "_internal/trace/responses"))
            self.assertFalse(http.downloads or http.creates)
            self.assertEqual(record["status"], "complete")
            self.assertGreater(load_json(run / REGISTRY_PATH)["counts"]["observations"], 0)

    async def test_unreadable_or_empty_objects_do_not_gate_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["a", "b", "c"])
            fake = FakeFinder()
            fake.outputs = {f"source_finder/{i:06d}": raw for i, raw in enumerate(["{}", "", "bad"], 1)}
            await fake.run(run)
            http = UploadHTTP()
            record = await http.run(run)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(fake.calls), 3)
            self.assertFalse(http.creates)

    def test_url_normalization_preserves_meaningful_queries_and_rejects_credentials(self):
        for url in ("https://user:secret@e.test/a.pdf", "https://e.test:wrong/a.pdf", "file:///a.pdf"):
            self.assertIsNone(candidate(parse_json(json.dumps(entry(url))))[0])
        normalized, _ = candidate(parse_json(json.dumps(entry("HTTPS://E.TEST:443/a.pdf?part=2#page=3"))))
        self.assertEqual(normalized, "https://e.test/a.pdf?part=2")
        raw = '{"sources":[{"document":true,"url":"https://e.test/a.pdf"}],"sources":[]}'
        self.assertIn('"upload": false', pretty_json(raw, {"urls": {}, "files": {}}))
        self.assertIn('"upload_status": "failed"', pretty_json(raw, {"urls": {}, "files": {}}))
