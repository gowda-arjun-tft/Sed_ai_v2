"""Step 1 of 3 — build the run folder.

No model, no network, ordinary code. This runs before the agent exists, and its
whole job is to make a folder that is a self-contained record of one property:

```
runs/L2_20260820_a1b2/
    run.json          the record: what was read, by which model, what passed
    inputs/
        fact_sheet.md      byte-identical copy of the source document
        planner_prompt.md  byte-identical copy of the roster
    missions/         empty; the agent writes fourteen JSON files here
    staging/          empty; scratch space the agent uses only if it needs to
```

**Why copy the inputs instead of pointing at them.** A run has to stay readable
after the source document has moved, been edited, or been deleted. The copies are
hashed into `run.json`, so the report can later prove the run was checked against
the same bytes it was given — and Layer 3 re-verifies the planner copy before it
will accept the run.

The two validations here look like guardrails but are not: they inspect a
**human-supplied file** before any model sees it. Nothing in this module ever
inspects what the agent produced.
"""

from __future__ import annotations

import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .fs import now_iso, read_text, sha256, write_json
from .planner import load_planner
from .settings import (
    AGENT_NAMES,
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    REASONING_EFFORT,
)

# `missions/` is the deliverable. `staging/` is the agent's own scratch space,
# used only when a fact sheet is too large to hold in one context — created
# empty either way so the agent never has to make a directory to use one.
RUN_SUBDIRS = ("inputs", "missions", "staging")


def create_run(fact_sheet: Path, planner: Path, runs_dir: Path) -> Path:
    """Create one run folder and return its path.

    Args:
        fact_sheet: The property fact sheet, anywhere on disk.
        planner: `prompts/planner_prompt.md`, normally `settings.PLANNER_PATH`.
        runs_dir: Where run folders live, normally `settings.RUNS_DIR`.

    Returns:
        The new `runs/L2_YYYYMMDD_xxxx` directory.

    Raises:
        ValueError: The fact sheet is missing, empty, or has no `##` heading;
            or the planner prompt fails `load_planner`.
        RuntimeError: A copied input did not hash the same as its source.

    Order matters. Everything that can fail cheaply fails first, so a bad input
    never leaves a half-built folder behind, and a broken roster is caught before
    a single model call is paid for.
    """
    fact_sheet = fact_sheet.resolve()
    planner = planner.resolve()

    # A fact sheet with no `##` heading is a wrong-file mistake — someone passed
    # JSON, a PDF, or the wrong path. Catching it here costs nothing; catching it
    # after the agent has read it costs a run. This is the *only* thing asked of
    # the document's content: no required sections, no expected labels, no
    # language. `##` is Markdown structure, not vocabulary.
    if not fact_sheet.is_file():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    sheet_text = read_text(fact_sheet)
    if not sheet_text.strip():
        raise ValueError(f"fact sheet is missing or empty: {fact_sheet}")
    if not re.search(r"(?m)^## ", sheet_text):
        raise ValueError("fact sheet must contain at least one ## heading")

    # Fails now if the roster has drifted, rather than after the agent has spent
    # an hour writing missions against a roster Layer 3 will reject.
    load_planner(planner)

    run_dir = _make_run_dir(runs_dir)
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

    write_json(run_dir / "run.json", _initial_record(run_dir.name, fact_sheet, planner))
    return run_dir


def _make_run_dir(runs_dir: Path) -> Path:
    """Create a uniquely named `L2_YYYYMMDD_xxxx` directory under `runs_dir`.

    The date makes runs sortable by eye; four hex characters keep several runs of
    the same property on the same day apart.

    `mkdir()` without `exist_ok` is the uniqueness test: the filesystem decides,
    atomically, whether this name was taken. A `FileExistsError` means another
    run won the name, so it draws again — this is why the loop exists rather than
    a "does it exist" check, which two processes could both pass.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_dir = runs_dir / f"L2_{datetime.now(UTC):%Y%m%d}_{secrets.token_hex(2)}"
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue


def _initial_record(run_id: str, fact_sheet: Path, planner: Path) -> dict:
    """The `run.json` a fresh run starts with.

    `status` is `"started"` here. `report.run_checks` overwrites it with
    `"complete"` or `"failed"` and adds the `checks` and `facts` blocks — so a
    folder still saying `"started"` is one whose report never ran, which is
    exactly what Layer 3's acceptance check looks for.

    The size and hash of each input are recorded so the report can detect an
    input edited mid-run, and the model, effort and harness version are recorded
    because a run's output is only interpretable next to what produced it.
    """
    return {
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
        "agent_count": len(AGENT_NAMES),
    }
