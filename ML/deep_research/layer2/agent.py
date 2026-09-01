"""Tool-free structured-output Deep Agent for each fact-sheet chunk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents.structured_output import ProviderStrategy
from pydantic import RootModel

from .fs import load_json, read_text, slug
from .harness import build_model, configure_harness
from .settings import CHUNK_INPUT_PARTITIONING, PROMPTS_DIR


class Layer2Response(RootModel[dict[str, Any]]):
    """Any top-level JSON object, without a semantic content schema."""


def domain_key(name: str) -> str:
    """Stable JSON field name for one domain."""
    return slug(name).replace("-", "_")


def system_prompt(planner_path: Path) -> str:
    """Combine the lean routing contract with the planner snapshot verbatim."""
    instructions = read_text(PROMPTS_DIR / "chunk_router.md").rstrip()
    planner = read_text(planner_path).rstrip()
    return f"{instructions}\n\n<routing_contract>\n{planner}\n</routing_contract>"


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


def _partition_chunk(
    chunk: str, index: int, encoding_name: str, overlap_tokens: int
) -> tuple[str, str]:
    """Separate repeated source context from new source tokens."""
    if index == 1:
        return "", chunk
    import tiktoken

    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(chunk)
    boundary = min(overlap_tokens, len(tokens))
    return encoding.decode(tokens[:boundary]), encoding.decode(tokens[boundary:])


def chunk_request(
    chunk: str,
    index: int,
    total: int,
    chunking: dict[str, Any] | None = None,
) -> str:
    """Build one legacy or overlap-aware isolated chunk invocation."""
    if (chunking or {}).get("input_partitioning") == CHUNK_INPUT_PARTITIONING:
        overlap, new = _partition_chunk(
            chunk,
            index,
            str(chunking.get("encoding") or "o200k_base"),
            int(chunking.get("overlap_tokens") or 0),
        )
        return (
            f'<fact_sheet_chunk index="{index}" total="{total}">\n'
            f"<overlap_context>\n{overlap}\n</overlap_context>\n"
            f"<new_content>\n{new}\n</new_content>\n"
            "</fact_sheet_chunk>"
        )
    return (
        f'<fact_sheet_chunk index="{index}" total="{total}">\n'
        f"{chunk}\n"
        "</fact_sheet_chunk>"
    )


def response_value(result: dict[str, Any]) -> dict[str, Any]:
    """Return LangChain's parsed top-level JSON object."""
    value = result.get("structured_response")
    if isinstance(value, Layer2Response):
        return value.root
    raise ValueError("Layer 2 response has no structured JSON object")
