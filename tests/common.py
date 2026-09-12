from __future__ import annotations

import asyncio
from pathlib import Path

from ML.deep_research.layer2.backend.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    slug,
    write_json,
)
from ML.deep_research.layer3.legacy_input import write_mission_markdown
from ML.deep_research.layer3.settings import AGENT_NAMES

PLANNER_PATH = Path(__file__).parent / "fixtures" / "legacy_l2_planner_prompt.md"


class NativeBatchGraph:
    """Small fake of Runnable.abatch_as_completed for offline runner tests."""

    async def abatch_as_completed(
        self, inputs, config=None, *, return_exceptions=False, **_kwargs
    ):
        configs = config if isinstance(config, list) else [config] * len(inputs)
        concurrency = int(configs[0].get("max_concurrency", len(inputs)))
        semaphore = asyncio.Semaphore(concurrency)

        async def invoke(index):
            async with semaphore:
                try:
                    result = await self.ainvoke(inputs[index], config=configs[index])
                except Exception as exc:
                    if not return_exceptions:
                        raise
                    result = exc
                return index, result

        tasks = [asyncio.create_task(invoke(index)) for index in range(len(inputs))]
        for task in asyncio.as_completed(tasks):
            yield await task


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
    },
    {
        "section": "Annual rent",
        "fact": '"EUR 100,000"',
        "means": "The annual rent is EUR 100,000.",
    },
]

def create_complete_run(root: Path) -> Path:
    """Build a complete context-only Layer 2 fixture without a model call."""
    fact_sheet = root / "fact_sheet.md"
    fact_sheet.write_text(FACT_SHEET, encoding="utf-8")
    # Historical source fixture for unchanged L3/L4; never execute schema 4 here.
    from ML.deep_research.layer2.backend.fs import sha256
    run_dir = root / "runs" / "fixture-group" / "L2_fixture"
    atomic_write_text(run_dir / "inputs" / "fact_sheet.md", FACT_SHEET)
    atomic_write_text(run_dir / "inputs" / "planner_prompt.md", PLANNER_PATH.read_text(encoding="utf-8"))
    write_json(run_dir / "run.json", {
        "schema_version": 3, "run_id": run_dir.name, "status": "complete",
        "fact_sheet": {"sha256": sha256(fact_sheet), "name": fact_sheet.name},
        "planner_prompt": {"sha256": sha256(PLANNER_PATH)}, "chunking": {},
    })

    write_json(run_dir / "chunks" / "chunk_0001.json", {"fixture": True})
    record = load_json(run_dir / "run.json")
    record["chunking"]["chunks"] = [
        {
            "index": 1,
            "file": "chunks/chunk_0001.json",
            "status": "complete",
            "error": "",
        }
    ]
    record["status"] = "complete"
    write_json(run_dir / "run.json", record)

    for index, name in enumerate(AGENT_NAMES):
        holds_facts = index == 0
        mission = {"agent": name, "context": list(CONTEXT) if holds_facts else []}
        filename = slug(name)
        write_json(run_dir / "missions" / f"{filename}.json", mission)
        write_mission_markdown(
            run_dir / "mission_md" / f"{filename}.md",
            mission,
        )
    return run_dir


def create_complete_l3_run(root: Path) -> Path:
    """A complete permissive Layer 3 run assembled without model or web calls."""
    from tests.historical_layer3 import create_run as create_l3_run
    from ML.deep_research.layer3.settings import DOMAIN_NAMES

    l2_run = create_complete_run(root)
    l3_run = create_l3_run(
        l2_run,
        root / "runs",
        public_input_confirmed=True,
    )
    run = load_json(l3_run / "run.json")
    execution = run["execution"]
    for domain in DOMAIN_NAMES:
        record = execution["domains"][domain]
        report_path = l3_run / "domains" / slug(domain) / "final.md"
        atomic_write_text(report_path, f"# {domain}\n\nModel response.\n")
        record.update(
            status="complete",
            output_path=report_path.relative_to(l3_run).as_posix(),
            model_turns=1,
            elapsed_seconds=1.0,
            updated_at=now_iso(),
        )
    final_path = l3_run / "research" / "final.md"
    atomic_write_text(final_path, "# Answer\n\nModel synthesis.\n")
    execution["final"].update(
        status="complete",
        error="",
        output_path="research/final.md",
        model_turns=1,
        elapsed_seconds=1.0,
        updated_at=now_iso(),
    )
    run["status"] = "complete"
    write_json(l3_run / "run.json", run)
    return l3_run


__all__ = ["CONTEXT", "FACT_SHEET", "create_complete_l3_run", "create_complete_run"]
