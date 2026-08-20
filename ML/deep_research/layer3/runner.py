from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    slug,
    write_json,
)

from .contracts import ResearchContext
from .llm import create_mission_supervisor, structured_value
from .mission import load_inputs, mission_thread_id
from .prompts import mission_message
from .providers import from_run
from .settings import LENSES
from .usage import UsageCallback, summarize_usage


@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(
        str(run_dir / "checkpoints.sqlite3")
    ) as saver:
        await saver.setup()
        yield saver


def _content(files: dict[str, Any], path: str) -> str:
    value = files.get(path)
    if not isinstance(value, dict):
        return ""
    content = value.get("content", "")
    return "\n".join(content) if isinstance(content, list) else str(content)


def _combined(first: str, followup: str) -> str:
    if not followup:
        return first
    separator = "\n" if first.endswith("\n") else "\n\n"
    return first + separator + "## Follow-up\n\n" + followup


def commit_outputs(run_dir: Path, agent: str, state: dict[str, Any]) -> None:
    """Validate all staged outputs, then atomically publish the mission."""
    files = state.get("files") or {}
    if not isinstance(files, dict):
        raise ValueError("checkpoint contains no StateBackend files")
    outputs: dict[Path, str] = {}
    target = run_dir / "lenses" / slug(agent)
    for lens in LENSES:
        first = _content(files, f"/lenses/{lens}/first.md")
        if not first.strip():
            raise ValueError(f"missing {lens} first-round report")
        followup = _content(files, f"/lenses/{lens}/followup.md")
        outputs[target / f"{lens}.md"] = _combined(first, followup)
    additional = _content(files, "/lenses/additional/report.md")
    additional_target = target / "additional.md"
    if additional.strip():
        outputs[additional_target] = additional
    answer = _content(files, "/answer.md")
    if not answer.strip():
        raise ValueError("missing final /answer.md")
    outputs[run_dir / "research" / f"{slug(agent)}.md"] = answer
    for path, text in outputs.items():
        atomic_write_text(path, text)
    if not additional.strip():
        additional_target.unlink(missing_ok=True)


def _record(run: dict[str, Any], agent: str) -> dict[str, Any]:
    return run["missions"][slug(agent)]


def _save(run_dir: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = now_iso()
    run["usage"] = summarize_usage(run_dir)
    write_json(run_dir / "run.json", run)


async def _run_one(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    mission: dict[str, Any],
    definition: dict[str, Any],
    retriever: Any,
    *,
    retry_failed: bool,
) -> None:
    agent = str(mission["agent"])
    record = _record(run, agent)
    if record["status"] == "complete":
        return
    if record["status"] == "failed":
        if not retry_failed:
            return
        record["attempt"] += 1
        record["thread_id"] = mission_thread_id(
            run["run_id"], agent, record["attempt"]
        )
        record.update(status="pending", outcome="", reason="", error="")

    thread_id = record["thread_id"]
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [UsageCallback(run_dir, thread_id)],
        "metadata": {"run_id": run["run_id"], "agent": agent},
    }
    context = ResearchContext(run_dir, agent, thread_id, retriever)
    record.update(status="running", error="", updated_at=now_iso())
    _save(run_dir, run)
    try:
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            result = (
                await graph.ainvoke(None, config=config, context=context)
                if snapshot.next
                else snapshot.values
            )
        else:
            result = await graph.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": mission_message(mission, definition),
                        }
                    ]
                },
                config=config,
                context=context,
            )
        outcome = structured_value(result)
        commit_outputs(run_dir, agent, result)
        record.update(
            status="complete",
            outcome=outcome.status,
            reason=outcome.reason,
            error="",
            additional_lens=outcome.additional_lens,
            additional_focus=outcome.additional_focus,
            updated_at=now_iso(),
        )
    except Exception as error:
        record.update(
            status="failed",
            error=f"{type(error).__name__}: {error}",
            updated_at=now_iso(),
        )
    _save(run_dir, run)


async def run_missions(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    if run.get("schema_version") != 2:
        raise ValueError("legacy Layer 3 runs cannot be resumed by this harness")
    retriever = from_run(run, run_dir)
    run["status"] = "running"
    _save(run_dir, run)
    async with checkpoint_saver(run_dir) as saver:
        graph = create_mission_supervisor(run_dir, saver)
        for mission, definition in load_inputs(run_dir):
            await _run_one(
                graph,
                run_dir,
                run,
                mission,
                definition,
                retriever,
                retry_failed=retry_failed,
            )
    run["status"] = (
        "complete"
        if all(item["status"] == "complete" for item in run["missions"].values())
        else "incomplete"
    )
    _save(run_dir, run)
