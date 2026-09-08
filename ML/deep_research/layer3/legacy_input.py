"""Historical Layer 2 input parsing and Markdown rendering for Layer 3."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.backend.fs import atomic_write_text, read_text


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


def _text(value: Any) -> str:
    """Input any routed value; return display text used by the Markdown renderer."""
    return value if isinstance(value, str) else "" if value is None else str(value)


def render_mission_markdown(domain: dict[str, Any]) -> str:
    """Input one domain object; return context grouped by exact source section."""
    groups: dict[str, list[dict[str, Any]]] = {}
    context = domain.get("context")
    for value in context if isinstance(context, list) else []:
        entry = value if isinstance(value, dict) else {"fact": value, "means": ""}
        section = entry.get("section")
        heading = section if isinstance(section, str) and section else "Unsectioned"
        groups.setdefault(heading, []).append(entry)

    lines = [f"# {_text(domain.get('agent')) or 'Domain'}", ""]
    for section, entries in groups.items():
        lines.extend([f"## {section}", ""])
        for entry in entries:
            fact = _text(entry.get("fact"))
            means = _text(entry.get("means"))
            body = f"{fact} [{means}]" if fact else f"[{means}]"
            lines.append("- " + body.replace("\n", "\n  "))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_mission_markdown(path: Path, domain: dict[str, Any]) -> None:
    """Input a path and domain object; atomically save its Markdown handoff for Layer 3."""
    atomic_write_text(path, render_mission_markdown(domain))
