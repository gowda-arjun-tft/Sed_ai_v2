"""Create immutable-input Layer 2 run folders without invoking a model."""

from __future__ import annotations

import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .fs import now_iso, read_text, run_group_name, sha256, write_json
from .planner import load_planner
from .settings import (
    AGENT_NAMES,
    CHUNK_ENCODING,
    CHUNK_INPUT_PARTITIONING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    CHUNK_STRATEGY,
    DEEPAGENTS_VERSION,
    LAYER2_SCHEMA_VERSION,
    MAX_CHUNK_CONCURRENCY,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_NAME,
    PROVIDER_MAX_RETRIES,
    REASONING_EFFORT,
    REASONING_EFFORTS,
)

RUN_SUBDIRS = ("inputs", "chunks", "missions", "mission_md")


def create_run(
    fact_sheet: Path,
    planner: Path,
    runs_dir: Path,
    *,
    reasoning_effort: str = REASONING_EFFORT,
) -> Path:
    """Input a fact sheet, planner and root; return a preflighted schema-3 run path."""
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
    fact_sheet = fact_sheet.resolve()
    planner = planner.resolve()

    if not fact_sheet.is_file() or not read_text(fact_sheet).strip():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    if not planner.is_file():
        raise ValueError(f"planner prompt is missing: {planner}")
    _, definitions = load_planner(planner)
    names = [item.get("name") if isinstance(item, dict) else None for item in definitions]
    if names != AGENT_NAMES:
        raise ValueError("planner roster does not match the configured eight domains")
    fact_bytes = fact_sheet.stat().st_size
    planner_bytes = planner.stat().st_size
    fact_hash = sha256(fact_sheet)
    planner_hash = sha256(planner)

    run_dir = _make_run_dir(runs_dir, fact_sheet)
    for name in RUN_SUBDIRS:
        (run_dir / name).mkdir()

    fact_copy = run_dir / "inputs" / "fact_sheet.md"
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    shutil.copy2(fact_sheet, fact_copy)
    shutil.copy2(planner, planner_copy)
    if fact_hash != sha256(fact_copy) or planner_hash != sha256(planner_copy):
        raise RuntimeError("an input copy did not match its source")

    write_json(run_dir / "run.json", {
        "schema_version": LAYER2_SCHEMA_VERSION,
        "run_id": run_dir.name,
        "run_group": run_dir.parent.name,
        "status": "started",
        "started_at": now_iso(),
        "fact_sheet": {
            "name": fact_sheet.name,
            "source_path": str(fact_sheet),
            "bytes": fact_bytes,
            "sha256": fact_hash,
        },
        "planner_prompt": {
            "source_path": str(planner),
            "bytes": planner_bytes,
            "sha256": planner_hash,
        },
        "model": MODEL_NAME,
        "reasoning_effort": reasoning_effort,
        "limits": {
            "input_tokens_per_model_call": MODEL_INPUT_TOKEN_LIMIT,
            "provider_max_retries": PROVIDER_MAX_RETRIES,
        },
        "chunking": {
            "strategy": CHUNK_STRATEGY,
            "input_partitioning": CHUNK_INPUT_PARTITIONING,
            "encoding": CHUNK_ENCODING,
            "size_tokens": CHUNK_SIZE_TOKENS,
            "overlap_tokens": CHUNK_OVERLAP_TOKENS,
            "stride_tokens": CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS,
            "max_concurrency": MAX_CHUNK_CONCURRENCY,
            "chunks": [],
        },
        "deepagents_version": DEEPAGENTS_VERSION,
        "agent_count": len(AGENT_NAMES),
    })
    return run_dir


def _make_run_dir(runs_dir: Path, fact_sheet: Path) -> Path:
    """Input a root and source path; atomically create and return a grouped run folder."""
    group_dir = runs_dir / run_group_name(fact_sheet)
    group_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_dir = group_dir / (
            f"L2_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        )
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue
