from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .settings import AGENT_NAMES
from .fs import read_text


def load_planner(path: Path) -> tuple[str, list[dict[str, Any]]]:
    text = read_text(path)
    match = re.search(
        r"<!-- AGENTS_JSON_START -->\s*(.*?)\s*<!-- AGENTS_JSON_END -->",
        text,
        re.S,
    )
    if not match:
        raise ValueError("planner_prompt.md has no AGENTS_JSON block")
    agents = json.loads(match.group(1))
    names = [agent.get("name") for agent in agents]
    if len(agents) != 14 or names != AGENT_NAMES:
        raise ValueError(
            "planner_prompt.md must contain the fourteen frozen agent names in order"
        )
    required = {
        "name",
        "establishes",
        "do_not_cover",
        "take_as_given",
        "web_sources",
    }
    if any(set(agent) != required for agent in agents):
        raise ValueError(f"every planner agent must contain exactly {sorted(required)}")
    return text, agents
