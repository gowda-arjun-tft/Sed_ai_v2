"""Load the trusted eight-domain roster embedded in the planner prompt."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .fs import read_text


def load_planner(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Input a planner path; return its full prompt and roster for prompting and setup."""
    text = read_text(path)
    match = re.search(
        r"<!-- AGENTS_JSON_START -->\s*(.*?)\s*<!-- AGENTS_JSON_END -->",
        text,
        re.S,
    )
    if not match:
        raise ValueError("planner_prompt.md has no AGENTS_JSON block")
    return text, json.loads(match.group(1))
