from __future__ import annotations

import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ..settings import (
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    REASONING_EFFORT,
)
from ..fs import now_iso, sha256, write_json
from ..claims import load_claims
from ..planner import load_planner


def create_run(input_json: Path, planner: Path, runs_dir: Path) -> Path:
    input_json = input_json.resolve()
    planner = planner.resolve()
    if not input_json.is_file() or input_json.suffix.casefold() != ".json":
        raise ValueError(f"claims input must be an existing .json file: {input_json}")
    claims, _ = load_claims(input_json)
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
    input_copy = inputs / "claims.json"
    planner_copy = inputs / "planner_prompt.md"
    shutil.copy2(input_json, input_copy)
    shutil.copy2(planner, planner_copy)
    copies_match = (
        sha256(input_json) == sha256(input_copy)
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
            "input": {
                "source_path": str(input_json),
                "bytes": input_json.stat().st_size,
                "sha256": sha256(input_json),
                "claims": len(claims),
            },
            "input_file": "claims.json",
            "input_format": "json",
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
