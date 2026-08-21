from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import now_iso, write_json

from ..mission import stage_thread_id
from ..usage import record_event, summarize_usage


def model_turns(run_dir: Path, thread_id: str) -> int:
    path = run_dir / "usage.jsonl"
    if not path.is_file():
        return 0
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return sum(
        item.get("phase") == "model" and item.get("session_id") == thread_id
        for item in records
    )


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
    record_event(
        run_dir,
        event_id=f"{record['thread_id']}:{phase}",
        phase=phase,
        actor=record["actor"],
        session_id=record["thread_id"],
        detail=detail,
    )


def retry_record(run: dict[str, Any], record: dict[str, Any]) -> None:
    record["attempt"] += 1
    record["thread_id"] = stage_thread_id(
        run["run_id"],
        record["stage"],
        record["actor"],
        record["batch"],
        record["attempt"],
    )
    record.update(
        status="pending",
        outcome="",
        reason="",
        error="",
        unknowns=[],
        model_turns=0,
        elapsed_seconds=0.0,
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
        "outcome": "",
        "reason": "",
        "error": "",
        "unknowns": [],
        "model_turns": 0,
        "elapsed_seconds": 0.0,
        "updated_at": now_iso(),
    }
