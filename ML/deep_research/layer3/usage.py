from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from ML.deep_research.layer2.fs import now_iso, read_text, text_hash


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
            values,
            ("input_token_details", "input_tokens_details"),
            ("cache_read", "cached_tokens"),
        ),
        "cache_creation_input_tokens": _detail(
            values,
            ("input_token_details", "input_tokens_details"),
            ("cache_creation",),
        ),
        "output_tokens": int(values.get("output_tokens", 0) or 0),
        "reasoning_output_tokens": _detail(
            values,
            ("output_token_details", "output_tokens_details"),
            ("reasoning", "reasoning_tokens"),
        ),
        "total_tokens": int(values.get("total_tokens", 0) or 0),
    }


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
    """Record model calls for one direct Layer 3 invocation."""

    def __init__(self, run_dir: Path, session_id: str) -> None:
        self.run_dir = run_dir
        self.session_id = session_id
        self._actors: dict[UUID, str] = {}

    def on_chat_model_start(
        self,
        _serialized: dict[str, Any],
        _messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        with _LOCK:
            self._actors[run_id] = str(
                (metadata or {}).get("lc_agent_name")
                or (metadata or {}).get("agent")
                or "unknown"
            )

    def on_llm_end(self, response: Any, *, run_id: UUID, **_: Any) -> None:
        with _LOCK:
            actor = self._actors.pop(run_id, "unknown")
        for position, generations in enumerate(response.generations):
            message = getattr(generations[0], "message", None) if generations else None
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                continue
            values = _mapping(usage)
            _append(
                self.run_dir,
                {
                    "usage_id": f"{run_id}:{position}",
                    "session_id": self.session_id,
                    "actor": getattr(message, "name", None) or actor,
                    "phase": "model",
                    "timestamp": now_iso(),
                    **_tokens(values),
                },
            )


def record_search_usage(
    run_dir: Path, response: Any, actor: str, session_id: str = "web-search"
) -> None:
    usage = getattr(response, "usage", None)
    if not usage:
        return
    values = _mapping(usage)
    _append(
        run_dir,
        {
            "usage_id": str(getattr(response, "id", "") or text_hash(str(values))),
            "session_id": session_id,
            "actor": actor,
            "phase": "web_search",
            "timestamp": now_iso(),
            **_tokens(values),
        },
    )


def record_event(
    run_dir: Path,
    *,
    event_id: str,
    phase: str,
    actor: str,
    session_id: str,
    detail: str = "",
) -> None:
    """Append one replay-safe, zero-token progress event to the live usage log."""
    if not all(value.strip() for value in (event_id, phase, actor, session_id)):
        raise ValueError("event identity, phase, actor, and session must be non-empty")
    _append(
        run_dir,
        {
            "usage_id": f"event:{event_id}",
            "session_id": session_id,
            "actor": actor,
            "phase": phase,
            "detail": detail,
            "timestamp": now_iso(),
            **_tokens({}),
        },
    )


def summarize_usage(run_dir: Path) -> dict[str, int]:
    records = [
        json.loads(line)
        for line in read_text(run_dir / "usage.jsonl").splitlines()
        if line.strip()
    ] if (run_dir / "usage.jsonl").exists() else []
    token_fields = (
        "input_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    model_calls = sum(item.get("phase") == "model" for item in records)
    web_search_calls = sum(item.get("phase") == "web_search" for item in records)
    summary = {
        "api_calls": model_calls + web_search_calls,
        "model_calls": model_calls,
        "web_search_calls": web_search_calls,
        "events": len(records) - model_calls - web_search_calls,
    }
    summary.update(
        {field: sum(int(item.get(field, 0) or 0) for item in records) for field in token_fields}
    )
    return summary
