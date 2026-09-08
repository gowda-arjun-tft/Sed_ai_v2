from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage

from ML.deep_research.layer2.backend.fs import load_json, now_iso, text_hash
from ML.deep_research.layer2.backend.usage import _mapping, _tokens

from .sources import load_jsonl


_LOCK = threading.RLock()


def _append(run_dir: Path, record: dict[str, Any]) -> None:
    path = run_dir / "usage.jsonl"
    try:
        with _LOCK:
            existing = {item.get("usage_id") for item in load_jsonl(path)}
            if record.get("usage_id") in existing:
                return
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return

class UsageCallback(BaseCallbackHandler):
    """Record model calls for one direct Layer 3 invocation."""

    def __init__(self, run_dir: Path, session_id: str) -> None:
        self.run_dir = run_dir
        self.session_id = session_id
        self._calls: dict[UUID, dict[str, Any]] = {}
        policy = load_json(run_dir / "run.json").get("context_management") or {}
        self.soft_target_tokens = int(policy.get("soft_target_tokens", 0) or 0)

    def on_chat_model_start(
        self,
        _serialized: dict[str, Any],
        _messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        metadata = metadata or {}
        cleared = sum(
            bool(
                isinstance(message, ToolMessage)
                and (message.response_metadata.get("context_editing") or {}).get(
                    "cleared", False
                )
            )
            for batch in _messages
            for message in batch
        )
        with _LOCK:
            self._calls[run_id] = {
                "actor": str(
                    metadata.get("lc_agent_name")
                    or metadata.get("agent")
                    or "unknown"
                ),
                "operation": (
                    "summarization"
                    if metadata.get("lc_source") == "summarization"
                    else "research"
                ),
                "compacted_source_results": cleared,
            }

    def on_llm_end(self, response: Any, *, run_id: UUID, **_: Any) -> None:
        with _LOCK:
            call = self._calls.pop(
                run_id,
                {
                    "actor": "unknown",
                    "operation": "research",
                    "compacted_source_results": 0,
                },
            )
        for position, generations in enumerate(response.generations):
            message = getattr(generations[0], "message", None) if generations else None
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                continue
            values = _mapping(usage)
            tokens = _tokens(values)
            _append(
                self.run_dir,
                {
                    "usage_id": f"{run_id}:{position}",
                    "session_id": self.session_id,
                    "actor": getattr(message, "name", None) or call["actor"],
                    "phase": "model",
                    "operation": call["operation"],
                    "compacted_source_results": call["compacted_source_results"],
                    "soft_target_tokens": self.soft_target_tokens,
                    "over_soft_target": bool(
                        self.soft_target_tokens
                        and tokens["input_tokens"] > self.soft_target_tokens
                    ),
                    "timestamp": now_iso(),
                    **tokens,
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
        return
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
    records = load_jsonl(run_dir / "usage.jsonl")
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
        "summarization_calls": sum(
            item.get("phase") == "model"
            and item.get("operation") == "summarization"
            for item in records
        ),
        "web_search_calls": web_search_calls,
        "over_soft_target_calls": sum(
            item.get("phase") == "model" and bool(item.get("over_soft_target"))
            for item in records
        ),
        "compacted_source_results": sum(
            int(item.get("compacted_source_results", 0) or 0)
            for item in records
            if item.get("phase") == "model"
        ),
        "events": len(records) - model_calls - web_search_calls,
    }
    summary.update(
        {field: sum(int(item.get(field, 0) or 0) for item in records) for field in token_fields}
    )
    return summary
