"""Shared Deep Agents model configuration for Layers 2, 3, and 4."""

from __future__ import annotations

from functools import cache
from typing import Any

from ..backend.settings import (
    MODEL_SPEC,
    PROVIDER_MAX_RETRIES,
    REASONING_EFFORT,
)


@cache
def configure_provider() -> None:
    """Input none; cache the provider profile used by all CDI model builders."""
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
    """Input none; cache the no-subagent, no-repair profile used by CDI graphs."""
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
        ),
    )


def build_model(reasoning_effort: str = REASONING_EFFORT, **overrides: Any) -> Any:
    """Return the fixed provider model; optional native client overrides leave default callers unchanged."""
    from deepagents.profiles.provider import apply_provider_profile
    from langchain.chat_models import init_chat_model

    configure_provider()
    options = apply_provider_profile(MODEL_SPEC)
    options["reasoning_effort"] = reasoning_effort
    options.update(overrides)
    return init_chat_model(MODEL_SPEC, **options)
