"""Observe native checkpoint boundaries without issuing additional checkpoint writes."""

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from uuid import uuid4

from ML.deep_research.domain_decider.backend.tracing import event, private_json


class TracedSqliteSaver(AsyncSqliteSaver):
    """The installed SQLite saver plus private receipts after successful native operations."""

    trace_root = None

    async def aput(self, config, checkpoint, metadata, new_versions):
        """Record a successful checkpoint ID and its actual parent, without copying the database."""
        result = await super().aput(config, checkpoint, metadata, new_versions)
        if self.trace_root is not None:
            event(self.trace_root, "checkpoint_saved", checkpoint_id=checkpoint["id"],
                  parent=config.get("configurable", {}).get("checkpoint_id"),
                  thread=config.get("configurable", {}).get("thread_id"), step=metadata.get("step"))
        return result

    async def aput_writes(self, config, writes, task_id, task_path=""):
        """Retain applied todo/note updates and correlate them with native pending-write receipts."""
        await super().aput_writes(config, writes, task_id, task_path)
        if self.trace_root is not None:
            selected = [(key, value) for key, value in writes if key in {"todos", "files", "_summarization_event"}]
            reference = None
            if selected:
                reference = f"state-{task_id}-{uuid4().hex}.json"
                private_json(self.trace_root / reference, selected)
            event(self.trace_root, "checkpoint_writes_saved", task_id=task_id, task_path=task_path,
                  checkpoint_id=config.get("configurable", {}).get("checkpoint_id"), state_reference=reference)
