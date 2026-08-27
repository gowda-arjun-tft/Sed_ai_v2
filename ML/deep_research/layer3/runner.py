from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any, AsyncIterator

from langgraph.types import Command, Interrupt

from ML.deep_research.layer2.fs import (
    atomic_write_text, load_json, now_iso, read_text, slug,
)

from .contracts import ResearchContext
from .document_supervisor import preflight_document_worker, process_document_interrupts
from .llm import (
    create_domain_coordinator_harness,
    create_synthesis_harness,
    final_text,
)
from .mission import load_research_input
from .pipeline.progress import (
    attempt_session_id,
    fail_record,
    model_turns,
    persist_run,
    restart_record,
    retry_record,
    save_run,
    stage_event,
)
from .prompts import domain_message, synthesis_message
from .providers import from_run
from .settings import DOMAIN_NAMES, SCHEMA_VERSION
from .usage import UsageCallback


def _interrupts(value: Any) -> tuple[Interrupt, ...]:
    if not isinstance(value, dict):
        return ()
    return tuple(
        item
        for item in value.get("__interrupt__", ())
        if isinstance(item, Interrupt)
    )


def _saved_interrupts(record: dict[str, Any]) -> tuple[Interrupt, ...]:
    return tuple(
        Interrupt(value=item["value"], id=item["id"])
        for item in record.get("document_interrupts", ())
        if isinstance(item, dict) and "id" in item and "value" in item
    )


async def _resume_document_interrupts(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    result: dict[str, Any],
    config: dict[str, Any],
    context: ResearchContext,
    lock: asyncio.Lock,
) -> dict[str, Any]:
    while pending := _interrupts(result):
        record.update(
            status="waiting_for_documents",
            document_interrupts=[
                {"id": item.id, "value": item.value} for item in pending
            ],
            updated_at=now_iso(),
        )
        run["status"] = "waiting_for_documents"
        stage_event(run_dir, record, "documents_waiting", str(len(pending)))
        await persist_run(run_dir, run, lock)

        resumes = await process_document_interrupts(run_dir, list(pending))
        record.update(status="running", document_interrupts=[], updated_at=now_iso())
        run["status"] = "running"
        stage_event(run_dir, record, "documents_ready", str(len(resumes)))
        await persist_run(run_dir, run, lock)
        result = await graph.ainvoke(
            Command(resume=resumes), config=config, context=context
        )
    return result


@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(
        str(run_dir / "checkpoints.sqlite3")
    ) as saver:
        await saver.setup()
        yield saver


async def _run_stage(
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
    was_waiting = record["status"] == "waiting_for_documents"
    if not was_waiting:
        record.update(status="running", error="", updated_at=now_iso())
    stage_event(run_dir, record, "stage_start")
    await persist_run(run_dir, run, lock)
    try:
        snapshot = await graph.aget_state(config)
        checkpoint_interrupts = tuple(getattr(snapshot, "interrupts", ()))
        saved_interrupts = _saved_interrupts(record) if was_waiting else ()
        if checkpoint_interrupts or saved_interrupts:
            result = {"__interrupt__": checkpoint_interrupts or saved_interrupts}
        elif snapshot.values:
            result = (
                await graph.ainvoke(None, config=config, context=context)
                if snapshot.next
                else snapshot.values
            )
        else:
            result = await graph.ainvoke(initial, config=config, context=context)
        result = await _resume_document_interrupts(
            graph, run_dir, run, record, result, config, context, lock
        )
        record.update(status="staged", error="", document_interrupts=[])
        stage_event(run_dir, record, "stage_result")
        return result
    except Exception as error:
        run["status"] = "running"
        await fail_record(run_dir, run, record, error, lock)
        return None
    finally:
        record.update(
            model_turns=model_turns(run_dir, thread_id),
            elapsed_seconds=round(monotonic() - started, 3),
            updated_at=now_iso(),
        )
        await persist_run(run_dir, run, lock)


async def _publish_domain(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    initial: dict[str, Any],
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> str | None:
    target = run_dir / "domains" / slug(record["actor"]) / "final.md"
    if record["status"] == "complete":
        if target.is_file():
            return read_text(target)
        record["status"] = "pending"

    state = await _run_stage(
        graph,
        run_dir,
        run,
        record,
        retriever,
        initial,
        lock,
        retry_failed=retry_failed,
    )
    if state is None:
        return None
    report = final_text(state)
    atomic_write_text(target, report)
    output_path = target.relative_to(run_dir).as_posix()
    record.update(status="complete", output_path=output_path)
    stage_event(run_dir, record, "domain_publish", output_path)
    await persist_run(run_dir, run, lock)
    return report


async def _publish_synthesis(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    reports: dict[str, str],
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> bool:
    target = run_dir / "research" / "final.md"
    if record["status"] == "complete":
        if target.is_file():
            return True
        record["status"] = "pending"

    state = await _run_stage(
        graph,
        run_dir,
        run,
        record,
        retriever,
        {
            "messages": [{"role": "user", "content": synthesis_message(reports)}],
        },
        lock,
        retry_failed=retry_failed,
    )
    if state is None:
        return False
    atomic_write_text(target, final_text(state))
    record.update(status="complete", output_path="research/final.md")
    stage_event(run_dir, record, "answer_publish", "research/final.md")
    await persist_run(run_dir, run, lock)
    return True


async def run_research(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    if run.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 3 schema {run.get('schema_version')!r} cannot resume in schema "
            f"{SCHEMA_VERSION}; start a fresh Layer 3 run from the completed Layer 2 run"
        )
    await preflight_document_worker(run_dir)
    retriever = from_run(run, run_dir)
    assignments = {item["name"]: item for item in load_research_input(run_dir)}
    lock = asyncio.Lock()
    run["status"] = "running"
    save_run(run_dir, run)

    reports: dict[str, str] = {}
    domain_changed = False
    async with checkpoint_saver(run_dir) as saver:
        coordinator = create_domain_coordinator_harness(run_dir, saver)
        for name in DOMAIN_NAMES:
            was_complete = run["execution"]["domains"][name]["status"] == "complete"
            report = await _publish_domain(
                coordinator,
                run_dir,
                run,
                run["execution"]["domains"][name],
                retriever,
                {"messages": [{"role": "user", "content": domain_message(assignments[name])}]},
                lock,
                retry_failed=retry_failed,
            )
            if report is not None:
                reports[name] = report
                domain_changed = domain_changed or not was_complete

        final_record = run["execution"]["final"]
        if domain_changed and final_record["status"] != "pending":
            restart_record(run, final_record)

        complete = await _publish_synthesis(
            create_synthesis_harness(run_dir, saver),
            run_dir,
            run,
            final_record,
            retriever,
            reports,
            lock,
            retry_failed=retry_failed,
        )
        if not complete:
            run["status"] = "incomplete"
            save_run(run_dir, run)
            return

    run["status"] = "complete"
    save_run(run_dir, run)
