from __future__ import annotations

import json
from pathlib import Path

from ..llm import create_mission_agent
from ..fs import load_json, read_text, slug, write_json
from ..factsheet import context_from_block
from ..planner import load_planner
from ..progress import bucket_entries


def _existing_mission_is_valid(
    path: Path,
    name: str,
    expected_count: int,
) -> bool:
    try:
        mission = load_json(path)
        return (
            mission.get("agent") == name
            and bool(str(mission.get("mission", "")).strip())
            and len(mission.get("context", [])) == expected_count
        )
    except (OSError, ValueError, TypeError):
        return False


def write_missions(run_dir: Path) -> None:
    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    agent = create_mission_agent()
    for definition in definitions:
        name = definition["name"]
        bucket_path = run_dir / "buckets" / f"{slug(name)}.md"
        entries = bucket_entries(bucket_path)
        mission_path = run_dir / "missions" / f"{slug(name)}.json"
        if _existing_mission_is_valid(mission_path, name, len(entries)):
            continue
        bucket = read_text(bucket_path)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Agent definition:\n"
                            f"{json.dumps(definition, ensure_ascii=False, indent=2)}\n\n"
                            f"Bucket ({len(entries)} facts):\n{bucket}\n\n"
                            "Write this agent's mission."
                        ),
                    }
                ]
            }
        )
        structured = result.get("structured_response")
        mission_text = (
            structured.mission
            if hasattr(structured, "mission")
            else str(structured["mission"])
        )
        if not entries and "fact sheet is silent" not in mission_text.casefold():
            mission_text = (
                f"The fact sheet is silent on this subject. {mission_text.strip()}"
            )
        write_json(
            mission_path,
            {
                "agent": name,
                "mission": mission_text.strip(),
                "context": [context_from_block(block) for _, block in entries],
            },
        )

    run = load_json(run_dir / "run.json")
    run.setdefault("model_calls", {})["missions"] = 14
    run["status"] = "missions_written"
    write_json(run_dir / "run.json", run)
