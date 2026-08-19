from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..llm import create_routing_agent
from ..settings import AGENT_NAMES
from ..fs import atomic_write_text, load_json, slug, text_hash, write_json
from ..factsheet import atoms, piece_body
from ..planner import load_planner
from ..progress import bucket_entries, read_progress
from ..routing_tools import build_routing_tools


def _bucket_paths(run_dir: Path) -> dict[str, Path]:
    paths = {
        name: run_dir / "buckets" / f"{slug(name)}.md"
        for name in AGENT_NAMES
    }
    paths["_unrouted"] = run_dir / "buckets" / "_unrouted.md"
    for name, path in paths.items():
        if not path.exists():
            title = "Unrouted facts" if name == "_unrouted" else name
            atomic_write_text(path, f"# {title}\n")
    return paths


def route_facts(run_dir: Path) -> None:
    planner_text, _ = load_planner(run_dir / "inputs" / "planner_prompt.md")
    name_to_file = _bucket_paths(run_dir)
    state: dict[str, Any] = {
        "piece_id": "",
        "facts": [],
        "destinations": {},
    }
    tools = build_routing_tools(run_dir, name_to_file, state)
    agent = create_routing_agent(run_dir, planner_text, tools)
    mode = load_json(run_dir / "run.json")["split_mode"]

    for row in read_progress(run_dir):
        if row["status"] == "done":
            continue
        piece_path = next(
            (run_dir / "pieces").glob(f"{row['piece_id']}_*.md")
        )
        body = piece_body(piece_path)
        current_facts = atoms(body, mode)
        state.update(
            piece_id=row["piece_id"],
            facts=current_facts,
            destinations={},
        )
        for name, path in name_to_file.items():
            for metadata, fact in bucket_entries(path):
                if metadata.get("piece_id") == row["piece_id"] and fact in current_facts:
                    state["destinations"].setdefault(fact, set()).add(name)
        agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Route piece {row['piece_id']}. It contains "
                            f"{len(current_facts)} claim blocks.\n\n{body}"
                        ),
                    }
                ]
            }
        )
        latest = next(
            item
            for item in read_progress(run_dir)
            if item["piece_id"] == row["piece_id"]
        )
        if latest["status"] != "done":
            raise RuntimeError(
                f"the agent returned without completing {row['piece_id']}; "
                "resume the run"
            )

    run = load_json(run_dir / "run.json")
    run["model_calls"] = {
        "routing": len(read_progress(run_dir)),
        "missions": run.get("model_calls", {}).get("missions", 0),
    }
    run["status"] = "routed"
    write_json(run_dir / "run.json", run)


def validate_routing(run_dir: Path) -> None:
    run = load_json(run_dir / "run.json")
    mode = run["split_mode"]
    rows = read_progress(run_dir)
    if not rows or any(row["status"] != "done" for row in rows):
        raise RuntimeError("phase 2 gate failed: progress.csv still has pending pieces")
    if any(
        int(row["facts_routed"]) + int(row["facts_unrouted"])
        != int(row["facts_in_piece"])
        for row in rows
    ):
        raise RuntimeError("phase 2 gate failed: a piece's routed counts do not balance")

    piece_atoms = {
        path.name[:4]: atoms(piece_body(path), mode)
        for path in sorted((run_dir / "pieces").glob("p*.md"))
    }
    allowed = Counter(block for blocks in piece_atoms.values() for block in blocks)
    entries = [
        entry
        for path in (run_dir / "buckets").glob("*.md")
        for entry in bucket_entries(path)
    ]
    if any(allowed[block] == 0 for _, block in entries):
        raise RuntimeError(
            "phase 2 gate failed: a bucket contains text that is not an exact piece block"
        )

    expected = set()
    for piece_id, blocks in piece_atoms.items():
        seen: Counter[str] = Counter()
        for block in blocks:
            seen[block] += 1
            expected.add((piece_id, text_hash(block), seen[block]))
    actual = {
        (meta.get("piece_id"), meta.get("sha256"), int(meta.get("occurrence", 1)))
        for meta, _ in entries
    }
    if not expected <= actual:
        raise RuntimeError(
            f"phase 2 gate failed: {len(expected - actual)} facts reached no bucket "
            "and were not recorded as unrouted"
        )
