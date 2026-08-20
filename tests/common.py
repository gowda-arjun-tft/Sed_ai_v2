from __future__ import annotations

import json
from pathlib import Path

from ML.deep_research.layer2.fs import slug, write_json
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.report import run_checks as run_l2_checks
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

# What the agent would have written, written by hand instead. These two entries
# stand in for the transcription the model now does.
CONTEXT = [
    {
        "section": "Land-register reference",
        "fact": '"Sheet 2967"',
        "means": "The property is registered on sheet 2967.",
        "where": "register.pdf · p1",
    },
    {
        "section": "Annual rent",
        "fact": '"EUR 100,000"',
        "means": "The annual rent is EUR 100,000.",
        "where": "lease.pdf · p9",
    },
]

SILENT = (
    "The fact sheet is silent on this subject. Establish the position from "
    "public sources."
)


def create_complete_run(root: Path) -> Path:
    """A finished Layer 2 run, built without a model call.

    Stands in for what the agent produces: the run folder, the two input copies,
    and fourteen mission files. The first agent gets the facts; the rest get a
    silent-subject mission, which is a normal outcome.
    """
    fact_sheet = root / "fact_sheet.md"
    fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
    run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")

    for index, name in enumerate(AGENT_NAMES):
        holds_facts = index == 0
        write_json(
            run_dir / "missions" / f"{slug(name)}.json",
            {
                "agent": name,
                "mission": (
                    "Establish the property position on this subject."
                    if holds_facts
                    else SILENT
                ),
                "context": list(CONTEXT) if holds_facts else [],
            },
        )
    run_l2_checks(run_dir)
    return run_dir


def create_complete_l3_run(root: Path) -> Path:
    import asyncio

    from ML.deep_research.layer3.cli import run_all
    from ML.deep_research.layer3.pipeline.create_run import create_run as create_l3_run

    l2_run = create_complete_run(root)
    fixtures = root / "fixtures"
    (fixtures / "queries").mkdir(parents=True)
    (fixtures / "pages").mkdir()
    l3_run = create_l3_run(l2_run, root / "runs", fixture_root=fixtures)
    checks = asyncio.run(run_all(l3_run))
    assert sum(ok for _, _, ok, _ in checks) == len(checks)
    return l3_run


__all__ = ["CONTEXT", "FACT_SHEET", "create_complete_l3_run", "create_complete_run"]
