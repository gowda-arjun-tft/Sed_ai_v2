"""Build the one reusable mission-scoped Deep Agents graph."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.agent import configure_provider

from .contracts import MissionOutcome, ResearchContext
from .prompts import lens_system_prompt, supervisor_system_prompt
from .research_tools import make_research_tools
from .settings import LENSES, MODEL_SPEC


@cache
def configure_deepagents() -> None:
    """Share the provider profile and remove the implicit general-purpose helper."""
    from deepagents import (
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        register_harness_profile,
    )

    configure_provider()
    register_harness_profile(
        MODEL_SPEC,
        HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)
        ),
    )


def _permissions(prefix: str) -> list[Any]:
    from deepagents import FilesystemPermission

    return [
        FilesystemPermission(operations=["read"], paths=[f"{prefix}/**"], mode="allow"),
        FilesystemPermission(
            operations=["read"],
            paths=["/large_tool_results/**", "/conversation_history/**"],
            mode="allow",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
        FilesystemPermission(operations=["write"], paths=[f"{prefix}/**"], mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]


def _filesystem(backend: Any, permissions: list[Any]) -> Any:
    from deepagents.middleware import FilesystemMiddleware

    return FilesystemMiddleware(
        backend=backend,
        tools=["ls", "read_file", "write_file"],
        _permissions=permissions,
    )


def _subagent(run_dir: Path, backend: Any, lens: str) -> dict[str, Any]:
    name = lens if lens in LENSES else "additional-researcher"
    prefix = f"/lenses/{lens}"
    permissions = _permissions(prefix)
    return {
        "name": name,
        "description": (
            f"Researches only the {lens} perspective for one mission. "
            "Give it the mission, boundaries, round, exact output path, and for "
            "follow-up only its own first report path plus bare questions."
        ),
        "system_prompt": lens_system_prompt(run_dir, lens),
        "tools": make_research_tools(lens),
        "middleware": [_filesystem(backend, permissions)],
        "permissions": permissions,
    }


def create_mission_supervisor(run_dir: Path, checkpointer: Any = None) -> Any:
    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import StateBackend

    configure_deepagents()
    backend = StateBackend()
    parent_permissions = [
        FilesystemPermission(
            operations=["write"], paths=["/answer.md", "/notes/**"], mode="allow"
        ),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    subagents = [_subagent(run_dir, backend, lens) for lens in LENSES]
    subagents.append(_subagent(run_dir, backend, "additional"))
    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=supervisor_system_prompt(run_dir),
        tools=[],
        middleware=[_filesystem(backend, parent_permissions)],
        backend=backend,
        permissions=parent_permissions,
        subagents=subagents,
        context_schema=ResearchContext,
        checkpointer=checkpointer,
        response_format=MissionOutcome,
        name="cdi-layer3-mission-supervisor",
    )


def structured_value(result: dict[str, Any]) -> MissionOutcome:
    value = result.get("structured_response")
    return value if isinstance(value, MissionOutcome) else MissionOutcome.model_validate(value)
