from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from .settings import MODEL_SPEC, REASONING_EFFORT


@cache
def configure_deepagents() -> None:
    from deepagents import (
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        ProviderProfile,
        register_harness_profile,
        register_provider_profile,
    )

    register_provider_profile(
        MODEL_SPEC,
        ProviderProfile(init_kwargs={"reasoning_effort": REASONING_EFFORT}),
    )
    register_harness_profile(
        MODEL_SPEC,
        HarnessProfile(
            excluded_tools=frozenset(
                {"write_file", "edit_file", "delete", "execute"}
            ),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
def create_routing_agent(
    run_dir: Path,
    planner_text: str,
    tools: list[Any],
) -> Any:
    from deepagents import create_deep_agent
    from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
    from langchain.agents.middleware import TodoListMiddleware

    configure_deepagents()
    prompt = f"""You allocate property fact blocks to research agents. Do no research and make no findings.

{planner_text}

For the one piece in each user message, call append_to_bucket for every complete fact block and
every agent whose subject it touches. Use _unrouted only when no roster agent needs it. Copy each
fact block exactly. Then call mark_piece_done. Do not finish before mark_piece_done succeeds.
"""
    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=prompt,
        tools=tools,
        middleware=[TodoListMiddleware()],
        backend=CompositeBackend(
            default=StateBackend(),
            routes={
                "/run/": FilesystemBackend(
                    root_dir=str(run_dir.resolve()),
                    virtual_mode=True,
                )
            },
        ),
        subagents=[],
        name="cdi-layer2-router",
    )


def create_mission_agent() -> Any:
    from deepagents import create_deep_agent
    from pydantic import BaseModel, Field

    class MissionDraft(BaseModel):
        mission: str = Field(
            min_length=1,
            description="Property-specific research mission in plain prose",
        )

    configure_deepagents()
    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=(
            "Write only the property-specific mission requested. Do no research. "
            "Use only the supplied definition and bucket. Name what the researcher "
            "must establish, conflicts it must settle, and unusual property facts "
            "it should know."
        ),
        tools=[],
        response_format=MissionDraft,
        subagents=[],
        name="cdi-layer2-mission-writer",
    )
