"""Shared Deep Agents model configuration for Layer 2 and Layer 3."""

from __future__ import annotations

from functools import cache
from typing import Any

from .settings import (
    MODEL_SPEC,
    PROVIDER_MAX_RETRIES,
    REASONING_EFFORT,
    SUMMARIZATION_KEEP_TOKENS,
    SUMMARIZATION_TRIGGER_TOKENS,
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
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)
        ),
    )


def build_model() -> Any:
    """Build the fixed model after applying the provider profile."""
    from deepagents.profiles.provider import apply_provider_profile
    from langchain.chat_models import init_chat_model

    configure_provider()
    return init_chat_model(MODEL_SPEC, **apply_provider_profile(MODEL_SPEC))


def context_middleware(model: Any, backend: Any) -> Any:
    """Compact only Layer 3's long research conversations."""
    from deepagents.middleware.summarization import SummarizationMiddleware

    return SummarizationMiddleware(
        model=model,
        backend=backend,
        trigger=("tokens", SUMMARIZATION_TRIGGER_TOKENS),
        keep=("tokens", SUMMARIZATION_KEEP_TOKENS),
        trim_tokens_to_summarize=None,
        truncate_args_settings={
            "trigger": ("tokens", SUMMARIZATION_TRIGGER_TOKENS),
            "keep": ("tokens", SUMMARIZATION_KEEP_TOKENS),
        },
    )
