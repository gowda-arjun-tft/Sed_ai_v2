"""Build the direct domain-research and synthesis Deep Agent harnesses."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from ML.deep_research.layer2.ML.harness import (
    configure_harness,
    configure_provider,
)
from ML.deep_research.layer2.backend.fs import load_json

from .contracts import RESEARCHER_NAME, ResearchContext
from .memory import context_policy, evidence_eviction, research_summarization
from .prompts import researcher_system_prompt, synthesis_system_prompt
from .research_tools import make_research_tools
from .settings import (
    MODEL_MAX_RETRIES,
    MODEL_SPEC,
    MODEL_TIMEOUT_SECONDS,
    REASONING_EFFORT,
)


class _NoFilesystemMiddleware(AgentMiddleware):
    """Replace Deep Agents' file middleware for evidence-only graphs."""

    @property
    def name(self) -> str:
        return "FilesystemMiddleware"


@cache
def configure_deepagents() -> None:
    configure_provider()
    configure_harness()


def build_layer3_model(run_dir: Path) -> Any:
    """Build the fixed Responses model without an output-token ceiling."""
    from deepagents.profiles.provider import apply_provider_profile
    from langchain.chat_models import init_chat_model

    configure_provider()
    options = apply_provider_profile(MODEL_SPEC)
    options.update(
        reasoning_effort=load_json(run_dir / "run.json").get(
            "reasoning_effort", REASONING_EFFORT
        ),
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
    )
    return init_chat_model(MODEL_SPEC, **options)


def _research_middleware(run_dir: Path, model: Any, backend: Any) -> list[Any]:
    """Build the direct researcher's run-frozen context management stack."""
    order = [_NoFilesystemMiddleware()]
    policy = context_policy(run_dir)
    if policy is not None:
        order.append(evidence_eviction(policy))
        order.append(research_summarization(model, backend, policy))
    return order


def _model_and_backend(run_dir: Path) -> tuple[Any, Any]:
    """Resolve the shared model and state backend for one graph."""
    from deepagents.backends import StateBackend

    configure_deepagents()
    return build_layer3_model(run_dir), StateBackend()


def _graph(
    *,
    system_prompt: str,
    model: Any,
    backend: Any,
    tools: list[Any],
    middleware: list[Any],
    name: str,
    checkpointer: Any,
) -> Any:
    from deepagents import create_deep_agent

    configure_deepagents()
    return create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=middleware,
        backend=backend,
        subagents=[],
        context_schema=ResearchContext,
        checkpointer=checkpointer,
        response_format=None,
        name=name,
    )


def create_direct_research_harness(
    run_dir: Path,
    system_prompt: str,
    name: str,
    checkpointer: Any = None,
) -> Any:
    """Build one looping evidence researcher for Layer 3 or Layer 4."""
    model, backend = _model_and_backend(run_dir)
    return _graph(
        system_prompt=system_prompt,
        model=model,
        backend=backend,
        tools=make_research_tools(name),
        middleware=_research_middleware(run_dir, model, backend),
        name=name,
        checkpointer=checkpointer,
    )


def create_tool_free_harness(
    run_dir: Path,
    system_prompt: str,
    name: str,
    checkpointer: Any = None,
) -> Any:
    """Build one checkpointed free-form Markdown call without tools or loops."""
    model, backend = _model_and_backend(run_dir)
    return _graph(
        system_prompt=system_prompt,
        model=model,
        backend=backend,
        tools=[],
        middleware=[_NoFilesystemMiddleware()],
        name=name,
        checkpointer=checkpointer,
    )


def create_domain_researcher_harness(
    run_dir: Path,
    checkpointer: Any = None,
) -> Any:
    return create_direct_research_harness(
        run_dir,
        researcher_system_prompt(run_dir),
        RESEARCHER_NAME,
        checkpointer,
    )


def create_synthesis_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    # One stateless call over the eight finished domain reports: no loop, no
    # tools, nothing to compact.
    return create_tool_free_harness(
        run_dir,
        synthesis_system_prompt(run_dir),
        "property-synthesis",
        checkpointer,
    )


def final_text(result: dict[str, Any]) -> str:
    """Return the model's final assistant content without grading it."""
    for message in reversed(result.get("messages", [])):
        if getattr(message, "type", "") == "ai":
            value = str(message.text)
            return value
    return ""
