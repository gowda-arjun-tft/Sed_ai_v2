from __future__ import annotations

import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ..settings import (
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    REASONING_EFFORT,
)
from ..fs import now_iso, read_text, sha256, write_json
from ..planner import load_planner


def create_run(fact_sheet: Path, planner: Path, runs_dir: Path) -> Path:
    fact_sheet = fact_sheet.resolve()
    planner = planner.resolve()
    if not fact_sheet.is_file() or not read_text(fact_sheet).strip():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    if not re.search(r"(?m)^## ", read_text(fact_sheet)):
        raise ValueError("fact sheet must contain at least one ## heading")
    load_planner(planner)

    runs_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = f"L2_{datetime.now(UTC):%Y%m%d}_{secrets.token_hex(2)}"
        run_dir = runs_dir / run_id
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue

    inputs = run_dir / "inputs"
    for name in ("pieces", "buckets", "missions"):
        (run_dir / name).mkdir()
    inputs.mkdir()
    fact_copy = inputs / "fact_sheet.md"
    planner_copy = inputs / "planner_prompt.md"
    shutil.copy2(fact_sheet, fact_copy)
    shutil.copy2(planner, planner_copy)
    copies_match = (
        sha256(fact_sheet) == sha256(fact_copy)
        and sha256(planner) == sha256(planner_copy)
    )
    if not copies_match:
        raise RuntimeError("an input copy did not match its source")

    write_json(
        run_dir / "run.json",
        {
            "run_id": run_id,
            "status": "started",
            "started_at": now_iso(),
            "fact_sheet": {
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
            "reasoning_effort": REASONING_EFFORT,
            "deepagents_version": DEEPAGENTS_VERSION,
            "agent_count": 14,
        },
    )
    return run_dir
