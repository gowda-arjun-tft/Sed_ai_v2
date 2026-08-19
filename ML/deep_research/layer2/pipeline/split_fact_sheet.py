from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..settings import SKIPPED_SECTIONS
from ..fs import atomic_write_text, load_json, slug, write_json
from ..factsheet import (
    Section,
    atoms,
    estimate_tokens,
    fact_blocks,
    field_value,
    piece_body,
    split_sections,
)
from ..progress import write_progress
from ..fs import read_text


PreparedPiece = tuple[list[str], str, str, int]


def _partition_sections(sections: list[Section]) -> tuple[list[Section], list[tuple[Section, str]]]:
    kept: list[Section] = []
    skipped: list[tuple[Section, str]] = []
    for section in sections:
        reason = SKIPPED_SECTIONS.get(section.title.casefold())
        if section.title.casefold() == "executive readout":
            other_text = "\n".join(item.raw for item in sections if item is not section)
            evidence = [field_value(block, "Evidence") for block in fact_blocks(section.raw)]
            if evidence and not all(value and value in other_text for value in evidence):
                reason = None
        if reason:
            skipped.append((section, reason))
        else:
            kept.append(section)
    return kept, skipped


def _write_pieces(run_dir: Path, prepared: list[PreparedPiece]) -> list[dict[str, str]]:
    rows = []
    for number, (titles, body, part, count) in enumerate(prepared, 1):
        piece_id = f"p{number:03d}"
        label = "-and-".join(slug(title) for title in titles)
        size = estimate_tokens(body)
        joined_title = " + ".join(titles)
        comment = (
            f'<!-- piece {piece_id} · from section "{joined_title}" · '
            f"{part} · ~{size} tokens -->"
        )
        path = run_dir / "pieces" / f"{piece_id}_{label}.md"
        atomic_write_text(path, f"{comment}\n\n{body.strip()}\n")
        rows.append(
            {
                "piece_id": piece_id,
                "section": joined_title,
                "part": part,
                "tokens": str(size),
                "facts_in_piece": str(count),
                "status": "pending",
                "facts_routed": "",
                "facts_unrouted": "",
                "routed_at": "",
            }
        )
    return rows


def split_fact_sheet(run_dir: Path) -> None:
    run = load_json(run_dir / "run.json")
    source = read_text(run_dir / "inputs" / "fact_sheet.md")
    sections = split_sections(source)
    mode = "facts" if fact_blocks(source) else "sections"
    kept, skipped = _partition_sections(sections)

    skipped_dir = run_dir / "pieces" / "_skipped"
    skipped_dir.mkdir(exist_ok=True)
    for section, reason in skipped:
        path = skipped_dir / f"{slug(section.title)}.md"
        atomic_write_text(path, f"<!-- skipped: {reason} -->\n\n{section.raw}\n")

    prepared = [
        (
            [section.title],
            section.raw,
            "1/1",
            len(fact_blocks(section.raw)) if mode == "facts" else 1,
        )
        for section in kept
    ]
    rows = _write_pieces(run_dir, prepared)
    write_progress(run_dir, rows)

    original = Counter(atoms(source, mode))
    cut = Counter()
    for path in sorted((run_dir / "pieces").glob("p*.md")):
        cut.update(atoms(piece_body(path), mode))
    for path in sorted(skipped_dir.glob("*.md")):
        cut.update(atoms(read_text(path), mode))
    pieces_empty = any(
        not piece_body(path).strip()
        for path in (run_dir / "pieces").glob("p*.md")
    )
    if original != cut or pieces_empty:
        raise RuntimeError("phase 1 failed its lossless-cut check")

    run["split_mode"] = mode
    run["fact_sheet"]["blocks"] = len(original)
    run["pieces"] = len(rows)
    run["sections_set_aside"] = len(skipped)
    run["status"] = "split"
    write_json(run_dir / "run.json", run)
