from __future__ import annotations

import json
from typing import Any

from ML.deep_research.layer2.fs import read_text

from .settings import LENSES, PROMPTS_DIR


def lens_system_prompt(lens: str, focus: str = "") -> str:
    shared = read_text(PROMPTS_DIR / "shared_rules.md")
    if lens in LENSES:
        specific = read_text(PROMPTS_DIR / "lenses" / f"{lens}.md")
    else:
        specific = (
            f"You are the additional research lens named {lens}.\n"
            f"Your unique focus is: {focus}"
        )
    return f"{shared.strip()}\n\n{specific.strip()}\n"


def mission_message(
    mission: dict[str, Any],
    definition: dict[str, Any],
    questions: tuple[str, ...] = (),
) -> str:
    payload = {
        "mission": mission,
        "boundaries": {
            "establishes": definition.get("establishes", []),
            "do_not_cover": definition.get("do_not_cover", []),
            "take_as_given": definition.get("take_as_given", []),
            "web_sources": definition.get("web_sources", []),
        },
    }
    text = "Research this mission:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if questions:
        text += (
            "\n\nThis is a question-only second round. Research these questions yourself. "
            "They have no attribution and contain no other researcher's report:\n- "
            + "\n- ".join(questions)
        )
    return text


def aggregator_prompt(name: str) -> str:
    return read_text(PROMPTS_DIR / f"{name}.md")
