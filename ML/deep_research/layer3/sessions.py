from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    text_hash,
    write_json,
)

from .contracts import ResearchContext, SessionSpec
from .llm import create_research_agent
from .prompts import mission_message
from .register import increment_attempts, read_rows, researcher_id, update_row
from .research_tools import session_result_path
from .settings import RECURSION_LIMIT, WORKERS
from .sources import SourceStore, load_jsonl
from .usage import record_agent_usage


@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    path = run_dir / "checkpoints.sqlite3"
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        await saver.setup()
        yield saver


def second_round_path(target: Path) -> Path:
    """Where a second round is written.

    Its own file, so nothing is ever spliced into or split out of the text the
    researcher wrote. The first round is never reopened, so it cannot be
    corrupted and there is nothing to hash-check.
    """
    return target.with_name(f"{target.stem}.second{target.suffix}")


def _counts(run_dir: Path, session_id: str) -> tuple[int, int]:
    queries = [
        item
        for item in load_jsonl(run_dir / "sources" / "queries.jsonl")
        if item.get("session_id") == session_id
    ]
    citations = [
        item
        for item in load_jsonl(run_dir / "sources" / "citations.jsonl")
        if item.get("session_id") == session_id
    ]
    return len({item.get("source_sha256") for item in citations}), len(queries)


def commit_session_result(run_dir: Path, spec: SessionSpec) -> None:
    """Write the report exactly as the researcher stored it."""
    result = load_json(session_result_path(run_dir, spec.thread_id))
    report = str(result["report"])
    status = str(result["status"])
    reason = str(result.get("reason", ""))
    row_id = researcher_id(spec.agent, spec.lens)
    sources, queries = _counts(run_dir, spec.thread_id)
    spec.target.parent.mkdir(parents=True, exist_ok=True)
    if spec.round_name == "first":
        atomic_write_text(spec.target, report)
        update_row(
            run_dir,
            row_id,
            first_status=status,
            first_at=now_iso(),
            first_sources=sources,
            first_queries=queries,
            first_hash=text_hash(report),
            first_detail=reason,
            detail=reason,
        )
        return
    atomic_write_text(second_round_path(spec.target), report)
    registered = next(
        (row for row in read_rows(run_dir) if row["row_id"] == row_id), {}
    )
    update_row(
        run_dir,
        row_id,
        second_status=status,
        second_at=now_iso(),
        second_questions=len(spec.questions),
        second_detail=reason,
        detail="; ".join(filter(None, (registered.get("first_detail", ""), reason))),
    )


def _record_failure(run_dir: Path, spec: SessionSpec, reason: str) -> None:
    """Record that a session did not produce a report.

    Nothing is written in the researcher's place. The register carries the
    failure; no invented artefact stands in for work that never happened.
    """
    field = "first_status" if spec.round_name == "first" else "second_status"
    detail = "first_detail" if spec.round_name == "first" else "second_detail"
    update_row(
        run_dir,
        researcher_id(spec.agent, spec.lens),
        **{field: "failed", detail: reason, "detail": reason},
    )


async def run_online_sessions(
    run_dir: Path,
    specs: list[SessionSpec],
    retriever: Any,
) -> None:
    if not specs:
        return
    semaphore = asyncio.Semaphore(WORKERS)
    async with checkpoint_saver(run_dir) as saver:
        keys = {(spec.lens, spec.focus) for spec in specs}
        agents = {key: create_research_agent(key[0], key[1], saver) for key in keys}

        async def run_one(spec: SessionSpec) -> None:
            async with semaphore:
                row_id = researcher_id(spec.agent, spec.lens)
                context = ResearchContext(
                    run_dir=run_dir,
                    agent=spec.agent,
                    lens=spec.lens,
                    round_name=spec.round_name,
                    session_id=spec.thread_id,
                    retriever=retriever,
                )
                field = "first_status" if spec.round_name == "first" else "second_status"
                increment_attempts(run_dir, row_id)
                update_row(run_dir, row_id, **{field: "running"})
                try:
                    result = await agents[(spec.lens, spec.focus)].ainvoke(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": mission_message(
                                        spec.mission, spec.definition, spec.questions
                                    ),
                                }
                            ],
                            "query_count": 0,
                        },
                        config={
                            "configurable": {"thread_id": spec.thread_id},
                            "recursion_limit": RECURSION_LIMIT,
                        },
                        context=context,
                    )
                    record_agent_usage(
                        run_dir,
                        spec.thread_id,
                        f"researcher_{spec.round_name}",
                        result,
                    )
                except Exception as exception:
                    _record_failure(
                        run_dir, spec, f"{type(exception).__name__}: {exception}"
                    )
                    return
                if session_result_path(run_dir, spec.thread_id).is_file():
                    commit_session_result(run_dir, spec)
                else:
                    _record_failure(run_dir, spec, "the session stored no report")

        await asyncio.gather(*(run_one(spec) for spec in specs))


async def _run_fixture_one(run_dir: Path, spec: SessionSpec, retriever: Any) -> None:
    """Offline stand-in for a research session. Test scaffolding only.

    No model runs here, so this walks the same tools by hand to produce a
    plausibly-shaped run. It is not a researcher and imposes nothing on one.
    """
    query = f"public evidence for {spec.lens} research methods"
    store = SourceStore(run_dir)
    hits = await retriever.search(query)
    store.record_query(
        session_id=spec.thread_id,
        sequence=1,
        agent=spec.agent,
        lens=spec.lens,
        query=query,
        new_sources=len(hits),
    )
    findings = []
    for hit in hits:
        try:
            record = store.store(await retriever.fetch(hit.url))
            text = store.source_text(record["source_sha256"]) or ""
            quote = " ".join(text.split())
            if quote:
                marker = store.record_citation(
                    source_id=record["source_sha256"],
                    quote=quote,
                    tier="3",
                    agent=spec.agent,
                    lens=spec.lens,
                    round_name=spec.round_name,
                    session_id=spec.thread_id,
                )
                findings.append(f"- {quote} {marker}")
        except OSError:
            continue
    status = "answered" if findings else "cannot be answered"
    detail = "" if findings else "The offline fixture returned no text source."
    report = (
        f"# {spec.agent} — {spec.lens}\n\n"
        + ("\n".join(findings) if findings else detail)
        + "\n"
    )
    write_json(
        session_result_path(run_dir, spec.thread_id),
        {"status": status, "reason": detail, "report": report},
    )
    field = "first_status" if spec.round_name == "first" else "second_status"
    update_row(run_dir, researcher_id(spec.agent, spec.lens), **{field: "running"})
    commit_session_result(run_dir, spec)


async def run_fixture_sessions(
    run_dir: Path,
    specs: list[SessionSpec],
    retriever: Any,
) -> None:
    semaphore = asyncio.Semaphore(WORKERS)

    async def bounded(spec: SessionSpec) -> None:
        async with semaphore:
            await _run_fixture_one(run_dir, spec, retriever)

    await asyncio.gather(*(bounded(spec) for spec in specs))
