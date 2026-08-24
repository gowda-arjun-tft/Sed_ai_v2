"""Technical, model-free completion checks for Layer 2 schema version 2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fs import atomic_write_text, load_json, sha256, slug
from .planner import load_planner
from .settings import AGENT_NAMES, LAYER2_SCHEMA_VERSION


Check = tuple[int, str, bool, str]


def _load_json_or_none(path: Path) -> Any:
    try:
        return load_json(path) if path.is_file() else None
    except (OSError, ValueError):
        return None


def _checks(run_dir: Path, run: dict[str, Any]) -> list[Check]:
    fact_path = run_dir / "inputs" / "fact_sheet.md"
    planner_path = run_dir / "inputs" / "planner_prompt.md"
    schema_ok = run.get("schema_version") == LAYER2_SCHEMA_VERSION
    hashes_ok = (
        fact_path.is_file()
        and planner_path.is_file()
        and sha256(fact_path) == run.get("fact_sheet", {}).get("sha256")
        and sha256(planner_path) == run.get("planner_prompt", {}).get("sha256")
    )
    try:
        _, definitions = load_planner(planner_path)
        planner_ok = [item["name"] for item in definitions] == AGENT_NAMES
    except (OSError, ValueError):
        planner_ok = False

    chunk_entries = run.get("chunking", {}).get("chunks", [])
    chunk_values = [
        _load_json_or_none(run_dir / str(item.get("file", "")))
        for item in chunk_entries
        if isinstance(item, dict)
    ]
    chunks_ok = bool(chunk_entries) and len(chunk_values) == len(chunk_entries) and all(
        isinstance(value, dict) for value in chunk_values
    )

    mission_values = [
        _load_json_or_none(run_dir / "missions" / f"{slug(name)}.json")
        for name in AGENT_NAMES
    ]
    missions_ok = len(mission_values) == len(AGENT_NAMES) and all(
        isinstance(value, dict) for value in mission_values
    )
    checks = [
        (1, "Schema and copied inputs are intact", schema_ok and hashes_ok, f"schema={run.get('schema_version')}"),
        (2, "Planner contains the frozen eight-domain roster", planner_ok, f"agents={len(AGENT_NAMES)}"),
        (3, "Every expected chunk result is valid JSON", chunks_ok, f"chunks={len(chunk_values)}"),
        (4, "Eight mission files are valid JSON", missions_ok, f"missions={sum(isinstance(v, dict) for v in mission_values)}"),
    ]
    return checks


def run_checks(run_dir: Path) -> list[Check]:
    """Write check_report.md and stamp completion without semantic inspection."""
    record_path = run_dir / "run.json"
    if not record_path.is_file():
        raise FileNotFoundError(f"not a CDI run folder: {run_dir}")
    run = _load_json_or_none(record_path)
    run = run if isinstance(run, dict) else {}
    checks = _checks(run_dir, run)
    passed = sum(ok for _, _, ok, _ in checks)
    lines = [f"# Layer 2 check report — {run_dir.name}", ""]
    lines.extend(
        f"- [{'x' if ok else ' '}] {number}. {label} — {detail}"
        for number, label, ok, detail in checks
    )
    lines.extend(["", f"**Result: {passed}/{len(checks)} passed.**", ""])
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines))
    return checks
