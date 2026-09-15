"""Private append-only observations correlated with existing response and checkpoint artifacts."""

import json
import os
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .fs import atomic_write_text

TRACE_ROOT = ContextVar("research_trace_root", default=None)
TRACE_CONTEXT = ContextVar("research_trace_context", default={})
LOGICAL_CALL = ContextVar("research_logical_call", default=None)
_LOCK = RLock()


def plain(value):
    """Serialize framework values without exception bodies or binary checkpoint payloads."""
    if hasattr(value, "model_dump"):
        return plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, bytes):
        return {"binary_bytes": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def private_json(path, value):
    """Protect the runtime credential even if a provider unexpectedly echoes it."""
    text = json.dumps(plain(value), ensure_ascii=False, indent=2)
    secret = os.environ.get("OPENAI_API_KEY")
    if secret:
        text = text.replace(secret, "[credential redacted]")
    atomic_write_text(path, text + "\n")


def event(root, event_type, **values):
    """Append one observed event; payload artifacts stay outside the operational log."""
    root = Path(root)
    sink = TRACE_ROOT.get() or root
    sink = Path(sink)
    path = sink / "events.jsonl"
    item = {"event_id": uuid4().hex, "utc": datetime.now(UTC).isoformat(), "event": event_type,
            "scope": str(root), **TRACE_CONTEXT.get(), "logical_call": LOGICAL_CALL.get(), **values}
    text = json.dumps(plain(item), ensure_ascii=False)
    secret = os.environ.get("OPENAI_API_KEY")
    if secret:
        text = text.replace(secret, "[credential redacted]")
    # ponytail: one process-local append lock; the existing run lock excludes other writers.
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")
            stream.flush()
    return item["event_id"]


def reasoning_summaries(path, payload):
    """Save only provider-returned public reasoning summary blocks, never hidden chain-of-thought."""
    summaries = []
    def visit(value):
        """Find supported summary blocks without treating final answer text as reasoning."""
        if isinstance(value, dict):
            if value.get("type") == "reasoning" and value.get("summary"):
                summaries.append(value["summary"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(payload)
    private_json(path, {"summaries": summaries, "available": bool(summaries)})
