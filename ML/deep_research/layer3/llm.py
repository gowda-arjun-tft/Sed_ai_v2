"""Build the domain-scoped STORM Deep Agent harnesses."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from ML.deep_research.layer2.harness import (
    configure_harness,
    configure_provider,
)
from ML.deep_research.layer2.fs import load_json

from .contracts import LENS_NAMES, VERIFIER_NAME, ResearchContext
from .memory import context_policy, evidence_eviction, research_summarization
from .prompts import (
    LENS_DESCRIPTIONS,
    coordinator_system_prompt,
    lens_system_prompt,
    synthesis_system_prompt,
    verifier_system_prompt,
)
from .research_tools import make_research_tools
from .settings import (
    MODEL_MAX_RETRIES,
    MODEL_SPEC,
    MODEL_TIMEOUT_SECONDS,
    REASONING_EFFORT,
)


class _NoFilesystemMiddleware(AgentMiddleware):
    """Replace Deep Agents' file middleware for evidence-only subagents."""

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


def _subagents(
    run_dir: Path,
    *,
    model: Any = None,
    backend: Any = None,
) -> list[dict[str, Any]]:
    """Build the six looping research subagents from the run-frozen policy.

    These are the only agents that loop while pulling large payloads into their
    own history, so they are the only ones given eviction and summarization.
    Runs created before the versioned context policy keep their original
    no-compaction behavior.

    `model` is optional because the summarizer needs a resolved chat model while
    the rest of a spec does not, and constructing one requires an API key.
    Without a model the specs still evict when their run enables compaction;
    only summarization is absent.
    """
    order = [_NoFilesystemMiddleware()]
    policy = context_policy(run_dir)
    if policy is not None:
        order.append(evidence_eviction(policy))
        if model is not None:
            order.append(research_summarization(model, backend, policy))

    def spec(name: str, description: str, system_prompt: str) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "system_prompt": system_prompt,
            "tools": make_research_tools(name),
            "middleware": list(order),
        }

    agents = [
        spec(lens, LENS_DESCRIPTIONS[lens], lens_system_prompt(run_dir, lens))
        for lens in LENS_NAMES
    ]
    agents.append(
        spec(
            VERIFIER_NAME,
            "Independently verifies a coherent cluster of cited claims and sources.",
            verifier_system_prompt(run_dir),
        )
    )
    return agents


def _model_and_backend(run_dir: Path) -> tuple[Any, Any]:
    """Resolve the shared model and backend a graph and its subagents both need."""
    from deepagents.backends import StateBackend

    configure_deepagents()
    return build_layer3_model(run_dir), StateBackend()


def _graph(
    *,
    system_prompt: str,
    model: Any,
    backend: Any,
    subagents: list[dict[str, Any]],
    name: str,
    checkpointer: Any,
) -> Any:
    from deepagents import create_deep_agent

    configure_deepagents()
    return create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        tools=[],
        middleware=[_NoFilesystemMiddleware()],
        backend=backend,
        subagents=subagents,
        context_schema=ResearchContext,
        checkpointer=checkpointer,
        response_format=None,
        name=name,
    )


def create_domain_coordinator_harness(
    run_dir: Path,
    checkpointer: Any = None,
) -> Any:
    model, backend = _model_and_backend(run_dir)
    return _graph(
        system_prompt=coordinator_system_prompt(run_dir),
        model=model,
        backend=backend,
        subagents=_subagents(run_dir, model=model, backend=backend),
        name="domain-storm-coordinator",
        checkpointer=checkpointer,
    )


def create_synthesis_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    # One stateless call over the eight finished domain reports: no loop, no
    # tools, nothing to compact.
    model, backend = _model_and_backend(run_dir)
    return _graph(
        system_prompt=synthesis_system_prompt(run_dir),
        model=model,
        backend=backend,
        subagents=[],
        name="property-synthesis",
        checkpointer=checkpointer,
    )


def final_text(result: dict[str, Any]) -> str:
    """Return the model's final assistant content without grading it."""
    for message in reversed(result.get("messages", [])):
        if getattr(message, "type", "") == "ai":
            value = str(message.text)
            return value
    return ""
