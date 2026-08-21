from __future__ import annotations

import secrets
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ML.deep_research.layer2.fs import load_json, now_iso, sha256, slug, write_json

from ..mission import stage_thread_id
from ..settings import (
    CHECKPOINT_PACKAGE_VERSION,
    DEEPAGENTS_VERSION,
    DOMAIN_NAMES,
    FETCH_TIMEOUT_SECONDS,
    HARNESS_NAME,
    MAX_SOURCE_BYTES,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_MAX_RETRIES,
    MODEL_NAME,
    MODEL_TIMEOUT_SECONDS,
    PROMPTS_DIR,
    REASONING_EFFORT,
    RUN_PREFIX,
    SCHEMA_VERSION,
    SKILL_PATH,
    SUMMARIZATION_KEEP_TOKENS,
    SUMMARIZATION_TRIGGER_TOKENS,
)


def _validate_l2(run_dir: Path) -> tuple[dict, Path, list[Path]]:
    metadata_path = run_dir / "run.json"
    if not metadata_path.is_file():
        raise ValueError("Layer 2 run has no run.json")
    metadata = load_json(metadata_path)
    checks = metadata.get("checks") or {}
    complete = (
        isinstance(checks.get("run"), int)
        and checks.get("run") > 0
        and checks.get("failed") == 0
        and checks.get("passed") == checks.get("run")
    )
    if not complete:
        raise ValueError("Layer 2 run must record every check passed and none failed")
    planner = run_dir / "inputs" / "planner_prompt.md"
    mission_dir = run_dir / "missions"
    missions = sorted(mission_dir.glob("*.json"))
    expected = {f"{slug(name)}.json": name for name in DOMAIN_NAMES}
    found = {path.name: path for path in missions}
    if set(found) != set(expected):
        raise ValueError(
            "Layer 3 schema 5 requires the exact current eight-domain Layer 2 "
            "roster; legacy Layer 2 runs are not resumable"
        )
    for filename, name in expected.items():
        mission = load_json(found[filename])
        if not isinstance(mission, dict) or mission.get("agent") != name:
            raise ValueError(f"Layer 2 mission identity does not match {filename}")
    return metadata, planner, missions


def _new_run_dir(runs_dir: Path) -> tuple[str, Path]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = f"{RUN_PREFIX}_{datetime.now(UTC):%Y%m%d}_{secrets.token_hex(2)}"
        run_dir = runs_dir / run_id
        try:
            run_dir.mkdir()
            return run_id, run_dir
        except FileExistsError:
            pass


def _copy_prompts(run_dir: Path) -> tuple[str, dict[str, str]]:
    target = run_dir / "inputs" / "prompts"
    target.mkdir(parents=True)
    skill_copy = target / "SKILL.md"
    shutil.copy2(SKILL_PATH, skill_copy)
    for source in sorted(PROMPTS_DIR.rglob("*.md")):
        relative = source.relative_to(PROMPTS_DIR)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    prompt_hashes = {
        str(path.relative_to(target)).replace("\\", "/"): sha256(path)
        for path in sorted(target.rglob("*.md"))
        if path.name != "SKILL.md"
    }
    return sha256(skill_copy), prompt_hashes


def create_run(
    l2_run: Path,
    runs_dir: Path,
    *,
    public_input_confirmed: bool = False,
) -> Path:
    l2_run = l2_run.resolve()
    source, planner, missions = _validate_l2(l2_run)
    if not public_input_confirmed:
        raise ValueError("online research requires public-input confirmation")
    run_id, run_dir = _new_run_dir(runs_dir)
    mission_dir = run_dir / "inputs" / "missions"
    for path in (
        mission_dir,
        run_dir / "domains",
        run_dir / "review",
        run_dir / "research",
        run_dir / "sources" / "raw",
        run_dir / "sources" / "text",
    ):
        path.mkdir(parents=True, exist_ok=True)
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    shutil.copy2(planner, planner_copy)
    for mission in missions:
        target = mission_dir / mission.name
        shutil.copy2(mission, target)
    skill_hash, prompt_hashes = _copy_prompts(run_dir)
    for name in ("index.jsonl", "citations.jsonl", "queries.jsonl"):
        (run_dir / "sources" / name).touch()
    (run_dir / "usage.jsonl").touch()
    sqlite3.connect(run_dir / "checkpoints.sqlite3").close()
    started = now_iso()
    write_json(
        run_dir / "run.json",
        {
            "schema_version": SCHEMA_VERSION,
            "harness": HARNESS_NAME,
            "run_id": run_id,
            "status": "created",
            "started_at": started,
            "updated_at": started,
            "source_l2": {
                "run_id": source.get("run_id"),
                "path": str(l2_run),
                "status": source.get("status"),
                "checks": source.get("checks") or {},
                "facts": source.get("facts") or {},
            },
            "skill": {"path": "inputs/prompts/SKILL.md", "sha256": skill_hash},
            "prompt_hashes": prompt_hashes,
            "provider": "online",
            "public_input_confirmed": True,
            "model": MODEL_NAME,
            "reasoning_effort": REASONING_EFFORT,
            "model_context_window_tokens": MODEL_INPUT_TOKEN_LIMIT,
            "deepagents_version": DEEPAGENTS_VERSION,
            "checkpoint_package_version": CHECKPOINT_PACKAGE_VERSION,
            "limits": {
                "summarization_trigger_tokens": SUMMARIZATION_TRIGGER_TOKENS,
                "summarization_keep_tokens": SUMMARIZATION_KEEP_TOKENS,
                "model_and_search_timeout_seconds": MODEL_TIMEOUT_SECONDS,
                "transient_retries": MODEL_MAX_RETRIES,
                "fetch_timeout_seconds": FETCH_TIMEOUT_SECONDS,
                "maximum_source_bytes": MAX_SOURCE_BYTES,
            },
            "usage": {
                "api_calls": 0,
                "model_calls": 0,
                "web_search_calls": 0,
                "events": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "total_tokens": 0,
            },
            "domains": list(DOMAIN_NAMES),
            "execution": _execution(run_id, started),
        },
    )
    return run_dir


def _record(run_id: str, stage: str, actor: str, batch: int, started: str) -> dict:
    return {
        "stage": stage,
        "actor": actor,
        "batch": batch,
        "thread_id": stage_thread_id(run_id, stage, actor, batch, 1),
        "attempt": 1,
        "status": "pending",
        "outcome": "",
        "reason": "",
        "error": "",
        "unknowns": [],
        "artifact": "",
        "model_turns": 0,
        "elapsed_seconds": 0.0,
        "updated_at": started,
    }


def _execution(run_id: str, started: str) -> dict:
    return {
        "domains": {
            name: _record(run_id, "domain", name, 0, started)
            for name in DOMAIN_NAMES
        },
        "review": _record(run_id, "review", "property-reviewer", 0, started),
        "clarification": None,
        "final": _record(run_id, "synthesis", "property-synthesis", 0, started),
    }
