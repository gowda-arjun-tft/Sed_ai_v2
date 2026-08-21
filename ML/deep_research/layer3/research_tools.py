"""Evidence tools exposed to one Layer 3 research workstream."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime, tool

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    read_text,
    slug,
    text_hash,
    write_json,
)

from .contracts import ResearchContext, SearchHit
from .retrieval import normalize_url
from .sources import SourceStore


_QUERY_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_SOURCE_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_REPORT_LOCK = threading.RLock()


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
            return [SearchHit(**item) for item in load_json(cache).get("hits", [])]
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


def partial_report_path(run_dir: Path, researcher: str) -> Path:
    """Return the durable progressive report path for one bound domain."""
    return run_dir / "domains" / f"{slug(researcher)}.partial.md"


def _report_ledger_path(run_dir: Path, researcher: str) -> Path:
    return run_dir / "domains" / ".fragments" / f"{slug(researcher)}.json"


def _render_fragments(
    fragments: list[dict[str, Any]],
    session_id: str,
) -> str:
    return "".join(
        str(item.get("markdown", ""))
        for item in fragments
        if item.get("session_id") == session_id
    )


def read_partial_report(
    run_dir: Path,
    researcher: str,
    session_id: str | None = None,
) -> str:
    """Read the visible partial or reconstruct one attempt from its ledger."""
    if session_id is not None:
        ledger = _report_ledger_path(run_dir, researcher)
        state = load_json(ledger) if ledger.is_file() else {"fragments": []}
        return _render_fragments(state.get("fragments", []), session_id)
    path = partial_report_path(run_dir, researcher)
    return read_text(path) if path.is_file() else ""


def _append_fragment(
    context: ResearchContext,
    researcher: str,
    fragment_id: str,
    markdown: str,
) -> str:
    key = fragment_id.strip()
    if not key:
        return "Report fragment rejected: fragment_id cannot be empty."
    target = partial_report_path(context.run_dir, researcher)
    ledger = _report_ledger_path(context.run_dir, researcher)
    with _REPORT_LOCK:
        state = load_json(ledger) if ledger.is_file() else {"fragments": []}
        fragments = state.get("fragments", [])
        prior = next(
            (
                item
                for item in fragments
                if item.get("session_id") == context.session_id
                and item.get("fragment_id") == key
            ),
            None,
        )
        if prior is not None and prior.get("markdown") != markdown:
            return (
                "Report fragment rejected: this fragment_id already has different "
                "content. Use a new stable fragment_id."
            )
        created = prior is None
        if created:
            fragments.append(
                {
                    "session_id": context.session_id,
                    "fragment_id": key,
                    "markdown": markdown,
                }
            )
            write_json(ledger, {"fragments": fragments})
        atomic_write_text(
            target,
            _render_fragments(fragments, context.session_id),
        )
    event_id = text_hash(
        f"append_report\n{researcher}\n{context.session_id}\n{key}"
    )
    from .usage import record_event

    record_event(
        context.run_dir,
        event_id=event_id,
        phase="report_progress",
        actor=researcher,
        session_id=context.session_id,
        detail=f"fragment_id={key}; characters={len(markdown)}",
    )
    return "Report fragment saved." if created else "Report fragment already saved."


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
    """Build four tools, binding researcher attribution and paths server-side."""

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
                lens=researcher,
                session_id=context.session_id,
            )
        except ValueError as error:
            return f"Citation rejected: {error}"

    @tool("append_report", parse_docstring=True)
    def append_report(
        fragment_id: str,
        markdown: str,
        runtime: ToolRuntime[ResearchContext, Any],
    ) -> str:
        """Durably append one progressive report fragment.

        Reusing an ID with identical Markdown is a no-op. Reusing it with
        different Markdown is rejected so checkpoint replay cannot mutate work.

        Args:
            fragment_id: A stable identifier chosen for this report fragment.
            markdown: The exact Markdown fragment to persist.
        """
        return _append_fragment(
            runtime.context,
            researcher,
            fragment_id,
            markdown,
        )

    return [search_web, read_source, cite, append_report]


__all__ = ["make_research_tools", "partial_report_path", "read_partial_report"]
