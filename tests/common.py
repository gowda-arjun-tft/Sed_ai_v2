from __future__ import annotations

from pathlib import Path

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    slug,
    write_json,
)
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
    """A complete Layer 3 run assembled without model or web calls."""
    from ML.deep_research.layer3.contracts import Document
    from ML.deep_research.layer3.pipeline.create_run import create_run as create_l3_run
    from ML.deep_research.layer3.pipeline.run_checks import run_checks
    from ML.deep_research.layer3.settings import LENSES
    from ML.deep_research.layer3.sources import SourceStore

    l2_run = create_complete_run(root)
    l3_run = create_l3_run(
        l2_run,
        root / "runs",
        public_input_confirmed=True,
    )
    store = SourceStore(l3_run)
    source = store.store(
        Document(
            url="https://example.com/public-record",
            content_type="text/html; charset=utf-8",
            body=b"<p>Verified public fact.</p>",
            fetched_at=now_iso(),
            publisher="Example Registry",
        )
    )
    run = load_json(l3_run / "run.json")
    for agent in AGENT_NAMES:
        record = run["missions"][slug(agent)]
        session_id = record["thread_id"]
        markers = []
        for lens in LENSES:
            store.record_query(
                session_id=session_id,
                agent=agent,
                lens=lens,
                query=f"{agent} {lens} public evidence",
                new_sources=1,
            )
            marker = store.record_citation(
                source_id=source["source_sha256"],
                quote="Verified public fact.",
                tier=1,
                agent=agent,
                lens=lens,
                session_id=session_id,
            )
            markers.append(marker)
            atomic_write_text(
                l3_run / "lenses" / slug(agent) / f"{lens}.md",
                f"# {lens.title()}\n\nVerified public fact. {marker}\n",
            )
        atomic_write_text(
            l3_run / "research" / f"{slug(agent)}.md",
            f"# Answer\n\nVerified public fact. {markers[0]}\n",
        )
        record.update(
            status="complete",
            outcome="answered",
            reason="",
            error="",
            updated_at=now_iso(),
        )
    run["status"] = "complete"
    write_json(l3_run / "run.json", run)
    checks = run_checks(l3_run)
    assert sum(ok for _, _, ok, _ in checks) == len(checks)
    return l3_run


__all__ = ["CONTEXT", "FACT_SHEET", "create_complete_l3_run", "create_complete_run"]
