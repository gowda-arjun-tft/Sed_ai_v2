"""Layer 4 harnesses built from the Layer 3 research engine."""

from pathlib import Path
from typing import Any

from ML.deep_research.layer3.llm import (
    create_direct_research_harness,
    create_tool_free_harness,
)

from .prompts import (
    candidate_system_prompt,
    internal_system_prompt,
    researcher_system_prompt,
    synthesis_system_prompt,
)
from .settings import (
    EXTERNAL_CANDIDATE_SEGREGATOR_NAME,
    EXTERNAL_RESEARCHER_NAME,
    INTERNAL_SEGREGATOR_NAME,
    SYNTHESIS_NAME,
)


def create_internal_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    return create_tool_free_harness(
        run_dir,
        internal_system_prompt(run_dir),
        INTERNAL_SEGREGATOR_NAME,
        checkpointer,
    )


def create_candidate_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    return create_tool_free_harness(
        run_dir,
        candidate_system_prompt(run_dir),
        EXTERNAL_CANDIDATE_SEGREGATOR_NAME,
        checkpointer,
    )


def create_external_researcher_harness(
    run_dir: Path,
    checkpointer: Any = None,
) -> Any:
    return create_direct_research_harness(
        run_dir,
        researcher_system_prompt(run_dir),
        EXTERNAL_RESEARCHER_NAME,
        checkpointer,
    )


def create_synthesis_harness(run_dir: Path, checkpointer: Any = None) -> Any:
    return create_tool_free_harness(
        run_dir,
        synthesis_system_prompt(run_dir),
        SYNTHESIS_NAME,
        checkpointer,
    )

