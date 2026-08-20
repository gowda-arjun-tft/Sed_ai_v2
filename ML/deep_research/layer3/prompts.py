from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import read_text

from .settings import LENSES


def _snapshot(run_dir: Path) -> Path:
    return run_dir / "inputs" / "prompts"


def supervisor_system_prompt(run_dir: Path) -> str:
    """Use the immutable procedure copied into this run."""
    return read_text(_snapshot(run_dir) / "SKILL.md")


def lens_system_prompt(run_dir: Path, lens: str) -> str:
    name = lens if lens in LENSES else "additional"
    root = _snapshot(run_dir)
    return (
        read_text(root / "shared_rules.md").strip()
        + "\n\n"
        + read_text(root / "lenses" / f"{name}.md").strip()
        + "\n"
    )


def mission_message(mission: dict[str, Any], definition: dict[str, Any]) -> str:
    payload = {
        "mission": mission,
        "boundaries": {
            "establishes": definition.get("establishes", []),
            "do_not_cover": definition.get("do_not_cover", []),
            "take_as_given": definition.get("take_as_given", []),
            "web_sources": definition.get("web_sources", []),
        },
    }
    return (
        "Complete this mission using the mandatory procedure. Stage every report "
        "and /answer.md before returning MissionOutcome.\n\n<mission_data>\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n</mission_data>"
    )
