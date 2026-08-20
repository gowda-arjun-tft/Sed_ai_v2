"""The researcher's tools.

Every tool here does what it is asked and reports what happened. None of them
refuses, second-guesses, rate-limits or edits the researcher. There is no search
budget, no obligation to review a result before searching again, no requirement
to search before finishing, no citation verification and no check on the wording
of a report.

The researcher decides what to search, what to open, what to quote, how it grades
a source, when it has enough, and what to write.
"""

from __future__ import annotations

from pathlib import Path

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from ML.deep_research.layer2.fs import load_json, write_json

from .contracts import ResearchContext, ResearchState, SearchHit
from .sources import SourceStore


def tool_command(
    runtime: ToolRuntime[ResearchContext, ResearchState],
    content: str,
    **updates: object,
) -> Command:
    return Command(
        update={
            **updates,
            "messages": [
                ToolMessage(content, tool_call_id=runtime.tool_call_id or "tool")
            ],
        }
    )


def session_result_path(run_dir: Path, session_id: str) -> Path:
    return run_dir / "session_results" / f"{session_id}.json"


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
    if cache.is_file():
        return [SearchHit(**item) for item in load_json(cache).get("hits", [])]
    hits = await context.retriever.search(query)
    write_json(cache, {"query": query, "hits": [_hit_dict(hit) for hit in hits]})
    return hits


@tool(parse_docstring=True)
async def search_web(
    query: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> Command:
    """Search the public web.

    Search as often as you find useful. There is no query budget and no
    requirement to open anything before searching again.

    Args:
        query: The search query.
    """
    state = runtime.state
    context = runtime.context
    store = SourceStore(context.run_dir)
    sequence = int(state.get("query_count", 0)) + 1

    hits = await _search(context, query)
    store.record_query(
        session_id=context.session_id,
        sequence=sequence,
        agent=context.agent,
        lens=context.lens,
        query=query,
        new_sources=len(hits),
    )

    listing = "\n".join(
        f"- {hit.hit_id}: {hit.title} — {hit.url}" for hit in hits
    ) or "This query returned no results."
    return tool_command(runtime, listing, query_count=sequence)


@tool(parse_docstring=True)
async def read_source(
    url: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> Command:
    """Fetch and store a page, and return its text.

    Any URL is accepted, whether or not a search returned it.

    Args:
        url: The address to fetch.
    """
    context = runtime.context
    try:
        document = await context.retriever.fetch(url)
        store = SourceStore(context.run_dir)
        record = store.store(document)
        text = store.source_text(record["source_sha256"])
        content = (
            f"SOURCE {record['source_sha256']}\nURL {document.url}\n\n{text}"
            if text is not None
            else (
                f"Stored {record['source_sha256']} ({document.content_type}, "
                f"{len(document.body)} bytes). No text extraction was available "
                "for this content type."
            )
        )
    except Exception as error:
        content = f"Fetching {url} failed: {type(error).__name__}: {error}"
    return tool_command(runtime, content)


@tool(parse_docstring=True)
def skip_source(
    url: str,
    reason: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> Command:
    """Note a result you have decided not to open.

    Args:
        url: The address you are passing over.
        reason: Why it is not worth opening.
    """
    context = runtime.context
    SourceStore(context.run_dir).record_skip(
        session_id=context.session_id,
        agent=context.agent,
        lens=context.lens,
        url=url,
        reason=reason,
    )
    return tool_command(runtime, f"Noted. Skipped {url}.")


@tool(parse_docstring=True)
def cite(
    source_id: str,
    exact_quote: str,
    tier: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> str:
    """Record a citation and return its marker for your report.

    Args:
        source_id: The source hash returned by read_source.
        exact_quote: The words you are relying on.
        tier: How you grade this source, in your own words.
    """
    context = runtime.context
    return SourceStore(context.run_dir).record_citation(
        source_id=source_id,
        quote=exact_quote,
        tier=tier,
        agent=context.agent,
        lens=context.lens,
        round_name=context.round_name,
        session_id=context.session_id,
    )


@tool(parse_docstring=True)
def finish_round(
    report: str,
    status: str,
    reason: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> Command:
    """Store your report and end this round.

    Args:
        report: Your report, exactly as you want it kept.
        status: How this round ended, in your own words.
        reason: Anything further worth recording. May be empty.
    """
    context = runtime.context
    write_json(
        session_result_path(context.run_dir, context.session_id),
        {"status": status, "reason": reason, "report": report},
    )
    return tool_command(runtime, "Stored.")
