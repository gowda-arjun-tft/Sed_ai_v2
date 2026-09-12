"""Native graph/checkpoint tests with model and network boundaries replaced offline."""

import asyncio
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ML.deep_research.layer3.contracts import Document
from ML.deep_research.layer3.research_run import create_research_run
from tests.layer3_fixtures import FakeFinder, new_run


async def linked_run(root, names=None):
    """Create real saved preparation, then a separate research handoff with frozen copies."""
    parent = new_run(root, names)
    await FakeFinder().run(parent)
    # A completed preparation predating research capabilities.
    from ML.deep_research.layer2.backend.fs import load_json, write_json
    record = load_json(parent / "run.json")
    record.pop("research")
    write_json(parent / "run.json", record)
    return parent, create_research_run(parent, root / "runs", public_input_confirmed=True)


class ResearchModel:
    """Exercise installed graph/model callbacks, native tools and SQLite using deterministic answers."""

    def __init__(self):
        """Track every actual fake invocation and concurrent main model call."""
        self.calls, self.surfaces = [], []
        self.active, self.peak = 0, 0
        self.fail_domain, self.gate = None, None
        self.custom = None

    @contextmanager
    def offline(self, checkpoint_dir):
        """Keep the real model builder/profile but replace transport before it can contact OpenAI."""
        owner = self

        async def generate(model, messages, stop=None, run_manager=None, **kwargs):
            """Return multi-turn model/tool content through the installed ChatOpenAI callbacks."""
            meta = getattr(run_manager, "metadata", {}) or {}
            domain = meta.get("lc_agent_name", "unknown")
            owner.calls.append((domain, messages, kwargs))
            owner.surfaces.append({t.get("function", {}).get("name", t.get("name")) for t in kwargs.get("tools", [])})
            owner.active += 1
            owner.peak = max(owner.peak, owner.active)
            try:
                if owner.gate:
                    await owner.gate.wait()
                await asyncio.sleep(0.005)
                if domain == owner.fail_domain:
                    raise TimeoutError("PRIVATE_EVIDENCE_DO_NOT_LOG")
                turns = [m for m in messages if getattr(m, "type", "") == "ai"]
                if meta.get("lc_source") == "summarization":
                    result = AIMessage(content="Prior evidence remains in /archive/; continue the domain plan.")
                elif owner.custom:
                    result = await owner.custom(domain, messages, kwargs)
                elif not turns:
                    result = AIMessage(content="Planning", tool_calls=[
                        {"name": "write_todos", "args": {"todos": [{"content": "Investigate duty", "status": "in_progress"}]}, "id": "todo-1"},
                        {"name": "write_file", "args": {"file_path": "/notes/findings.md", "content": "医院 — pending condition"}, "id": "note-1"}])
                elif len(turns) == 1:
                    result = AIMessage(content="Read underlying evidence", tool_calls=[
                        {"name": "read_source", "args": {"url": "https://official.example/record"}, "id": "read-1"}])
                else:
                    result = AIMessage(content="# Research\n\n医院 — condition and exception retained. [Record](https://official.example/record)\n\nGap: unresolved date.\n")
                result.usage_metadata = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
                return ChatResult(generations=[ChatGeneration(message=result)])
            finally:
                owner.active -= 1

        def fetch(url):
            """Return canonical public-source bytes, not a search snippet."""
            return Document(url, "text/plain; charset=utf-8", "医院 — rule, exception, 2030.".encode(), "2026-09-11")

        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        with patch("langchain_openai.ChatOpenAI._agenerate", generate), patch(
            "ML.deep_research.layer3.cli.checkpoint_root", return_value=checkpoint_dir
        ), patch("ML.deep_research.layer3.domain_tools._fetch", fetch), patch(
            "socket.socket.connect", side_effect=AssertionError("Network blocked")
        ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}):
            yield
