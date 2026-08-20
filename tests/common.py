from __future__ import annotations

import json
from pathlib import Path

from ML.deep_research.layer2.factsheet import context_from_block, fact_blocks, piece_body
from ML.deep_research.layer2.fs import now_iso, slug, text_hash
from ML.deep_research.layer2.pipeline.create_run import create_run
from ML.deep_research.layer2.pipeline.split_fact_sheet import split_fact_sheet
from ML.deep_research.layer2.progress import bucket_entries, read_progress, write_progress
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH


FACT_SHEET = """# Property fact sheet

## Identity, title and land

### Land-register reference

**Evidence:** "Sheet 2967"
**Source:** `register.pdf` — locator `p1`.
**Interpretation:** The property is registered on sheet 2967.

## Lease and income evidence

### Annual rent

**Evidence:** "EUR 100,000"
**Source:** `lease.pdf` — locator `p9`.
**Interpretation:** The annual rent is EUR 100,000.

## Executive readout

### Summary only

**Evidence:** "Sheet 2967"
**Source:** `register.pdf` — locator `p1`.
**Interpretation:** This repeats the full identity fact.
"""


def create_complete_run(root: Path) -> Path:
    fact_sheet = root / "fact_sheet.md"
    fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
    run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
    split_fact_sheet(run_dir)
    rows = read_progress(run_dir)
    piece_blocks = []
    for row in rows:
        piece = next((run_dir / "pieces").glob(f"{row['piece_id']}_*.md"))
        blocks = fact_blocks(piece_body(piece))
        piece_blocks.append((row["piece_id"], blocks))
        row.update(
            status="done",
            facts_routed=str(len(blocks)),
            facts_unrouted="0",
            routed_at=now_iso(),
        )
    write_progress(run_dir, rows)

    first_name = AGENT_NAMES[0]
    for name in AGENT_NAMES:
        path = run_dir / "buckets" / f"{slug(name)}.md"
        path.write_text(f"# {name}\n", encoding="utf-8")
    (run_dir / "buckets" / "_unrouted.md").write_text(
        "# Unrouted facts\n",
        encoding="utf-8",
    )
    first_bucket = run_dir / "buckets" / f"{slug(first_name)}.md"
    with first_bucket.open("a", encoding="utf-8") as handle:
        for piece_id, blocks in piece_blocks:
            for block in blocks:
                metadata = json.dumps(
                    {
                        "piece_id": piece_id,
                        "sha256": text_hash(block),
                        "reason": "test route",
                    },
                    separators=(",", ":"),
                )
                handle.write(
                    f"\n<!-- route {metadata} -->\n{block}\n<!-- /route -->\n"
                )

    for name in AGENT_NAMES:
        path = run_dir / "buckets" / f"{slug(name)}.md"
        entries = bucket_entries(path)
        mission = {
            "agent": name,
            "mission": (
                "Establish the property position."
                if entries
                else "The fact sheet is silent on this subject. Establish it from public sources."
            ),
            "context": [context_from_block(block) for _, block in entries],
        }
        mission_path = run_dir / "missions" / f"{slug(name)}.json"
        mission_path.write_text(json.dumps(mission), encoding="utf-8")
    return run_dir


def create_complete_l3_run(root: Path) -> Path:
    import asyncio

    from ML.deep_research.layer2.pipeline.run_checks import run_checks as run_l2_checks
    from ML.deep_research.layer3.cli import run_all
    from ML.deep_research.layer3.pipeline.create_run import create_run as create_l3_run

    l2_run = create_complete_run(root)
    assert sum(ok for _, _, ok, _ in run_l2_checks(l2_run)) == 19
    fixtures = root / "fixtures"
    (fixtures / "queries").mkdir(parents=True)
    (fixtures / "pages").mkdir()
    l3_run = create_l3_run(l2_run, root / "runs", fixture_root=fixtures)
    checks = asyncio.run(run_all(l3_run))
    assert sum(ok for _, _, ok, _ in checks) == len(checks)
    return l3_run
