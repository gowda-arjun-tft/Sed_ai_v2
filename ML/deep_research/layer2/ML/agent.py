"""Permissive JSON Deep Agents with stage-local read-only capabilities."""

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.structured_output import ProviderStrategy
from pydantic import ConfigDict, RootModel

from .context import InputBudget
from ..backend.fs import load_json, read_text
from ..backend.settings import stage_uses_tools
from .harness import build_model, configure_harness
from .evidence_backend import EvidenceBackend


class Layer2Response(RootModel[dict[str, Any]]):
    """Any JSON object: the schema deliberately does not constrain semantic content."""

    model_config = ConfigDict(json_schema_extra={"properties": {}})


class EmptyFilesystemMiddleware(AgentMiddleware):
    """Replace implicit file capabilities for stages operating on supplied inputs only."""

    @property
    def name(self) -> str:
        """Input none; return the native middleware slot replaced by this tool-free instance."""
        return "FilesystemMiddleware"


def read_only_filesystem(backend=None):
    """Input optional StateBackend; return native read tools shared by graph and input estimates."""
    return FilesystemMiddleware(
        backend=backend, tools=["ls", "glob", "grep", "read_file"],
        human_message_token_limit_before_evict=None,
    )


def create_stage_agent(run_dir: Path, stage: str, checkpointer=None):
    """Input run, stage and optional saver; return its frozen tool-free or read-only graph."""
    configure_harness()
    record = load_json(run_dir / "run.json")
    prompt = read_text(run_dir / "_internal" / "inputs" / "prompts" / f"{stage}.md")
    retrieval = stage_uses_tools(stage)
    backend = CompositeBackend(default=StateBackend(), routes={
        "/evidence/": EvidenceBackend(run_dir),
        "/history/": EvidenceBackend(run_dir, history=True),
    }) if retrieval else StateBackend()
    middleware = read_only_filesystem(backend) if retrieval else EmptyFilesystemMiddleware()
    # Only registered run evidence is readable; checkpoints contain no corpus files.
    return create_deep_agent(
        model=build_model(record["reasoning_effort"]), system_prompt=prompt,
        tools=[], subagents=[], backend=backend,
        middleware=[middleware, InputBudget(run_dir, record["context_policy"], prompt,
                                           Layer2Response.model_json_schema(), middleware.tools if retrieval else ())],
        response_format=ProviderStrategy(Layer2Response, strict=False),
        checkpointer=checkpointer if stage not in {"understanding", "distribution"} else None,
        name=f"layer2-{stage}",
    )


def response_value(result: dict) -> dict:
    """Input a graph result; return its provider-parsed object without content inspection."""
    value = result.get("structured_response")
    if isinstance(value, Layer2Response):
        return value.root
    if isinstance(value, dict):
        return value
    raise ValueError("Layer 2 response has no readable structured JSON object")
