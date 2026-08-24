"""Web evidence tools exposed to one STORM lens or citation verifier."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain.tools import ToolRuntime, tool

from ML.deep_research.layer2.fs import (
    load_json,
    write_json,
)

from .contracts import ResearchContext, SearchHit
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


async def _read(context: ResearchContext, url: str) -> str:
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
        return _source_result(store, record)


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
        """Search the public web and return source URLs.

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
    ) -> str:
        """Fetch, retain, and read one public source.

        Args:
            url: The HTTP or HTTPS source address.
        """
        try:
            return await _read(runtime.context, url)
        except Exception as error:
            return f"Fetching {url} failed: {type(error).__name__}: {error}"

    return [search_web, read_source]


__all__ = ["make_research_tools"]
