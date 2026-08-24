"""Shared Deep Agents model configuration for Layer 2 and Layer 3."""

from __future__ import annotations

from functools import cache
from typing import Any

from .settings import (
    MODEL_SPEC,
    PROVIDER_MAX_RETRIES,
    REASONING_EFFORT,
)


@cache
def configure_provider() -> None:
    """Register the shared Responses API profile without an output-token cap."""
    from deepagents import ProviderProfile, register_provider_profile

    register_provider_profile(
        MODEL_SPEC,
        ProviderProfile(
            init_kwargs={
                "reasoning_effort": REASONING_EFFORT,
                "store": False,
                "use_responses_api": True,
                "timeout": 600,
                "max_retries": PROVIDER_MAX_RETRIES,
            }
        ),
    )


@cache
def configure_harness() -> None:
    """Disable the process-wide implicit general-purpose subagent."""
    from deepagents import (
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        register_harness_profile,
    )

    register_harness_profile(
        MODEL_SPEC,
        HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            excluded_middleware=frozenset(
                {"SummarizationMiddleware", "PatchToolCallsMiddleware"}
            ),
            tool_description_overrides={
                "task": (
                    "Delegate one complete research or verification assignment to a fixed "
                    "specialist. Available specialists:\n{available_agents}\n"
                    "Send independent assignments as multiple task calls in one response. "
                    "Each specialist sees only its assignment and returns one Markdown report."
                )
            },
        ),
    )


def build_model(reasoning_effort: str = REASONING_EFFORT) -> Any:
    """Build the fixed Layer 2 model; the agent owns its response format."""
    from deepagents.profiles.provider import apply_provider_profile
    from langchain.chat_models import init_chat_model

    configure_provider()
    options = apply_provider_profile(MODEL_SPEC)
    options["reasoning_effort"] = reasoning_effort
    return init_chat_model(MODEL_SPEC, **options)
