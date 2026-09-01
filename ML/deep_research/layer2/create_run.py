"""Build a self-contained schema-version-2 Layer 2 run folder.

No model, no network, ordinary code. This runs before the agent exists, and its
whole job is to make a folder that is a self-contained record of one property:

```
runs/property-folder-fact-sheet-a1b2c3d4/L2_20260820_143052_a1b2/
    run.json          the record: what was read, by which model, what passed
    inputs/
        fact_sheet.md      byte-identical copy of the source document
        planner_prompt.md  byte-identical copy of the roster
    missions/         empty; ordered chunk merging writes eight JSON files here
    chunks/           one structured JSON result per model call
```

**Why copy the inputs instead of pointing at them.** A run has to stay readable
after the source document has moved, been edited, or been deleted. The copies are
hashed into `run.json`, so the report can later prove the run was checked against
the same bytes it was given — and Layer 3 re-verifies the planner copy before it
will accept the run.

The validations inspect only human-supplied inputs before any model call.
"""

from __future__ import annotations

import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .fs import now_iso, read_text, run_group_name, sha256, write_json
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
    """Create one run folder and return its path.

    Args:
        fact_sheet: The property fact sheet, anywhere on disk.
        planner: `prompts/planner_prompt.md`, normally `settings.PLANNER_PATH`.
        runs_dir: Where run folders live, normally `settings.RUNS_DIR`.

    Returns:
        The new `runs/<fact-sheet>/L2_YYYYMMDD_HHMMSS_xxxx` directory.

    Raises:
        ValueError: The fact sheet is missing or empty.
        RuntimeError: A copied input did not hash the same as its source.

    Order matters. Everything that can fail cheaply fails first, so a bad input
    never leaves a half-built folder behind, and a broken roster is caught before
    a single model call is paid for.
    """
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
    fact_sheet = fact_sheet.resolve()
    planner = planner.resolve()

    if not fact_sheet.is_file():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    sheet_text = read_text(fact_sheet)
    if not sheet_text.strip():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    run_dir = _make_run_dir(runs_dir, fact_sheet)
    for name in RUN_SUBDIRS:
        (run_dir / name).mkdir()

    fact_copy = run_dir / "inputs" / "fact_sheet.md"
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    # copy2 preserves modification time, so the copy's provenance is visible.
    shutil.copy2(fact_sheet, fact_copy)
    shutil.copy2(planner, planner_copy)
    if sha256(fact_sheet) != sha256(fact_copy) or sha256(planner) != sha256(
        planner_copy
    ):
        raise RuntimeError("an input copy did not match its source")

    write_json(
        run_dir / "run.json",
        _initial_record(run_dir.name, fact_sheet, planner, reasoning_effort),
    )
    return run_dir


def _make_run_dir(runs_dir: Path, fact_sheet: Path) -> Path:
    """Create a timestamped Layer 2 run inside the input's stable group.

    The timestamp makes runs sortable by eye; four hex characters keep runs
    started within the same second distinct.

    `mkdir()` without `exist_ok` is the uniqueness test: the filesystem decides,
    atomically, whether this name was taken. A `FileExistsError` means another
    run won the name, so it draws again — this is why the loop exists rather than
    a "does it exist" check, which two processes could both pass.
    """
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


def _initial_record(
    run_id: str, fact_sheet: Path, planner: Path, reasoning_effort: str
) -> dict:
    """The `run.json` a fresh run starts with.

    `status` is `"started"` here. The runner changes it to `"complete"` after
    every chunk has had one opportunity to return JSON and available results
    have been merged. Optional checks do not alter execution state.

    The size and hash of each input are recorded so the report can detect an
    input edited mid-run, and the model, effort and harness version are recorded
    because a run's output is only interpretable next to what produced it.
    """
    return {
        "schema_version": LAYER2_SCHEMA_VERSION,
        "run_id": run_id,
        "run_group": run_group_name(fact_sheet),
        "status": "started",
        "started_at": now_iso(),
        "fact_sheet": {
            "name": fact_sheet.name,
            "source_path": str(fact_sheet),
            "bytes": fact_sheet.stat().st_size,
            "sha256": sha256(fact_sheet),
        },
        "planner_prompt": {
            "source_path": str(planner),
            "bytes": planner.stat().st_size,
            "sha256": sha256(planner),
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
    }
