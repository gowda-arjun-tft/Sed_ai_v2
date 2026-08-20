from __future__ import annotations

from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import load_json, slug
from ML.deep_research.layer2.planner import load_planner

from .settings import AGENT_NAMES


def load_inputs(run_dir: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    by_name = {item["name"]: item for item in definitions}
    values = []
    for name in AGENT_NAMES:
        mission = load_json(run_dir / "inputs" / "missions" / f"{slug(name)}.json")
        if mission.get("agent") != name:
            raise ValueError(f"mission agent mismatch: {name}")
        values.append((mission, by_name[name]))
    return values
