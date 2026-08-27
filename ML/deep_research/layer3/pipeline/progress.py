from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import now_iso, write_json

from ..mission import stage_thread_id
from ..sources import load_jsonl
from ..usage import record_event, summarize_usage


def model_turns(run_dir: Path, thread_id: str) -> int:
    return sum(
        item.get("phase") == "model"
        and (
            item.get("session_id") == thread_id
            or str(item.get("session_id", "")).startswith(f"{thread_id}:attempt-")
        )
        for item in load_jsonl(run_dir / "usage.jsonl")
    )


def attempt_session_id(record: dict[str, Any]) -> str:
    """Return one attribution identity without changing checkpoint identity."""
    return f"{record['thread_id']}:attempt-{record['attempt']}"


def save_run(run_dir: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = now_iso()
    run["usage"] = summarize_usage(run_dir)
    write_json(run_dir / "run.json", run)


def stage_event(
    run_dir: Path,
    record: dict[str, Any],
    phase: str,
    detail: str = "",
) -> None:
    session_id = attempt_session_id(record)
    record_event(
        run_dir,
        event_id=f"{session_id}:{phase}",
        phase=phase,
        actor=record["actor"],
        session_id=session_id,
        detail=detail,
    )


def retry_record(record: dict[str, Any]) -> None:
    """Start another application attempt on the same durable checkpoint."""
    record["attempt"] += 1
    record.update(
        status="pending",
        error="",
        output_path="",
        model_turns=0,
        elapsed_seconds=0.0,
    )


def restart_record(run: dict[str, Any], record: dict[str, Any]) -> None:
    """Start a fresh checkpoint thread because the stage input changed."""
    retry_record(record)
    record["thread_id"] = stage_thread_id(
        run["run_id"],
        record["stage"],
        record["actor"],
        record["batch"],
        record["attempt"],
    )


async def persist_run(
    run_dir: Path,
    run: dict[str, Any],
    lock: asyncio.Lock,
) -> None:
    async with lock:
        save_run(run_dir, run)


async def fail_record(
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    error: Exception | str,
    lock: asyncio.Lock,
) -> None:
    message = str(error) if isinstance(error, str) else f"{type(error).__name__}: {error}"
    record.update(status="failed", error=message, updated_at=now_iso())
    stage_event(run_dir, record, "stage_failed", message)
    await persist_run(run_dir, run, lock)


def stage_record(
    run: dict[str, Any],
    stage: str,
    actor: str,
    batch: int,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "actor": actor,
        "batch": batch,
        "thread_id": stage_thread_id(run["run_id"], stage, actor, batch, 1),
        "attempt": 1,
        "status": "pending",
        "error": "",
        "output_path": "",
        "model_turns": 0,
        "elapsed_seconds": 0.0,
        "updated_at": now_iso(),
    }
