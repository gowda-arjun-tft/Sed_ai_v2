"""Offline schema-7 fixtures; no provider calls."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.runnables import RunnableLambda

from ML.deep_research.layer2.ML.agent import Layer2Response
from ML.deep_research.layer2 import create_run, run_all
from ML.deep_research.layer2.backend.fs import load_json


def new_run(root: Path, text="Hospital operating; annex approved, not installed.",
            plugin="## Operations\n## Ownership\n"):
    paths = [root / name for name in ("facts.md", "plugin.md", "requirements.md")]
    for path, content in zip(paths, [text, plugin, "Preserve all facts and ownership."]):
        path.write_text(content, encoding="utf-8")
    return create_run(*paths, root / "runs", reasoning_effort="high")


class FakeStages:
    def __init__(self):
        self.calls = []
        self.fail = set()
        self.unusual = set()
        self.active = 0
        self.peak = 0
        self.delay = 0
        self.messages = []

    def factory(self, run, stage, checkpointer=None):
        async def invoke(value, config):
            import asyncio
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                if self.delay:
                    await asyncio.sleep(self.delay)
                message = value["messages"][0]["content"]
                data = json.JSONDecoder().raw_decode(message)[0]
                self.messages.append((stage, message))
                self.calls.append((stage, data, config["configurable"]["thread_id"]))
                source = data.get("source", {}).get("source_id")
                if stage in self.fail or (stage, source) in self.fail:
                    raise ConnectionError("fabricated failure")
                if stage in self.unusual:
                    response = {"unexpected": {"empty": []}}
                elif stage == "understanding":
                    response = {"profile": data["new_content"],
                                "evidence": [{"fact": data["new_content"],
                                              "nested": {"quantity": "17.5 m²"}},
                                             {"fact": "Approved, not operating"}]}
                elif stage == "design":
                    names = [s.strip("# ") for s in data["domain_plugin"].splitlines() if s.startswith("##")]
                    response = {"domains": [{"name": name, "responsibilities": ["Facts"]}
                                            for name in names] if not data.get("domain_definitions") else []}
                elif stage == "distribution":
                    response = {"assignments": [{"fact_id": f["fact_id"], "domain_ids":
                        ["d0001"] if f["fact_id"].endswith("000001") and "d0001" in data["final_domain_ids"] else []}
                        for f in data["facts"]]}
                elif stage == "observations":
                    response = {"observations": [{"fact_ids": [r["fact_id"] for r in data["facts"]],
                                                 "change": "Add use-specific responsibility"}]}
                elif stage == "catalogue":
                    response = {"domains": [{"domain_id": None, "name": "Additional use", "reason": "Recorded use"}]
                                if not any(r.get("definition", {}).get("name") == "Additional use"
                                           for r in data["domain_definitions"]) else [],
                                "dispositions": [{"proposal_id": p["proposal_id"], "disposition": "accepted"}
                                                 for p in data["observations"]]}
                else:
                    response = {"assignments": [
                        {"fact_id": r["fact_id"], "domain_ids": [data["final_domain_ids"][-1]]}
                        for r in data["facts"]
                    ]}
                return {"structured_response": Layer2Response(root=response)}
            finally:
                self.active -= 1
        graph = RunnableLambda(invoke)
        graph.aget_state = AsyncMock(return_value=SimpleNamespace(values={}))
        return graph

    def run(self, path):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch(
            "ML.deep_research.layer2.backend.jobs.create_stage_agent", side_effect=self.factory,
        ):
            return run_all(path)


def published(run):
    return run / load_json(run / "_internal/trace/publication.json")["path"]


def read_ledger(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
