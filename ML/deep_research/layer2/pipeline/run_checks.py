from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..settings import AGENT_NAMES
from ..fs import (
    atomic_write_text,
    load_json,
    now_iso,
    read_text,
    sha256,
    slug,
    text_hash,
    write_json,
)
from ..factsheet import atoms, piece_body
from ..planner import load_planner
from ..progress import bucket_entries, read_progress


Check = tuple[int, str, bool, str]


def _route_keys(piece_atoms: dict[str, list[str]]) -> set[tuple[str, str, int]]:
    keys = set()
    for piece_id, blocks in piece_atoms.items():
        seen: Counter[str] = Counter()
        for block in blocks:
            seen[block] += 1
            keys.add((piece_id, text_hash(block), seen[block]))
    return keys


def _write_report(
    run_dir: Path,
    run: dict[str, Any],
    checks: list[Check],
    original_count: int,
    routed_count: int,
    skipped_count: int,
    skipped_sections: int,
    unrouted: list[tuple[dict[str, str], str]],
    bucket_counts: dict[str, int],
) -> None:
    passed = sum(ok for _, _, ok, _ in checks)
    lines = [
        f"# Run {run['run_id']} — check report",
        "",
        f"19 checks · {passed} passed · {19 - passed} failed",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- [{'x' if ok else ' '}] {number}. {label}"
        f"{f' — {detail}' if detail else ''}"
        for number, label, ok, detail in checks
    )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Fact sheet blocks: {original_count}",
            f"- Routed: {routed_count}",
            f"- Set aside: {skipped_count} in {skipped_sections} sections",
            f"- Unrouted: {len(unrouted)}",
            "",
            "## Buckets",
            "",
        ]
    )
    lines.extend(f"- {name}: {count} facts" for name, count in bucket_counts.items())
    if unrouted:
        lines.extend(["", "## Unrouted", ""])
        lines.extend(
            f"- {meta.get('piece_id')}: {meta.get('reason')}"
            for meta, _ in unrouted
        )
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines) + "\n")


