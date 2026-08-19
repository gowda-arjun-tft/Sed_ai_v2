from __future__ import annotations

import json
from pathlib import Path

from ML.deep_research.layer2.claims import context_from_claim_block
from ML.deep_research.layer2.factsheet import fact_blocks, piece_body
from ML.deep_research.layer2.fs import now_iso, slug, text_hash
from ML.deep_research.layer2.pipeline.create_run import create_run
from ML.deep_research.layer2.pipeline.split_fact_sheet import split_fact_sheet
from ML.deep_research.layer2.progress import bucket_entries, read_progress, write_progress
from ML.deep_research.layer2.settings import AGENT_NAMES, PLANNER_PATH


CLAIMS_INPUT = {
    "property_reference": "DE-001",
    "claims": [
        {
            "kind": "land_register",
            "value": "Sheet 2967",
            "source": {"file": "register.pdf", "page": 1},
        },
        {
            "kind": "annual_rent",
            "amount": 100000,
            "currency": "EUR",
            "source": {"file": "lease.pdf", "page": 9},
        },
    ],
}


def create_complete_run(root: Path) -> Path:
    fact_sheet = root / "claims.json"
    fact_sheet.write_text(json.dumps(CLAIMS_INPUT), encoding="utf-8")
    run_dir = create_run(fact_sheet, PLANNER_PATH, root / "runs")
    split_fact_sheet(run_dir)
    rows = read_progress(run_dir)
    piece = next((run_dir / "pieces").glob("p*.md"))
    blocks = fact_blocks(piece_body(piece))
    rows[0].update(
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
        for block in blocks:
            metadata = json.dumps(
                {
                    "piece_id": "p001",
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
                else "The JSON input is silent on this subject. Establish it from public sources."
            ),
            "context": [context_from_claim_block(block) for _, block in entries],
        }
        mission_path = run_dir / "missions" / f"{slug(name)}.json"
        mission_path.write_text(json.dumps(mission), encoding="utf-8")
    return run_dir
