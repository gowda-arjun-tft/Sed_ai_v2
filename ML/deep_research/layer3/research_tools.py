"""Evidence tools exposed to one Layer 3 research lens."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain.tools import ToolRuntime, tool

from ML.deep_research.layer2.fs import load_json, write_json

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
        "snippet": hit.snippet,
    }


async def _search(context: ResearchContext, query: str) -> list[SearchHit]:
    store = SourceStore(context.run_dir)
    cache = store.cache_path(query)
    lock = _lock(_QUERY_LOCKS, str(cache.resolve()))
    async with lock:
        if cache.is_file():
            return [SearchHit(**item) for item in load_json(cache).get("hits", [])]
        hits = await context.retriever.search(query)
        write_json(cache, {"query": query, "hits": [_hit_dict(hit) for hit in hits]})
        return hits


def _source_result(store: SourceStore, record: dict[str, Any]) -> str:
    source_id = str(record["source_sha256"])
    text = store.source_text(source_id)
    if text is not None:
        return f"SOURCE {source_id}\nURL {record['url']}\n\n{text}"
    return (
        f"Stored {source_id} ({record['content_type']}, {record['bytes']} bytes). "
        "This source has no canonical text and cannot be cited."
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


def make_research_tools(lens: str) -> list[Any]:
    """Build the three tools for a lens, binding attribution outside the model."""

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
        hits = await _search(context, query)
        SourceStore(context.run_dir).record_query(
            session_id=context.session_id,
            agent=context.agent,
            lens=lens,
            query=query,
            new_sources=len(hits),
        )
        return "\n".join(
            f"- {hit.hit_id}: {hit.title} — {hit.url}" for hit in hits
        ) or "This query returned no results."

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

    @tool("cite", parse_docstring=True)
    def cite(
        source_id: str,
        exact_quote: str,
        tier: int,
        runtime: ToolRuntime[ResearchContext, Any],
    ) -> str:
        """Verify and record an exact quotation, returning its citation marker.

        Args:
            source_id: The SHA-256 source identifier returned by read_source.
            exact_quote: Words copied from the retained canonical source text.
            tier: Evidence tier from 1 (strongest) through 4 (weakest).
        """
        context = runtime.context
        try:
            return SourceStore(context.run_dir).record_citation(
                source_id=source_id,
                quote=exact_quote,
                tier=tier,
                agent=context.agent,
                lens=lens,
                session_id=context.session_id,
            )
        except ValueError as error:
            return f"Citation rejected: {error}"

    return [search_web, read_source, cite]


__all__ = ["make_research_tools"]
