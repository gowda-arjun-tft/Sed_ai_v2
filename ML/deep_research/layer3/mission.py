from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from ML.deep_research.layer2.fs import read_text, slug
from ML.deep_research.layer2.planner import load_planner

from .settings import AGENT_NAMES


def stage_thread_id(
    run_id: str,
    stage: str,
    actor: str,
    batch: int,
    attempt: int,
) -> str:
    """Stable isolated checkpoint identity for one STORM stage attempt."""
    return str(uuid5(NAMESPACE_URL, f"cdi:{run_id}:{stage}:{actor}:{batch}:{attempt}"))


def load_research_input(run_dir: Path) -> list[dict[str, Any]]:
    """Load the eight isolated domain assignments."""
    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    by_name = {item["name"]: item for item in definitions}
    missions = []
    for name in AGENT_NAMES:
        mission = read_text(run_dir / "inputs" / "mission_md" / f"{slug(name)}.md")
        missions.append(mission)
    return [
        {
            "name": name,
            "mission": mission,
            "boundaries": {
                "mandate": by_name[name]["mandate"],
                "handoffs": by_name[name]["handoffs"],
            },
        }
        for name, mission in zip(AGENT_NAMES, missions, strict=True)
    ]
