"""Three focused research capabilities; file tools and planning are supplied natively."""

import asyncio
import json

from langchain.tools import tool

from ML.deep_research.layer2.backend.fs import text_hash, write_json
from ML.deep_research.layer2.backend.run_log import log_failure
from .providers.openai_search import _fetch, _hits
from .research_documents import DocumentLimitation, recovered_provider, save_provider
from .research_memory import check_input
from .research_budget import CallUnavailable
from .retrieval import normalize_url
from .source_finder import request_options
from .sources import SourceStore


def make_tools(root, record, domain, documents, budget=None):
    """Close over run/domain ownership so models cannot select another domain or host folder."""
    evidence = root / "evidence"
    store = SourceStore(evidence)
    locks = {}

    @tool
    async def search_web(query: str) -> str:
        """Search for relevant public sources. Snippets are discovery; read underlying evidence."""
        options = {**request_options(record), "model": record["model"], "store": False,
                   "reasoning": {"effort": record["reasoning_effort"]}}
        request = "Find sources for the exact research question, with citations.\n\n" + query
        check_input([request], record, options=options, ceiling=record["web_search"]["input_token_limit"])
        key = text_hash(json.dumps([query, options], sort_keys=True))
        cache = evidence / "search" / key
        async with locks.setdefault(key, asyncio.Lock()):
            if (cache / "hits.json").exists():
                return (cache / "hits.json").read_text(encoding="utf-8")
            response = recovered_provider(cache, phase="search")

            def prepare(note, final):
                """Include the counter in the exact search input and its accounting."""
                value = request + ("\n\n" + note if note else "")
                check_input([value], record, options=options, ceiling=record["web_search"]["input_token_limit"])
                write_json(cache / "request.json", {"input": value, "options": options})
                return value

            async def invoke(value):
                """Dispatch through the execution-owned SDK client."""
                return await documents.client.responses.create(input=value, **options)

            try:
                if response is None:
                    response = (await budget.call("search", prepare, invoke) if budget
                                else await invoke(prepare("", False)))
            except CallUnavailable as error:
                return str(error)
            except Exception as error:
                log_failure(documents.logger, "search_failed", error, domain=domain)
                return f"Search unavailable ({type(error).__name__}); investigate alternatives or disclose the gap."
            save_provider(cache, response, phase="search")
            hits = [vars(hit) for hit in _hits(response)]
            write_json(cache / "hits.json", hits)
            return json.dumps(hits, ensure_ascii=False)

    @tool
    async def read_source(url: str) -> str:
        """Read a public URL and retain canonical text with source references; report access limitations."""
        key = text_hash(normalize_url(url))
        async with locks.setdefault(key, asyncio.Lock()):
            saved = store.record_for_url(url)
            if saved is None:
                if budget:
                    budget.require_research()
                try:
                    document = await asyncio.to_thread(_fetch, url)
                except Exception as error:
                    write_json(evidence / "access" / f"{key}.json", {"url": url, "error_type": type(error).__name__})
                    log_failure(documents.logger, "source_read_failed", error, domain=domain)
                    return f"Source could not be read ({type(error).__name__}); no evidence was inferred."
                saved = store.store(document)
            text = store.source_text(saved["source_sha256"])
            if text is None:
                return "Source bytes retained but no readable text. Try read_document for a document or find an alternative."
            path = "/evidence/" + saved["text_path"]
            return f"Source: {saved['url']}\nSaved: {path}\n\n{text}"

    @tool
    async def read_document(reference: str, questions: str) -> str:
        """Read a domain-authorized file ID or new public document URL, answering specific questions."""
        key = text_hash(json.dumps([reference, questions]))
        async with locks.setdefault(key, asyncio.Lock()):
            try:
                return await documents.read(domain, reference, questions, evidence, budget=budget)
            except (OSError, PermissionError):
                raise  # Preserve storage failures; do not disguise lost records as inaccessible sources.
            except Exception as error:
                reason = str(error) if isinstance(error, (DocumentLimitation, CallUnavailable)) else type(error).__name__
                write_json(evidence / "document_limitations" / f"{key}.json",
                           {"reference": reference, "questions": questions, "limitation": reason})
                log_failure(documents.logger, "document_read_limitation", error, domain=domain)
                return f"Document unavailable ({reason}); use alternative evidence or disclose the limitation."

    return [search_web, read_source, read_document]
