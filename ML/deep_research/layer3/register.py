from __future__ import annotations

import csv
import secrets
import threading
import uuid
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import now_iso, slug

from .settings import LENSES


FIELDS = [
    "row_id",
    "row_type",
    "agent",
    "lens",
    "thread_id",
    "second_thread_id",
    "attempts",
    "first_status",
    "first_at",
    "first_sources",
    "first_queries",
    "first_hash",
    "second_status",
    "second_at",
    "second_questions",
    "first_detail",
    "second_detail",
    "detail",
    "updated_at",
]
_LOCK = threading.RLock()


def researcher_id(agent: str, lens: str) -> str:
    return f"{slug(agent)}::{slug(lens)}"


def aggregator_id(agent: str) -> str:
    return f"{slug(agent)}::aggregator"


def thread_id(run_id: str, row_id: str, stage: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cdi:{run_id}:{row_id}:{stage}"))


def _blank_row(
    run_id: str,
    row_id: str,
    row_type: str,
    agent: str,
    lens: str,
) -> dict[str, str]:
    return {
        "row_id": row_id,
        "row_type": row_type,
        "agent": agent,
        "lens": lens,
        "thread_id": thread_id(run_id, row_id, "first"),
        "second_thread_id": thread_id(run_id, row_id, "second"),
        "attempts": "0",
        "first_status": "never started",
        "first_at": "",
        "first_sources": "0",
        "first_queries": "0",
        "first_hash": "",
        "second_status": "never started",
        "second_at": "",
        "second_questions": "0",
        "first_detail": "",
        "second_detail": "",
        "detail": "",
        "updated_at": now_iso(),
    }


def seed_register(run_dir: Path, run_id: str, agents: list[str]) -> None:
    rows = []
    for agent in agents:
        for lens in LENSES:
            row_id = researcher_id(agent, lens)
            rows.append(_blank_row(run_id, row_id, "researcher", agent, lens))
        row_id = aggregator_id(agent)
        rows.append(_blank_row(run_id, row_id, "agent", agent, "aggregator"))
    write_rows(run_dir, rows)


def read_rows(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "register.csv"
    if not path.exists():
        return []
    with _LOCK, path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(run_dir: Path, rows: list[dict[str, str]]) -> None:
    path = run_dir / "register.csv"
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    with _LOCK, temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in FIELDS} for row in rows)
    temporary.replace(path)


def row(run_dir: Path, row_id: str) -> dict[str, str]:
    return next(item for item in read_rows(run_dir) if item["row_id"] == row_id)


def update_row(run_dir: Path, row_id: str, **changes: Any) -> dict[str, str]:
    unknown = set(changes) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown register fields: {sorted(unknown)}")
    with _LOCK:
        rows = read_rows(run_dir)
        target = next((item for item in rows if item["row_id"] == row_id), None)
        if target is None:
            raise KeyError(row_id)
        target.update({key: str(value) for key, value in changes.items()})
        target["updated_at"] = now_iso()
        write_rows(run_dir, rows)
        return dict(target)


def increment_attempts(run_dir: Path, row_id: str) -> int:
    current = row(run_dir, row_id)
    attempts = int(current["attempts"] or 0) + 1
    update_row(run_dir, row_id, attempts=attempts)
    return attempts


def add_sixth_row(run_dir: Path, run_id: str, agent: str, lens: str) -> dict[str, str]:
    row_id = researcher_id(agent, lens)
    with _LOCK:
        rows = read_rows(run_dir)
        existing = next((item for item in rows if item["row_id"] == row_id), None)
        if existing:
            return existing
        new_row = _blank_row(run_id, row_id, "researcher", agent, lens)
        new_row["second_status"] = "skipped"
        rows.append(new_row)
        write_rows(run_dir, rows)
        return new_row
