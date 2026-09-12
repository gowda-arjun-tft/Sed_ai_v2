"""Actual Files/Responses serialization, shared uploads and document-read limitations offline."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.run_log import operational_logger
from ML.deep_research.layer3.document_records import REGISTRY_PATH
from ML.deep_research.layer3.domain_tools import make_tools
from ML.deep_research.layer3.research_documents import ResearchDocuments
from ML.deep_research.layer3.research_run import create_research_run, eligible_sources
from ML.deep_research.layer3.source_publication import parse_json, publish
from tests.document_upload_fixtures import UploadHTTP, entry, prepared
from tests.layer3_fixtures import snapshot
from tests.test_layer3_research_budget import new_budget


class ResearchHTTP(UploadHTTP):
    """Extend the existing upload fake only with Responses file-input answers."""

    def __init__(self):
        """Record exact file-read requests for token/format boundary assertions."""
        super().__init__()
        self.reads = []

    async def handle(self, request):
        """Verify distinct native search and tool-free document request serialization."""
        if request.url.path == "/v1/responses":
            value = json.loads(request.content)
            self.reads.append(value)
            if "tools" in value:
                assert value["tools"][0]["type"] == "web_search"
                assert value["tool_choice"] == {"type": "web_search"}
                annotations = [{"type": "url_citation", "url": "https://official.example/report",
                                "title": "Official report", "start_index": 0, "end_index": 2}]
            else:
                assert value["input"][0]["content"][1]["type"] == "input_file"
                assert value["input"][0]["content"][1]["file_id"] in self.files
                annotations = []
            assert not set(value) & {"response_format", "max_output_tokens"}
            assert "format" not in value["text"]
            return httpx.Response(200, json={"id": "resp-offline", "object": "response", "status": "completed",
                "created_at": 1, "model": "gpt-5.6-luna", "output": [{"type": "message", "role": "assistant",
                "id": "msg-offline", "status": "completed", "content": [{"type": "output_text", "annotations": annotations,
                "text": "医院 — proposed rule; exception remains. Section 2."}]}],
                "usage": {"input_tokens": 300, "output_tokens": 25, "total_tokens": 325}})
        return await super().handle(request)


class ResearchDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_document_counter_cache_and_failed_dispatch_share_one_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp))
            http = ResearchHTTP()
            await http.run(run)
            record = load_json(run / "run.json")
            root = run / "_internal/counter-test"
            budget = new_budget(root)
            with http.offline(), operational_logger(run) as logger:
                async with AsyncOpenAI(api_key="offline", http_client=httpx.AsyncClient()) as client:
                    docs = ResearchDocuments(run, record, client, logger)
                    domain = record["domains"][0]
                    docs.authorize(domain["key"], parse_json(eligible_sources(run, record, domain)))
                    search, _, read = make_tools(root, record, domain["key"], docs, budget)
                    await search.ainvoke({"query": "Exact question"})
                    await read.ainvoke({"reference": "file-offline1", "questions": "Exact conditions?"})
                    await search.ainvoke({"query": "Exact question"})
                    await read.ainvoke({"reference": "file-offline1", "questions": "Exact conditions?"})
            self.assertEqual(budget.used, 2)
            self.assertEqual([c["kind"] for c in budget.state["calls"]], ["search", "document"])
            self.assertIn("logical call 1 of 80", http.reads[0]["input"])
            self.assertIn("logical call 2 of 80", http.reads[1]["instructions"])

    async def test_link_copies_ids_and_preserves_parent_then_authorizes_reads_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, _ = await prepared(root)
            http = ResearchHTTP()
            await http.run(parent)
            before = snapshot(parent)
            run = create_research_run(parent, root / "runs", public_input_confirmed=True)
            self.assertEqual(snapshot(parent), before)
            record = load_json(run / "run.json")
            with http.offline(), operational_logger(run) as logger:
                async with AsyncOpenAI(api_key="offline", http_client=httpx.AsyncClient()) as client:
                    docs = ResearchDocuments(run, record, client, logger)
                    key = record["domains"][0]["key"]
                    docs.authorize(key, parse_json(eligible_sources(run, record, record["domains"][0])))
                    evidence = run / "_internal/test-evidence"
                    answer = await docs.read(key, "file-offline1", "What conditions?", evidence)
                    self.assertIn("exception", answer)
                    self.assertEqual(await docs.read(key, "file-offline1", "What conditions?", evidence), answer)
                    self.assertEqual(len(http.reads), 1)
                    next(evidence.glob("documents/*/complete.json")).unlink()
                    self.assertEqual(await docs.read(key, "file-offline1", "What conditions?", evidence), answer)
                    self.assertEqual(len(http.reads), 1)  # saved provider response repairs publication, not content
                    with self.assertRaisesRegex(ValueError, "authorized"):
                        await docs.read("other-domain", "file-offline1", "What?", evidence)
                    self.assertEqual(len(http.creates), 1)
            self.assertEqual(snapshot(parent), before)

    async def test_search_transport_cache_and_document_limitations(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp))
            http = ResearchHTTP()
            record = load_json(run / "run.json")
            root = run / "_internal/research-test"
            with http.offline(), operational_logger(run) as logger:
                async with AsyncOpenAI(api_key="offline", http_client=httpx.AsyncClient()) as client:
                    docs = ResearchDocuments(run, record, client, logger)
                    search, _, read_document = make_tools(root, record, "domain", docs)
                    first = await search.ainvoke({"query": "Exact question 医院"})
                    self.assertEqual(json.loads(first)[0]["url"], "https://official.example/report")
                    next((root / "evidence/search").glob("*/hits.json")).unlink()
                    await search.ainvoke({"query": "Exact question 医院"})
                    self.assertEqual(len(http.reads), 1)
                    denied = await read_document.ainvoke({"reference": "file-not-authorized", "questions": "Question"})
                    self.assertIn("not authorized", denied)
                    self.assertEqual(len(http.reads), 1)

    async def test_new_urls_deduplicate_across_domains_and_survive_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = await prepared(Path(tmp), [[entry(document=False)], [entry(document=False)]])
            http = ResearchHTTP()
            record = load_json(run / "run.json")
            with http.offline(), operational_logger(run) as logger:
                async with AsyncOpenAI(api_key="offline", http_client=httpx.AsyncClient()) as client:
                    docs = ResearchDocuments(run, record, client, logger)
                    answers = await asyncio.gather(*[
                        docs.read(f"domain-{i}", url, "Question", run / f"_internal/domain-{i}") for i, url in enumerate(
                            ("https://docs.example/new.pdf", "https://docs.example/alias.pdf"))])
                    self.assertEqual(len(answers), 2)
                    self.assertEqual(len(http.creates), 1)
                    self.assertEqual(len(http.downloads), 2)
                    fresh = ResearchDocuments(run, record, client, logger)
                    await fresh.read("domain-0", "file-offline1", "Question", run / "_internal/domain-0")
                    self.assertEqual(len(http.reads), 2)
            receipt = load_json(run / REGISTRY_PATH)
            publish(run)
            self.assertEqual(load_json(run / REGISTRY_PATH), receipt)

    async def test_failed_prepared_documents_are_not_retried_and_uncertain_upload_is_reconciled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = "https://docs.example/missing.pdf"
            run, _ = await prepared(root, [[entry(bad)]])
            http = ResearchHTTP()
            http.documents[bad] = (404, b"missing", {})
            await http.run(run)
            before = len(http.downloads)
            record = load_json(run / "run.json")
            with http.offline(), operational_logger(run) as logger:
                async with AsyncOpenAI(api_key="offline", http_client=httpx.AsyncClient()) as client:
                    docs = ResearchDocuments(run, record, client, logger)
                    with self.assertRaisesRegex(ValueError, "previously failed"):
                        await docs.read("domain", bad, "Questions", run / "_internal/evidence")
                    self.assertEqual(len(http.downloads), before)
                    http.fail_create = "lost_response"
                    with self.assertRaises(Exception):
                        await docs.read("domain", "https://docs.example/new.pdf", "Questions", run / "_internal/evidence")
                    self.assertEqual(len(http.creates), 1)
                    # A stored intent is not a definite prepared-source failure: explicitly reconcile it.
                    item = docs.registry["urls"]["https://docs.example/new.pdf"]
                    self.assertEqual(docs.registry["files"][item["sha256"]]["status"], "uncertain")
                    http.fail_create = None
                    await docs.read("domain", "https://docs.example/new.pdf", "Questions", run / "_internal/evidence")
                    self.assertEqual(len(http.creates), 1)


if __name__ == "__main__":
    unittest.main()
