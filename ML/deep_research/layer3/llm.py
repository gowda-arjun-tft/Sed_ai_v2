"""Agent construction.

No middleware. No call ceilings, tool-call ceilings or retry policies wrapped
around the model, and no harness profile narrowing what it can reach for. The
researcher keeps the full built-in tool surface alongside its own tools.

Structured output is used where the surrounding code needs a machine-readable
answer -- that is a delivery format, not a restriction on what the model may
think or say. The researcher itself has no `response_format`: its report is free
prose.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from .calculation_tool import run_python
from .contracts import (
    AnswerDraft,
    GapDecision,
    QuestionSet,
    ResearchContext,
    ResearchState,
)
from .prompts import aggregator_prompt, lens_system_prompt
from .research_tools import (
    cite,
    finish_round,
    read_source,
    search_web,
    skip_source,
)
from .settings import MODEL_SPEC, REASONING_EFFORT


@cache
def configure_deepagents() -> None:
    from deepagents import ProviderProfile, register_provider_profile

    register_provider_profile(
        MODEL_SPEC,
        ProviderProfile(
            init_kwargs={
                "reasoning_effort": REASONING_EFFORT,
                "store": False,
                "use_responses_api": True,
            }
        ),
    )
    # No harness profile is registered. Nothing is excluded from the tool
    # surface, and the general-purpose subagent stays available.


def create_research_agent(lens: str, focus: str, checkpointer: Any) -> Any:
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend

    configure_deepagents()
    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=lens_system_prompt(lens, focus),
        tools=[search_web, read_source, skip_source, cite, run_python, finish_round],
        middleware=[],
        backend=StateBackend(),
        state_schema=ResearchState,
        context_schema=ResearchContext,
        checkpointer=checkpointer,
        name=f"cdi-layer3-{lens}",
    )


def create_structured_agent(kind: str, checkpointer: Any) -> Any:
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend

    configure_deepagents()
    formats = {
        "aggregator_pass1": QuestionSet,
        "gap_decision": GapDecision,
        "aggregator_pass2": AnswerDraft,
    }
    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=aggregator_prompt(kind),
        tools=[],
        middleware=[],
        backend=StateBackend(),
        response_format=formats[kind],
        checkpointer=checkpointer,
        name=f"cdi-layer3-{kind}",
    )


def structured_value(result: dict[str, Any], expected: type[Any]) -> Any:
    value = result.get("structured_response")
    if isinstance(value, expected):
        return value
    return expected.model_validate(value)
