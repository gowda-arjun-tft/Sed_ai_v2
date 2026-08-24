"""Append Layer 2 model usage while the agent is still running."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from .fs import now_iso, read_text


_LOCK = threading.RLock()


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    try:
        return dict(value or {})
    except (TypeError, ValueError):
        return {}


def _detail(values: dict[str, Any], groups: tuple[str, ...], keys: tuple[str, ...]) -> int:
    for group in groups:
        details = _mapping(values.get(group))
        for key in keys:
            if key in details:
                return int(details.get(key) or 0)
    return 0


def _tokens(values: dict[str, Any]) -> dict[str, int]:
    return {
        "input_tokens": int(values.get("input_tokens", 0) or 0),
        "cached_input_tokens": _detail(
            values, ("input_token_details", "input_tokens_details"),
            ("cache_read", "cached_tokens"),
        ),
        "cache_creation_input_tokens": _detail(
            values, ("input_token_details", "input_tokens_details"), ("cache_creation",)
        ),
        "output_tokens": int(values.get("output_tokens", 0) or 0),
        "reasoning_output_tokens": _detail(
            values, ("output_token_details", "output_tokens_details"),
            ("reasoning", "reasoning_tokens"),
        ),
        "total_tokens": int(values.get("total_tokens", 0) or 0),
    }


class UsageCallback(BaseCallbackHandler):
    """Persist usage after every completed chunk response."""

    def __init__(self, run_dir: Path, thread_id: str) -> None:
        self.path = run_dir / "usage.jsonl"
        self.thread_id = thread_id
        self._actors: dict[UUID, str] = {}

    def on_chat_model_start(
        self, _serialized: dict[str, Any], _messages: list[list[Any]], *,
        run_id: UUID, metadata: dict[str, Any] | None = None, **_: Any,
    ) -> None:
        with _LOCK:
            self._actors[run_id] = str((metadata or {}).get("lc_agent_name") or "cdi-layer2")

    def on_llm_end(self, response: Any, *, run_id: UUID, **_: Any) -> None:
        with _LOCK:
            actor = self._actors.pop(run_id, "cdi-layer2")
            for position, generations in enumerate(response.generations):
                message = getattr(generations[0], "message", None) if generations else None
                usage = getattr(message, "usage_metadata", None)
                if not usage:
                    continue
                record = {
                    "usage_id": f"{run_id}:{position}",
                    "thread_id": self.thread_id,
                    "actor": getattr(message, "name", None) or actor,
                    "timestamp": now_iso(),
                    **_tokens(_mapping(usage)),
                }
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")


def summarize_usage(run_dir: Path) -> dict[str, int]:
    records = []
    if (run_dir / "usage.jsonl").exists():
        for line in read_text(run_dir / "usage.jsonl").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    fields = (
        "input_tokens", "cached_input_tokens", "cache_creation_input_tokens",
        "output_tokens", "reasoning_output_tokens", "total_tokens",
    )
    summary = {"model_calls": len(records)}
    summary.update({key: sum(int(row.get(key, 0) or 0) for row in records) for key in fields})
    return summary
