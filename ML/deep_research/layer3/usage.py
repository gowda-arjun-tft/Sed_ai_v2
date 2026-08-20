from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from ML.deep_research.layer2.fs import read_text, text_hash


_LOCK = threading.RLock()


def _append(run_dir: Path, record: dict[str, Any]) -> None:
    path = run_dir / "usage.jsonl"
    with _LOCK:
        existing = {
            json.loads(line).get("usage_id")
            for line in read_text(path).splitlines()
            if line.strip()
        } if path.exists() else set()
        if record["usage_id"] in existing:
            return
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


class UsageCallback(BaseCallbackHandler):
    """Record supervisor and nested subagent calls through one callback path."""

    def __init__(self, run_dir: Path, session_id: str) -> None:
        self.run_dir = run_dir
        self.session_id = session_id

    def on_llm_end(self, response: Any, *, run_id: UUID, **_: Any) -> None:
        for position, generations in enumerate(response.generations):
            message = getattr(generations[0], "message", None) if generations else None
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                continue
            _append(
                self.run_dir,
                {
                    "usage_id": f"{run_id}:{position}",
                    "session_id": self.session_id,
                    "role": getattr(message, "name", None) or "agent",
                    "input_tokens": int(usage.get("input_tokens", 0)),
                    "output_tokens": int(usage.get("output_tokens", 0)),
                    "total_tokens": int(usage.get("total_tokens", 0)),
                },
            )


def record_search_usage(run_dir: Path, response: Any) -> None:
    usage = getattr(response, "usage", None)
    if not usage:
        return
    values = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    _append(
        run_dir,
        {
            "usage_id": str(getattr(response, "id", "") or text_hash(str(values))),
            "session_id": "web-search",
            "role": "web_search",
            "input_tokens": int(values.get("input_tokens", 0)),
            "output_tokens": int(values.get("output_tokens", 0)),
            "total_tokens": int(values.get("total_tokens", 0)),
        },
    )


def summarize_usage(run_dir: Path) -> dict[str, int]:
    records = [
        json.loads(line)
        for line in read_text(run_dir / "usage.jsonl").splitlines()
        if line.strip()
    ] if (run_dir / "usage.jsonl").exists() else []
    return {
        "model_calls": len(records),
        "input_tokens": sum(item.get("input_tokens", 0) for item in records),
        "output_tokens": sum(item.get("output_tokens", 0) for item in records),
        "total_tokens": sum(item.get("total_tokens", 0) for item in records),
    }
