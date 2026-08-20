from __future__ import annotations

from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    read_text,
    sha256,
    slug,
    text_hash,
    write_json,
)
from ML.deep_research.layer2.planner import load_planner

from ..question_files import questions_json_path
from ..register import aggregator_id, read_rows, researcher_id
from ..settings import AGENT_NAMES, LENSES, TERMINAL_STATUSES
from ..sources import load_jsonl
from ..usage import summarize_usage


Check = tuple[int, str, bool, str]


def _write_report(run_dir: Path, run: dict[str, Any], checks: list[Check]) -> None:
    passed = sum(ok for _, _, ok, _ in checks)
    lines = [
        f"# Run {run['run_id']} — Layer 3 check report",
        "",
        f"{len(checks)} checks · {passed} passed · {len(checks) - passed} failed",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- [{'x' if ok else ' '}] {number}. {label}"
        + (f" — {detail}" if detail else "")
        for number, label, ok, detail in checks
    )
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines) + "\n")


def run_checks(run_dir: Path) -> list[Check]:
    run = load_json(run_dir / "run.json")
    rows = read_rows(run_dir)
    row_map = {item["row_id"]: item for item in rows}
    missions: dict[str, dict[str, Any]] = {}
    for name in AGENT_NAMES:
        path = run_dir / "inputs" / "missions" / f"{slug(name)}.json"
        if path.is_file():
            try:
                missions[name] = load_json(path)
            except (OSError, ValueError):
                pass
    index = load_jsonl(run_dir / "sources" / "index.jsonl")
    queries = load_jsonl(run_dir / "sources" / "queries.jsonl")
    checks: list[Check] = []

    def add(number: int, label: str, ok: bool, detail: str = "") -> None:
        checks.append((number, label, bool(ok), detail))

    expected_hashes = run.get("source_l2", {}).get("mission_hashes", {})
    copied_hashes = {
        path.name: sha256(path)
        for path in (run_dir / "inputs" / "missions").glob("*.json")
    }
    source_checks = run.get("source_l2", {}).get("checks", {})
    add(
        1,
        "Layer 2 handoff passed 19/19 and mission hashes match",
        source_checks == {"passed": 19, "failed": 0}
        and copied_hashes == expected_hashes,
    )
    add(
        2,
        "Fourteen copied missions use the frozen roster",
        list(missions) == AGENT_NAMES
        and all(missions[name].get("agent") == name for name in AGENT_NAMES),
        f"found={len(missions)}",
    )
    planner = run_dir / "inputs" / "planner_prompt.md"
    planner_ok = False
    try:
        _, definitions = load_planner(planner)
        planner_ok = (
            sha256(planner) == run.get("planner_prompt", {}).get("sha256")
            and [item["name"] for item in definitions] == AGENT_NAMES
        )
    except (OSError, ValueError):
        pass
    add(3, "Planner prompt copy and hash match", planner_ok)
    add(
        4,
        "Every mission context locator is non-empty",
        len(missions) == len(AGENT_NAMES)
        and all(
            str(item.get("where", "")).strip()
            for mission in missions.values()
            for item in mission.get("context", [])
        ),
    )

    expected_lenses = {
        (slug(agent), lens): run_dir / "lenses" / slug(agent) / f"{lens}.md"
        for agent in AGENT_NAMES
        for lens in LENSES
    }
    add(5, "Seventy base lens files exist", all(path.is_file() for path in expected_lenses.values()))

    expected_questions = {
        (agent, lens): run_dir / "questions" / slug(agent) / f"{lens}.md"
        for agent in AGENT_NAMES
        for lens in LENSES
    }
    add(6, "Seventy question files exist", all(path.is_file() for path in expected_questions.values()))
    add(
        7,
        "Every question list has a machine-readable copy",
        all(questions_json_path(path).is_file() for path in expected_questions.values()),
    )

    answers = {agent: run_dir / "research" / f"{slug(agent)}.md" for agent in AGENT_NAMES}
    add(8, "Fourteen answer files exist", all(path.is_file() for path in answers.values()))

    raw_files = list((run_dir / "sources" / "raw").glob("*/*.bin"))
    add(9, "Every stored raw source hashes to its filename", all(sha256(path) == path.stem for path in raw_files))
    add(
        10,
        "Every source index record points to existing artifacts",
        all(
            (run_dir / str(item.get("raw_path", ""))).is_file()
            and (
                not item.get("text_path")
                or (run_dir / str(item["text_path"])).is_file()
            )
            for item in index
        ),
    )
    add(11, "Every query is recorded with its session and text", all(item.get("session_id") and "query" in item for item in queries))
    required_rows = {
        *(researcher_id(agent, lens) for agent in AGENT_NAMES for lens in LENSES),
        *(aggregator_id(agent) for agent in AGENT_NAMES),
    }
    add(12, "Register contains the required 84 or more rows", len(rows) >= len(AGENT_NAMES) * (len(LENSES) + 1) and required_rows <= set(row_map), f"rows={len(rows)}")
    # Every row reached some end state. What that state is, and what the model
    # wrote to get there, is not judged here.
    terminal = all(
        item["first_status"] in TERMINAL_STATUSES
        and item["second_status"] in TERMINAL_STATUSES
        for item in rows
    )
    add(13, "Every register row has terminal statuses", terminal)

    _write_report(run_dir, run, checks)
    passed = sum(ok for _, _, ok, _ in checks)
    run["checks"] = {
        "run": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
    }
    run["usage"] = summarize_usage(run_dir)
    run["phases"]["5"] = "complete"
    run["status"] = "complete" if passed == len(checks) else "failed"
    run["finished_at"] = now_iso()
    write_json(run_dir / "run.json", run)
    return checks
