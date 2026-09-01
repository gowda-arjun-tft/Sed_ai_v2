"""Tool-free structured-output Deep Agent for each fact-sheet chunk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents.structured_output import ProviderStrategy
from pydantic import ConfigDict, RootModel

from .fs import load_json, read_text
from .harness import build_model, configure_harness
from .settings import PROMPTS_DIR


class Layer2Response(RootModel[dict[str, Any]]):
    """Any top-level JSON object, without a semantic content schema."""

    # LangChain's OpenAI adapter requires this standard object-schema member.
    # It remains empty, so every top-level key and nested value stays permitted.
    model_config = ConfigDict(json_schema_extra={"properties": {}})


def system_prompt(planner_path: Path) -> str:
    """Input a planner snapshot; return the single router prompt used by chunk agents."""
    instructions = read_text(PROMPTS_DIR / "chunk_router.md").rstrip()
    planner = read_text(planner_path).rstrip()
    return f"{instructions}\n\n<routing_contract>\n{planner}\n</routing_contract>"


def create_chunk_agent(run_dir: Path) -> Any:
    """Input a run path; return its reusable JSON-mode graph with no model tools."""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import AgentMiddleware

    class EmptyFilesystemMiddleware(AgentMiddleware):
        @property
        def name(self) -> str:
            """Input none; return the built-in name that disables filesystem tools."""
            return "FilesystemMiddleware"

    configure_harness()
    record = load_json(run_dir / "run.json")
    reasoning_effort = record["reasoning_effort"]
    graph = create_deep_agent(
        model=build_model(reasoning_effort),
        system_prompt=system_prompt(run_dir / "inputs" / "planner_prompt.md"),
        tools=[],
        middleware=[EmptyFilesystemMiddleware()],
        subagents=[],
        response_format=ProviderStrategy(Layer2Response, strict=False),
        name="cdi-layer2-chunk-router",
    )
    return graph


def _partition_chunk(
    chunk: str, index: int, encoding_name: str, overlap_tokens: int
) -> tuple[str, str]:
    """Input one chunk; return overlap and new text for the tagged model request."""
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
    encoding_name: str,
    overlap_tokens: int,
) -> str:
    """Input a frozen chunk window; return its overlap-aware user message."""
    overlap, new = _partition_chunk(chunk, index, encoding_name, overlap_tokens)
    return (
        f'<fact_sheet_chunk index="{index}" total="{total}">\n'
        f"<overlap_context>\n{overlap}\n</overlap_context>\n"
        f"<new_content>\n{new}\n</new_content>\n"
        "</fact_sheet_chunk>"
    )


def response_value(result: dict[str, Any]) -> dict[str, Any]:
    """Input a graph result; return its provider-parsed JSON object for persistence."""
    value = result.get("structured_response")
    if isinstance(value, Layer2Response):
        return value.root
    raise ValueError("Layer 2 response has no structured JSON object")
