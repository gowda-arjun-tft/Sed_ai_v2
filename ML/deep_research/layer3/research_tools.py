"""Web evidence tools exposed to one STORM lens or citation verifier."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain.tools import ToolRuntime, tool
from langgraph.types import interrupt

from ML.deep_research.layer2.fs import (
    load_json,
    write_json,
)

from .contracts import ResearchContext, SearchHit
from .document_extraction import (
    MAX_DOCUMENT_ATTEMPTS,
    PendingDocument,
    ensure_document_job,
    extraction_policy,
    process_pass_through,
    render_document,
)
from .retrieval import normalize_url
from .sources import SourceStore


_QUERY_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_SOURCE_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}


def _lock(table: dict[tuple[int, str], asyncio.Lock], key: str) -> asyncio.Lock:
    """Return a loop-local lock so concurrent checkpoint replays share one effect."""
    loop_key = (id(asyncio.get_running_loop()), key)
    lock = table.get(loop_key)
    if lock is None:
        lock = asyncio.Lock()
        table[loop_key] = lock
    return lock


def _hit_dict(hit: SearchHit) -> dict[str, str]:
    return {
        "hit_id": hit.hit_id,
        "url": hit.url,
        "title": hit.title,
        "publisher": hit.publisher,
        "snippet": hit.snippet,
    }


async def _search(
    context: ResearchContext, query: str, researcher: str
) -> list[SearchHit]:
    store = SourceStore(context.run_dir)
    cache = store.cache_path(query)
    lock = _lock(_QUERY_LOCKS, str(cache.resolve()))
    async with lock:
        if cache.is_file():
            try:
                return [SearchHit(**item) for item in load_json(cache).get("hits", [])]
            except (OSError, TypeError, ValueError):
                pass
        hits = await context.retriever.search(
            query, actor=researcher, session_id=context.session_id
        )
        write_json(cache, {"query": query, "hits": [_hit_dict(hit) for hit in hits]})
        return hits


def _source_result(store: SourceStore, record: dict[str, Any]) -> str:
    source_id = str(record["source_sha256"])
    text = store.source_text(source_id)
    if text is not None:
        return f"SOURCE {source_id}\nURL {record['url']}\n\n{text}"
    return (
        f"Stored {source_id} ({record['content_type']}, {record['bytes']} bytes). "
        "No canonical text is available for verification; use a readable source "
        "or disclose this limitation."
    )


async def _read(
    context: ResearchContext,
    url: str,
    pages: str | None = None,
    find: str | None = None,
) -> str | PendingDocument:
    store = SourceStore(context.run_dir)
    lock = _lock(
        _SOURCE_LOCKS,
        f"{context.run_dir.resolve()}::{normalize_url(url)}",
    )
    async with lock:
        record = store.record_for_url(url)
        if record is None:
            document = await context.retriever.fetch(url)
            record = store.store(document)
        policy = extraction_policy(context.run_dir)
        if policy is None:
            return _source_result(store, record)
        if int(record.get("bytes", 0)) > policy.max_document_bytes:
            return (
                f"Stored {record['source_sha256']}, but it exceeds the "
                f"{policy.max_document_bytes // (1024 * 1024)} MiB document limit."
            )
        manifest = ensure_document_job(context.run_dir, record, policy)
        if manifest is None:
            return _source_result(store, record)
        source_id = str(record["source_sha256"])
        if manifest.get("kind") == "pass_through" and manifest.get("status") != "complete":
            manifest = process_pass_through(context.run_dir, source_id)
        if (
            manifest.get("status") == "failed"
            and manifest.get("retryable", True)
            and int(manifest.get("attempt", 0)) < MAX_DOCUMENT_ATTEMPTS
        ):
            return PendingDocument(source_id, str(record["url"]))
        if manifest.get("status") in {"complete", "failed"}:
            return render_document(
                context.run_dir,
                source_id,
                policy,
                pages=pages,
                find=find,
                source_url=str(record["url"]),
            )
        return PendingDocument(source_id, str(record["url"]))


def _format_hit(hit: SearchHit) -> str:
    values = [
        f"HIT {hit.hit_id}",
        f"Title: {hit.title}",
        f"URL: {hit.url}",
    ]
    if hit.publisher:
        values.append(f"Publisher: {hit.publisher}")
    values.append(f"Snippet: {hit.snippet}")
    return "\n".join(values)


def make_research_tools(researcher: str) -> list[Any]:
    """Build the two evidence tools, binding attribution server-side."""

    @tool("search_web", parse_docstring=True)
    async def search_web(
        query: str,
        runtime: ToolRuntime[ResearchContext, Any],
    ) -> str:
        """Search the public web for candidate sources and discovery snippets.

        Snippets identify pages to open; they are not evidence for a claim.

        Args:
            query: The research query to send to the search provider.
        """
        context = runtime.context
        hits = await _search(context, query, researcher)
        SourceStore(context.run_dir).record_query(
            session_id=context.session_id,
            agent=context.agent,
            lens=researcher,
            query=query,
            new_sources=len(hits),
        )
        return "\n\n".join(_format_hit(hit) for hit in hits) or (
            "This query returned no results."
        )

    @tool("read_source", parse_docstring=True)
    async def read_source(
        url: str,
        runtime: ToolRuntime[ResearchContext, Any],
        pages: str | None = None,
        find: str | None = None,
    ) -> str:
        """Open one public URL and return retained canonical text with its source ID.

        Use this result, not a search snippet, as evidence for a claim. An unreadable
        source returns an explicit limitation instead of inferred content. Large
        documents return a map; request pages or find text without downloading again.

        Args:
            url: The HTTP or HTTPS source address.
            pages: Optional page number or range, for example ``3-7``.
            find: Optional exact text to locate in retained document pages.
        """
        try:
            result = await _read(runtime.context, url, pages, find)
        except Exception as error:
            return f"Fetching {url} failed: {type(error).__name__}: {error}"
        # LangGraph interrupts must escape the broad operational error boundary.
        if isinstance(result, PendingDocument):
            interrupt(result.payload())
            try:
                resumed = await _read(runtime.context, url, pages, find)
            except Exception as error:
                return f"Reading retained source {url} failed: {type(error).__name__}: {error}"
            if isinstance(resumed, PendingDocument):
                return (
                    f"Stored {resumed.source_id}, but document extraction did not reach "
                    "a terminal state after resume."
                )
            return resumed
        return result

    return [search_web, read_source]
