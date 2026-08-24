"""Deterministic Markdown view of one authoritative mission JSON object."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fs import atomic_write_text


def _text(value: Any) -> str:
    return value if isinstance(value, str) else "" if value is None else str(value)


def render_mission_markdown(mission: dict[str, Any]) -> str:
    """Group complete context entries by exact section without rewriting them."""
    groups: dict[str, list[dict[str, Any]]] = {}
    context = mission.get("context")
    for value in context if isinstance(context, list) else []:
        entry = value if isinstance(value, dict) else {"fact": value, "means": ""}
        section = entry.get("section")
        heading = section if isinstance(section, str) and section else "Unsectioned"
        groups.setdefault(heading, []).append(entry)

    lines = [
        f"# {_text(mission.get('agent')) or 'Mission'}",
        "",
        "## Mission",
        "",
        _text(mission.get("mission")),
        "",
    ]
    for section, entries in groups.items():
        lines.extend([f"## {section}", ""])
        for entry in entries:
            fact = _text(entry.get("fact"))
            means = _text(entry.get("means"))
            body = f"{fact} [{means}]" if fact else f"[{means}]"
            lines.append("- " + body.replace("\n", "\n  "))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_mission_markdown(path: Path, mission: dict[str, Any]) -> None:
    atomic_write_text(path, render_mission_markdown(mission))
