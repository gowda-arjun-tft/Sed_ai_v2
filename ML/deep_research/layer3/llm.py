"""Build the direct Layer 3 Deep Agent graphs."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.harness import (
    configure_harness,
    configure_provider,
    context_middleware,
)

from .contracts import (
    ResearchContext,
    ResearchOutcome,
    ReviewOutcome,
)
from .prompts import domain_system_prompt, reviewer_system_prompt, synthesis_system_prompt
from .research_tools import make_research_tools
from .settings import (
    DOMAIN_NAMES,
    MODEL_MAX_RETRIES,
    MODEL_SPEC,
    MODEL_TIMEOUT_SECONDS,
    REASONING_EFFORT,
)


@cache
def configure_deepagents() -> None:
    configure_provider()
    configure_harness()


def build_layer3_model() -> Any:
    """Build the shared model policy with Layer 3's low reasoning effort."""
    from deepagents.profiles.provider import apply_provider_profile
    from langchain.chat_models import init_chat_model

    configure_provider()
    options = apply_provider_profile(MODEL_SPEC)
    options.update(
        reasoning_effort=REASONING_EFFORT,
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
    )
    return init_chat_model(MODEL_SPEC, **options)


def _permissions(*, read: tuple[str, ...]) -> list[Any]:
    from deepagents import FilesystemPermission

    internal = ("/large_tool_results/**", "/conversation_history/**")
    return [
        *(
            FilesystemPermission(operations=["read"], paths=[path], mode="allow")
            for path in (*read, *internal)
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]


def _graph(
    *,
    system_prompt: str,
    tools: list[Any],
    read: tuple[str, ...],
    response_format: type | None,
    name: str,
    checkpointer: Any,
) -> Any:
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend
    from deepagents.middleware import FilesystemMiddleware
    from langchain.agents.structured_output import ProviderStrategy

    configure_deepagents()
    backend = StateBackend()
    model = build_layer3_model()
    permissions = _permissions(read=read)
    return create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=["read_file"],
                _permissions=permissions,
            ),
            context_middleware(model, backend),
        ],
        backend=backend,
        permissions=permissions,
        subagents=[],
        context_schema=ResearchContext,
        checkpointer=checkpointer,
        response_format=ProviderStrategy(response_format) if response_format else None,
        name=name,
    )


def create_domain_harness(run_dir: Path, domain: str, checkpointer: Any = None) -> Any:
    if domain not in DOMAIN_NAMES:
        raise ValueError(f"unknown Layer 3 domain: {domain}")
    return _graph(
        system_prompt=domain_system_prompt(run_dir, domain),
        tools=make_research_tools(domain),
        read=(),
        response_format=ResearchOutcome,
        name=domain,
        checkpointer=checkpointer,
    )


def create_reviewer_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    return _graph(
        system_prompt=reviewer_system_prompt(run_dir),
        tools=[],
        read=("/domains/**",),
        response_format=ReviewOutcome,
        name="property-reviewer",
        checkpointer=checkpointer,
    )


def create_synthesis_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    return _graph(
        system_prompt=synthesis_system_prompt(run_dir),
        tools=[],
        read=("/domains/**", "/review.md"),
        response_format=None,
        name="property-synthesis",
        checkpointer=checkpointer,
    )


def structured_value(result: dict[str, Any], schema: type) -> Any:
    value = result.get("structured_response")
    return value if isinstance(value, schema) else schema.model_validate(value)


def final_text(result: dict[str, Any]) -> str:
    """Return the final assistant Markdown from a completed graph."""
    for message in reversed(result.get("messages", [])):
        if getattr(message, "type", "") == "ai":
            value = str(message.text).strip()
            if value:
                return value
    raise ValueError("synthesis returned no final Markdown")
