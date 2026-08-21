"""Tool-free structured Deep Agent used independently for each fact-sheet chunk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from .fs import read_text, slug
from .harness import build_model, configure_harness
from .planner import load_planner
from .settings import PROMPTS_DIR


class ContextEntry(BaseModel):
    """One model-routed fact; source locators are intentionally excluded."""

    model_config = ConfigDict(extra="forbid")
    section: str
    fact: str
    means: str


class DomainChunk(BaseModel):
    """One domain's contribution from one independent chunk."""

    model_config = ConfigDict(extra="forbid")
    mission: str
    context: list[ContextEntry]


def domain_key(name: str) -> str:
    """Stable structured-output field name for one frozen domain."""
    return slug(name).replace("-", "_")


def response_schema(definitions: list[dict[str, Any]]) -> type[BaseModel]:
    """Create a schema with one required property per authoritative domain."""
    fields = {
        domain_key(item["name"]): (
            DomainChunk,
            Field(description=item["mandate"]),
        )
        for item in definitions
    }
    return create_model(
        "ChunkMissionBatch",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def system_prompt(definitions: list[dict[str, Any]]) -> str:
    """Combine the lean routing contract with the frozen domain definitions."""
    instructions = read_text(PROMPTS_DIR / "chunk_router.md").rstrip()
    roster = json.dumps(definitions, ensure_ascii=False, indent=2)
    return f"{instructions}\n\n<domain_definitions>\n{roster}\n</domain_definitions>"


def create_chunk_agent(run_dir: Path) -> tuple[Any, type[BaseModel]]:
    """Compile one reusable graph with structured output and no model tools."""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import AgentMiddleware
    from langchain.agents.structured_output import ProviderStrategy

    class EmptyFilesystemMiddleware(AgentMiddleware):
        @property
        def name(self) -> str:
            return "FilesystemMiddleware"

    class EmptySubAgentMiddleware(AgentMiddleware):
        @property
        def name(self) -> str:
            return "SubAgentMiddleware"

    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    schema = response_schema(definitions)
    configure_harness()
    graph = create_deep_agent(
        model=build_model(),
        system_prompt=system_prompt(definitions),
        tools=[],
        middleware=[EmptyFilesystemMiddleware(), EmptySubAgentMiddleware()],
        subagents=[],
        response_format=ProviderStrategy(schema),
        name="cdi-layer2-chunk-router",
    )
    return graph, schema


def chunk_request(chunk: str, index: int, total: int) -> str:
    """Build the single user message for one isolated chunk invocation."""
    return (
        f"Route chunk {index} of {total}. Return the required structured response.\n\n"
        "<fact_sheet_chunk>\n"
        f"{chunk}\n"
        "</fact_sheet_chunk>"
    )


def structured_value(result: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
    """Read the provider-native structured response from a graph result."""
    value = result.get("structured_response")
    return value if isinstance(value, schema) else schema.model_validate(value)
