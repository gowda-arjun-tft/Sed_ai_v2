from __future__ import annotations

import secrets
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ML.deep_research.layer2.fs import load_json, now_iso, sha256, slug, write_json
from ML.deep_research.layer2.planner import load_planner

from ..register import seed_register
from ..settings import (
    AGENT_NAMES,
    CHECKPOINT_PACKAGE_VERSION,
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    PROMPTS_DIR,
    REASONING_EFFORT,
    RUN_PREFIX,
    WORKERS,
)


def _validate_l2(run_dir: Path) -> tuple[dict, Path, list[Path]]:
    metadata_path = run_dir / "run.json"
    if not metadata_path.is_file():
        raise ValueError("Layer 2 run has no run.json")
    metadata = load_json(metadata_path)
    checks = metadata.get("checks", {})
    if checks.get("passed") != 19 or checks.get("failed") != 0:
        raise ValueError("Layer 2 run must record 19 passed and 0 failed")
    planner = run_dir / "inputs" / "planner_prompt.md"
    _, definitions = load_planner(planner)
    if [item["name"] for item in definitions] != AGENT_NAMES:
        raise ValueError("Layer 2 planner roster does not match the frozen order")
    missions = [run_dir / "missions" / f"{slug(name)}.json" for name in AGENT_NAMES]
    if not all(path.is_file() for path in missions):
        raise ValueError("Layer 2 run must contain fourteen mission files")
    for name, path in zip(AGENT_NAMES, missions, strict=True):
        if load_json(path).get("agent") != name:
            raise ValueError(f"Layer 2 mission name mismatch: {path.name}")
    return metadata, planner, missions


def create_run(
    l2_run: Path,
    runs_dir: Path,
    *,
    fixture_root: Path | None = None,
    online: bool = False,
    public_input_confirmed: bool = False,
) -> Path:
    l2_run = l2_run.resolve()
    source, planner, missions = _validate_l2(l2_run)
    if online == bool(fixture_root):
        raise ValueError("choose exactly one of fixture or online retrieval")
    if online and not public_input_confirmed:
        raise ValueError("online research requires public-input confirmation")
    if fixture_root is not None and not fixture_root.resolve().is_dir():
        raise ValueError(f"fixture root is not a directory: {fixture_root}")
    runs_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = f"{RUN_PREFIX}_{datetime.now(UTC):%Y%m%d}_{secrets.token_hex(2)}"
        run_dir = runs_dir / run_id
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue
    inputs = run_dir / "inputs"
    mission_dir = inputs / "missions"
    for path in (
        mission_dir,
        run_dir / "lenses",
        run_dir / "questions",
        run_dir / "research",
        run_dir / "sources" / "raw",
        run_dir / "sources" / "text",
        run_dir / "session_results",
        run_dir / "gap_decisions",
    ):
        path.mkdir(parents=True, exist_ok=True)
    planner_copy = inputs / "planner_prompt.md"
    shutil.copy2(planner, planner_copy)
    mission_hashes = {}
    for mission in missions:
        target = mission_dir / mission.name
        shutil.copy2(mission, target)
        if sha256(mission) != sha256(target):
            raise RuntimeError(f"mission copy hash mismatch: {mission.name}")
        mission_hashes[mission.name] = sha256(target)
    for name in ("index.jsonl", "citations.jsonl", "queries.jsonl"):
        (run_dir / "sources" / name).touch()
    (run_dir / "usage.jsonl").touch()
    sqlite3.connect(run_dir / "checkpoints.sqlite3").close()
    write_json(
        run_dir / "run.json",
        {
            "run_id": run_id,
            "status": "phase_0_complete",
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "source_l2": {
                "run_id": source.get("run_id"),
                "path": str(l2_run),
                "checks": {"passed": 19, "failed": 0},
                "mission_hashes": mission_hashes,
            },
            "planner_prompt": {"sha256": sha256(planner_copy)},
            "provider": "online" if online else "fixture",
            "fixture_root": str(fixture_root.resolve()) if fixture_root else "",
            "public_input_confirmed": bool(public_input_confirmed),
            "model": MODEL_NAME,
            "reasoning_effort": REASONING_EFFORT,
            "deepagents_version": DEEPAGENTS_VERSION,
            "checkpoint_package_version": CHECKPOINT_PACKAGE_VERSION,
            "prompt_hashes": {
                str(path.relative_to(PROMPTS_DIR)).replace("\\", "/"): sha256(path)
                for path in sorted(PROMPTS_DIR.rglob("*.md"))
            },
            # Scheduling only. There are no research limits to record.
            "concurrency": {"workers": WORKERS},
            "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "phases": {str(index): ("complete" if index == 0 else "pending") for index in range(6)},
        },
    )
    seed_register(run_dir, run_id, AGENT_NAMES)
    return run_dir
