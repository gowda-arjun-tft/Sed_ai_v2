"""Offline direct-chat fixtures; provider transport is never used."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ML.deep_research.layer2 import create_run, run_all
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.windows import source_windows


def new_run(root: Path, text="Hospital operating; annex approved, not installed.",
            plugin="# Operations\n# Ownership\n", size=None, requirements="Preserve supplied distinctions."):
    paths = [root / name for name in ("facts.md", "plugin.md", "requirements.md")]
    for path, content in zip(paths, [text, plugin, requirements]):
        path.write_bytes(content.encode("utf-8"))
    if size:
        with patch("ML.deep_research.layer2.backend.create_run.source_windows",
                   side_effect=lambda text, **kw: source_windows(text, size=size, overlap=2, **kw)):
            return create_run(*paths, root / "runs", reasoning_effort="high", public_input_confirmed=True)
    return create_run(*paths, root / "runs", reasoning_effort="high", public_input_confirmed=True)


def domain_plan(*names):
    return json.dumps({"domains": [{"domain_id": f"D{index:02d}", "name": name,
                                   "responsibilities": [f"Research {name}."]}
                                  for index, name in enumerate(names, 1)]}, ensure_ascii=False)


def section(messages, label):
    return messages[-1].content.split(f"<{label}>\n", 1)[1].split(f"\n</{label}>", 1)[0]


class OfflineModel(BaseChatModel):
    owner: Any

    @property
    def _llm_type(self):
        return "offline-layer2"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise AssertionError("tests expect asynchronous direct calls")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        self.owner.options.append((run_manager.metadata["job"], kwargs))
        response = await self.owner.respond(messages, run_manager.metadata["job"])
        return ChatResult(generations=[ChatGeneration(message=response)])


class FakeStages:
    def __init__(self):
        self.calls, self.outputs, self.options = [], {}, []
        self.fail, self.unusual = set(), set()
        self.active, self.peak, self.delay = 0, 0, 0
        self.on_call = None
        self.model_profile = None

    async def respond(self, messages, job):
        stage = job.split("/")[0]
        self.calls.append((stage, messages, job))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.on_call:
                self.on_call(messages, job)
            if self.delay:
                await asyncio.sleep(self.delay(job) if callable(self.delay) else self.delay)
            if stage in self.fail or job in self.fail:
                raise ConnectionError("PRIVATE_EXCEPTION_PAYLOAD")
            if job in self.outputs or stage in self.outputs:
                text = self.outputs.get(job, self.outputs.get(stage))
            elif stage in self.unusual:
                text = "Unconventional Markdown — preserved without repair."
            elif stage == "metadata":
                text = section(messages, "previous_metadata") + section(messages, "new_content")
            elif stage == "design":
                text = domain_plan(*(line[2:] for line in section(messages, "domain_plugin").splitlines()
                                     if line.startswith("# ")))
            else:
                text = json.dumps({"D01": "## Supplied facts\n" + section(messages, "new_content"),
                                   "D02": "Shared responsibility.\n"}, ensure_ascii=False)
            if isinstance(text, AIMessage):
                return text
            return AIMessage(content=text, id=f"response-{job.replace('/', '-')}",
                             usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                             response_metadata={"status": "completed", "model_name": "offline"})
        finally:
            self.active -= 1

    def run(self, path):
        # Create asyncio's Windows wake-up sockets before blocking all network in the test.
        loop = asyncio.new_event_loop()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch(
            "ML.deep_research.layer2.backend.runner.build_model",
            return_value=OfflineModel(owner=self, profile=self.model_profile),
        ), patch("socket.socket.connect", side_effect=AssertionError("network disabled in offline test")), patch(
            "asyncio.events.new_event_loop", return_value=loop,
        ):
            try:
                return run_all(path)
            finally:
                loop.close()


def published(run):
    return run / load_json(run / "_internal/trace/publication.json")["path"]