def run_checks(run_dir: Path) -> list[Check]:
    run = load_json(run_dir / "run.json")
    mode = run["split_mode"]
    fact_copy = run_dir / "inputs" / "fact_sheet.md"
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    original_text = read_text(fact_copy)
    original_atoms = atoms(original_text, mode)
    piece_paths = sorted((run_dir / "pieces").glob("p*.md"))
    skipped_paths = sorted((run_dir / "pieces" / "_skipped").glob("*.md"))
    piece_atoms = {
        path.name[:4]: atoms(piece_body(path), mode) for path in piece_paths
    }
    skipped_atoms = [
        atom for path in skipped_paths for atom in atoms(read_text(path), mode)
    ]
    progress = read_progress(run_dir)
    _, definitions = load_planner(planner_copy)
    bucket_map = {
        name: bucket_entries(run_dir / "buckets" / f"{slug(name)}.md")
        for name in AGENT_NAMES
    }
    unrouted = bucket_entries(run_dir / "buckets" / "_unrouted.md")
    routed_entries = [entry for entries in bucket_map.values() for entry in entries]
    checks: list[Check] = []

    def add(number: int, label: str, ok: bool, detail: str = "") -> None:
        checks.append((number, label, bool(ok), detail))

    inputs_match = (
        fact_copy.is_file()
        and planner_copy.is_file()
        and sha256(fact_copy) == run["fact_sheet"]["sha256"]
        and sha256(planner_copy) == run["planner_prompt"]["sha256"]
    )
    add(1, "Input files and hashes", inputs_match)
    add(2, "Planner has fourteen definitions", len(definitions) == 14)
    add(
        3,
        "Frozen agent names match",
        [item["name"] for item in definitions] == AGENT_NAMES,
    )
    combined_cut = [atom for values in piece_atoms.values() for atom in values]
    combined_cut += skipped_atoms
    add(
        4,
        "Every block appears in exactly one cut destination",
        Counter(original_atoms) == Counter(combined_cut),
    )
    add(
        5,
        "Cut block count matches input",
        len(original_atoms) == len(combined_cut),
        f"input={len(original_atoms)}, cut={len(combined_cut)}",
    )
    add(
        6,
        "Every piece carries a parent heading",
        all(re.search(r"(?m)^## ", piece_body(path)) for path in piece_paths),
    )
    add(
        7,
        "Every set-aside section records a reason",
        all(read_text(path).startswith("<!-- skipped: ") for path in skipped_paths),
    )
    add(8, "Every progress row is done", bool(progress) and all(row["status"] == "done" for row in progress))
    balanced = all(
        int(row["facts_routed"] or -1) + int(row["facts_unrouted"] or -1)
        == int(row["facts_in_piece"])
        for row in progress
    )
    add(9, "Per-piece routed counts balance", balanced)
    piece_counter = Counter(atom for values in piece_atoms.values() for atom in values)
    add(
        10,
        "Every bucket block is an exact piece block",
        all(piece_counter[block] > 0 for _, block in routed_entries + unrouted),
    )
    expected_keys = _route_keys(piece_atoms)
    actual_keys = {
        (meta.get("piece_id"), meta.get("sha256"), int(meta.get("occurrence", 1)))
        for meta, _ in routed_entries + unrouted
    }
    add(
        11,
        "Every routed-piece fact reached a bucket or unrouted",
        expected_keys <= actual_keys,
        f"missing={len(expected_keys - actual_keys)}",
    )
    add(
        12,
        "Every unrouted fact has a reason",
        all(meta.get("reason", "").strip() for meta, _ in unrouted),
        f"unrouted={len(unrouted)}",
    )

    mission_paths = {path.stem: path for path in (run_dir / "missions").glob("*.json")}
    add(13, "Fourteen mission files exist", set(mission_paths) == {slug(name) for name in AGENT_NAMES}, f"found={len(mission_paths)}")
    missions = {}
    for name in AGENT_NAMES:
        path = run_dir / "missions" / f"{slug(name)}.json"
        if path.exists():
            try:
                missions[name] = load_json(path)
            except (ValueError, OSError):
                pass
    add(14, "Every mission uses its exact agent name", len(missions) == 14 and all(missions[name].get("agent") == name for name in AGENT_NAMES))
    exact = counts = nonempty = silent = locators = True
    for name, mission in missions.items():
        blocks = [block for _, block in bucket_map[name]]
        context = mission.get("context", [])
        exact &= all(any(str(item.get("fact", "")) in block for block in blocks) for item in context)
        counts &= len(context) == len(blocks)
        nonempty &= bool(str(mission.get("mission", "")).strip())
        silent &= bool(context) or "fact sheet is silent" in str(mission.get("mission", "")).casefold()
        locators &= all(bool(item.get("where")) and str(item["where"]) in original_text for item in context)
    add(15, "Every mission fact is exact bucket text", len(missions) == 14 and exact)
    add(16, "Mission context counts equal bucket counts", len(missions) == 14 and counts)
    add(17, "Every mission is non-empty", len(missions) == 14 and nonempty)
    add(18, "Every empty context says the fact sheet is silent", len(missions) == 14 and silent)
    add(19, "Every context locator resolves in the fact sheet", len(missions) == 14 and locators)

    routed_keys = {
        (meta.get("piece_id"), meta.get("sha256"), int(meta.get("occurrence", 1)))
        for meta, _ in routed_entries
    }
    bucket_counts = {name: len(entries) for name, entries in bucket_map.items()}
    _write_report(
        run_dir, run, checks, len(original_atoms), len(expected_keys & routed_keys),
        len(skipped_atoms), len(skipped_paths), unrouted, bucket_counts,
    )
    passed = sum(ok for _, _, ok, _ in checks)
    run["finished_at"] = now_iso()
    run["facts"] = {"routed": len(expected_keys & routed_keys), "set_aside": len(skipped_atoms), "unrouted": len(unrouted)}
    run["buckets"] = bucket_counts
    run["checks"] = {"run": 19, "passed": passed, "failed": 19 - passed}
    run["status"] = "complete" if passed == 19 else "failed"
    write_json(run_dir / "run.json", run)
    return checks
