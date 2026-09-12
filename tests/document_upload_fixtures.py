"""HTTP/Files transport fakes: exercise the installed SDK without network or model calls."""

import asyncio
import json
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import default
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI

from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer3.document_uploads import upload_documents
from tests.layer3_fixtures import FakeFinder, new_run

HTTPClient = httpx.AsyncClient
PDF = b"%PDF-1.7\nOffline synthetic document with UTF-8: \xe5\x8c\xbb\xe9\x99\xa2\n%%EOF"


def entry(url="https://docs.example/report.pdf", document=True, **extra):
    """Create an ordinary source entry whose source claims must survive enrichment."""
    return {"url": url, "document": document, "description": "医院: supplied public record",
            "access": "partial", "access_note": "Summary only", **extra}


async def prepared(root, groups=None):
    """Make actual saved source responses with fake-model calls, before enabling HTTP fakes."""
    groups = groups or [[entry()], [entry()]]
    run = new_run(root, [f"domain-{i}" for i in range(len(groups))])
    fake = FakeFinder()
    fake.outputs = {f"source_finder/{i:06d}": json.dumps({"sources": rows}, ensure_ascii=False)
                    for i, rows in enumerate(groups, 1)}
    await fake.run(run)
    return run, fake


class UploadHTTP:
    """Simulate public downloads and native Files API requests with configurable failures."""

    def __init__(self):
        """Record transport calls and uploaded bytes without external services."""
        self.documents, self.files, self.downloads, self.creates = {}, {}, [], []
        self.api_calls, self.fail_create, self.gate = [], None, None

    async def handle(self, request):
        """Serve documents or Files routes, rejecting unexpected API/model endpoints."""
        if request.url.host != "api.openai.com":
            self.downloads.append(str(request.url))
            response = self.documents.get(str(request.url), (200, PDF, {"Content-Type": "application/pdf"}))
            if isinstance(response, Exception):
                raise response
            code, body, headers = response
            return httpx.Response(code, content=body, headers=headers)
        self.api_calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/v1/files":
            raw = await request.aread()
            message = BytesParser(policy=default).parsebytes(
                f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode() + raw)
            parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
            assert parts["purpose"].get_payload(decode=True) == b"user_data"
            assert set(parts) == {"purpose", "file"}  # no expiry, vector store or other fields
            name, body = parts["file"].get_filename(), parts["file"].get_payload(decode=True)
            self.creates.append(name)
            if self.fail_create == "reject":
                return httpx.Response(400, json={"error": {"message": "PRIVATE_PAYLOAD", "code": "invalid_file"}})
            file_id = f"file-offline{len(self.files) + 1}"
            info = {"id": file_id, "filename": name, "bytes": len(body), "purpose": "user_data",
                    "object": "file", "created_at": 1}
            self.files[file_id] = (info, body)
            if self.gate:
                await self.gate.wait()
            if self.fail_create == "lost_response":
                raise httpx.ReadTimeout("PRIVATE_TOKEN_AND_URL", request=request)
            return httpx.Response(200, json=info)
        if request.method == "GET" and request.url.path == "/v1/files":
            return httpx.Response(200, json={"object": "list", "has_more": False,
                                            "data": [info for info, _ in self.files.values()]})
        if request.method == "GET" and request.url.path.startswith("/v1/files/"):
            file_id = request.url.path.split("/")[3]
            if file_id not in self.files:
                return httpx.Response(404, json={"error": {"message": "absent", "code": "not_found"}})
            info, body = self.files[file_id]
            return httpx.Response(200, content=body) if request.url.path.endswith("/content") else httpx.Response(200, json=info)
        raise AssertionError(f"Unexpected API endpoint {request.method} {request.url.path}")

    @contextmanager
    def offline(self):
        """Use native SDK serialization and mock HTTP; block sockets and live discovery."""
        owner = self

        class OfflineHTTP(HTTPClient):
            """Route every request through a controlled in-memory transport."""

            def __init__(self, **kwargs):
                """Install the offline transport without replacing HTTP response behavior."""
                super().__init__(**{**kwargs, "transport": httpx.MockTransport(owner.handle)})

        def client(**kwargs):
            """Build the installed OpenAI SDK with offline runtime authentication."""
            return AsyncOpenAI(api_key="offline-key", http_client=OfflineHTTP(), **kwargs)

        with patch("httpx.AsyncClient", OfflineHTTP), patch(
            "ML.deep_research.layer3.document_uploads.AsyncOpenAI", side_effect=client
        ), patch("socket.socket.connect", side_effect=AssertionError("Network blocked")), patch(
            "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]
        ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline-key"}):
            yield

    async def run(self, run, **kwargs):
        """Execute the public upload-only entrypoint with all network effects faked."""
        with self.offline():
            await upload_documents(run, **kwargs)
        return load_json(run / "run.json")
