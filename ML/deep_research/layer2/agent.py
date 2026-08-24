"""Tool-free structured-output Deep Agent for each fact-sheet chunk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents.structured_output import ProviderStrategy
from pydantic import RootModel

from .fs import load_json, read_text, slug
from .harness import build_model, configure_harness
from .settings import PROMPTS_DIR


class Layer2Response(RootModel[dict[str, Any]]):
    """Any top-level JSON object, without a semantic content schema."""


def domain_key(name: str) -> str:
    """Stable JSON field name for one domain."""
    return slug(name).replace("-", "_")


def system_prompt(planner_path: Path) -> str:
    """Combine the lean routing contract with the planner snapshot verbatim."""
    instructions = read_text(PROMPTS_DIR / "chunk_router.md").rstrip()
    planner = read_text(planner_path).rstrip()
    return f"{instructions}\n\n<domain_definitions>\n{planner}\n</domain_definitions>"


def create_chunk_agent(run_dir: Path) -> Any:
    """Compile one reusable graph with native JSON mode and no model tools."""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import AgentMiddleware

    class EmptyFilesystemMiddleware(AgentMiddleware):
        @property
        def name(self) -> str:
            return "FilesystemMiddleware"

    class EmptySubAgentMiddleware(AgentMiddleware):
        @property
        def name(self) -> str:
            return "SubAgentMiddleware"

    configure_harness()
    reasoning_effort = load_json(run_dir / "run.json")["reasoning_effort"]
    graph = create_deep_agent(
        model=build_model(reasoning_effort),
        system_prompt=system_prompt(run_dir / "inputs" / "planner_prompt.md"),
        tools=[],
        middleware=[EmptyFilesystemMiddleware(), EmptySubAgentMiddleware()],
        subagents=[],
        response_format=ProviderStrategy(Layer2Response, strict=False),
        name="cdi-layer2-chunk-router",
    )
    return graph


def chunk_request(chunk: str, index: int, total: int) -> str:
    """Build the single user message for one isolated chunk invocation."""
    return (
        f"Route chunk {index} of {total}. Return one JSON object.\n\n"
        "<fact_sheet_chunk>\n"
        f"{chunk}\n"
        "</fact_sheet_chunk>"
    )


def response_value(result: dict[str, Any]) -> dict[str, Any]:
    """Return LangChain's parsed top-level JSON object."""
    value = result.get("structured_response")
    if isinstance(value, Layer2Response):
        return value.root
    raise ValueError("Layer 2 response has no structured JSON object")
