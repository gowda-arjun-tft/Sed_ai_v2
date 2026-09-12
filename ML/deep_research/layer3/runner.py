"""Historical checkpoint helpers for Layer 4; active Layer 3 runs source discovery."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any, AsyncIterator

from ML.deep_research.layer2.backend.fs import now_iso
from .contracts import ResearchContext
from .pipeline.progress import (
    attempt_session_id, fail_record, model_turns, persist_run, retry_record, stage_event,
)
from .usage import UsageCallback

@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    """Open the historical Layer 4 checkpoint store; source discovery never calls this."""
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(
        str(run_dir / "checkpoints.sqlite3")
    ) as saver:
        await saver.setup()
        yield saver


async def run_stage(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    initial: dict[str, Any],
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> dict[str, Any] | None:
    """Retain the historical checkpointed stage executor for Layer 4."""
    if record["status"] == "failed":
        if not retry_failed:
            return None
        retry_record(record)

    thread_id = record["thread_id"]
    session_id = attempt_session_id(record)
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [UsageCallback(run_dir, session_id)],
        "metadata": {"run_id": run["run_id"], "agent": record["actor"]},
    }
    context = ResearchContext(run_dir, record["actor"], session_id, retriever)
    started = monotonic()
    record.update(status="running", error="", updated_at=now_iso())
    stage_event(run_dir, record, "stage_start")
    await persist_run(run_dir, run, lock)
    try:
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            result = (
                await graph.ainvoke(None, config=config, context=context)
                if snapshot.next
                else snapshot.values
            )
        else:
            result = await graph.ainvoke(initial, config=config, context=context)
        record.update(status="staged", error="")
        stage_event(run_dir, record, "stage_result")
        return result
    except Exception as error:
        await fail_record(run_dir, run, record, error, lock)
        return None
    finally:
        record.update(
            model_turns=model_turns(run_dir, thread_id),
            elapsed_seconds=round(monotonic() - started, 3),
            updated_at=now_iso(),
        )
        await persist_run(run_dir, run, lock)


async def run_research(run_dir: Path, *, retry_failed: bool = False) -> None:
    """Retain the public async entrypoint while running source discovery only."""
    from .source_runner import run_sources

    await run_sources(run_dir, retry_failed=retry_failed)
