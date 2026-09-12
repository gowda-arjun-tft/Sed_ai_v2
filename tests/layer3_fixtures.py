"""Offline dynamic Markdown inputs and native Runnable fake for source discovery."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from typing import Any

from ML.deep_research.layer2.backend.fs import atomic_write_text, load_json, write_json
from ML.deep_research.layer3.pipeline.create_run import create_run


def layer2_input(root: Path, names=None) -> Path:
    """Build completed schema-9 Markdown with no historical planner or internal model artifacts."""
    run = root / "runs/group/L2_fixture"
    write_json(run / "run.json", {"schema_version": 9, "status": "complete", "run_id": run.name})
    atomic_write_text(run / "asset_metadata.md", "# Shared asset\n医院 — issuer and operator.\n")
    for index, name in enumerate(names or ["energy", "lease"], 1):
        atomic_write_text(run / "domains" / f"{name}.md",
                          f"# {name}\n\n## Research responsibilities\nInvestigate duty {index}.\n"
                          f"Unique fact {index}; proposed, not operating.\n")
    return run


def new_run(root: Path, names=None, **kwargs) -> Path:
    """Freeze synthetic source guidance and Layer 2 context without calling a model."""
    l2 = layer2_input(root, names)
    guide = root / "source_suggestion.md"
    atomic_write_text(guide, "# Suggestions\nOfficial municipal records and issuer reports.\n")
    return create_run(l2, root / "runs", source_suggestion=guide,
                      public_input_confirmed=True, **kwargs)


def source_json(name="Reported domain") -> str:
    """Return deliberately formatted JSON whose exact bytes must survive publication."""
    return json.dumps({"domain": name, "sources": [{
        "url": "https://example.test/医院.pdf", "description": "Relevant public record.",
        "access": "partial", "access_note": "Summary read; tables unavailable.", "document": True,
    }]}, ensure_ascii=False, indent=3) + "\n"


class OfflineSourceModel(BaseChatModel):
    """Use the installed chat-model callback and serialization path without provider transport."""

    owner: Any
    max_retries: int = 3
    request_timeout: int = 600

    @property
    def _llm_type(self):
        """Identify the offline replacement."""
        return "offline-source-finder"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Reject accidental synchronous research."""
        raise AssertionError("Use async dispatch")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Drive the fake through real model callbacks and native batching."""
        result = await self.owner.ainvoke(messages, {"metadata": run_manager.metadata}, **kwargs)
        return ChatResult(generations=[ChatGeneration(message=result)])


class FakeFinder(Runnable):
    """Use installed native Runnable batching while replacing only model invocation."""

    def __init__(self):
        """Record inputs, concurrency, completion order and configurable operational failures."""
        self.calls, self.outputs, self.failures, self.delays = [], {}, set(), {}
        self.active, self.peak, self.finished = 0, 0, []
        self.profile = {"max_input_tokens": 400_000}
        self.max_retries, self.request_timeout = 3, 600
        self.hold = None

    def invoke(self, request, config=None, **kwargs):
        """Reject accidental synchronous dispatch in the async notebook workflow."""
        raise AssertionError("Use async source discovery")

    async def ainvoke(self, request, config=None, **options):
        """Emit realistic callback usage and hosted tool actions without network access."""
        key = config["metadata"]["lc_agent_name"]
        self.calls.append((key, request, options))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            hold = self.hold.get(key) if isinstance(self.hold, dict) else self.hold
            if hold:
                await hold.wait()
            await asyncio.sleep(self.delays.get(key, 0))
            if key in self.failures:
                raise TimeoutError("PRIVATE_URL_AND_QUERY_MUST_NOT_BE_LOGGED")
            result = self.outputs.get(key, source_json())
            if not isinstance(result, AIMessage):
                result = AIMessage(
                    content=result, id=f"resp-{key.rsplit('/', 1)[-1]}",
                    additional_kwargs={"tool_outputs": [
                        {"type": "web_search_call", "id": "ws-test", "status": "completed",
                         "action": {"type": "open_page", "url": "https://example.test/PRIVATE"}},
                    ]},
                    response_metadata={"status": "completed"},
                    usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                )
            self.finished.append(key)
            return result
        finally:
            self.active -= 1

    async def run(self, run: Path, **kwargs):
        """Patch only construction and block network during a real source runner invocation."""
        from ML.deep_research.layer3.source_runner import run_sources

        with patch("ML.deep_research.layer3.source_runner.build_model",
                   return_value=OfflineSourceModel(owner=self, profile=self.profile)), patch(
            "socket.socket.connect", side_effect=AssertionError("Network disabled"),
        ), patch("sqlite3.connect", side_effect=AssertionError("No source-finder SQLite")):
            await run_sources(run, **kwargs)
        return load_json(run / "run.json")


def snapshot(root: Path) -> dict:
    """Capture bytes to prove read-only checks and frozen artifacts do not change."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
