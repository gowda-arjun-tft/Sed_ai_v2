from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..settings import SKIPPED_SECTIONS, SMALL_SECTION_TOKENS, TARGET_TOKENS
from ..claims import input_claim_blocks
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


def _prepare_fact_pieces(kept: list[Section]) -> list[PreparedPiece]:
    prepared: list[PreparedPiece] = []
    small: list[Section] = []

    def flush_small() -> None:
        if not small:
            return
        prepared.append(
            (
                [section.title for section in small],
                "\n\n".join(section.raw for section in small),
                "1/1",
                sum(len(fact_blocks(section.raw)) for section in small),
            )
        )
        small.clear()

    for section in kept:
        size = estimate_tokens(section.raw)
        if size < SMALL_SECTION_TOKENS:
            combined = "\n\n".join(item.raw for item in small + [section])
            if small and estimate_tokens(combined) > TARGET_TOKENS:
                flush_small()
            small.append(section)
            continue
        flush_small()
        blocks = fact_blocks(section.raw)
        if size <= TARGET_TOKENS or not blocks:
            prepared.append(([section.title], section.raw, "1/1", len(blocks)))
            continue
        chunks: list[list[str]] = []
        current: list[str] = []
        for block in blocks:
            candidate = current + [block]
            if current and estimate_tokens("\n\n".join(candidate)) > TARGET_TOKENS:
                chunks.append(current)
                current = [block]
            else:
                current = candidate
        if current:
            chunks.append(current)
        for index, chunk in enumerate(chunks, 1):
            body = f"## {section.title}\n\n" + "\n\n".join(chunk)
            prepared.append(
                ([section.title], body, f"{index}/{len(chunks)}", len(chunk))
            )
    flush_small()
    return prepared


def _prepare_claim_pieces(blocks: list[str]) -> list[PreparedPiece]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for block in blocks:
        candidate = current + [block]
        body = "## Claims\n\n" + "\n\n".join(candidate)
        if current and estimate_tokens(body) > TARGET_TOKENS:
            chunks.append(current)
            current = [block]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [
        (
            ["Claims"],
            "## Claims\n\n" + "\n\n".join(chunk),
            f"{index}/{len(chunks)}",
            len(chunk),
        )
        for index, chunk in enumerate(chunks, 1)
    ]


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
    input_path = run_dir / "inputs" / run.get("input_file", "fact_sheet.md")
    source = read_text(input_path)
    if run.get("input_format") == "json":
        original_blocks = input_claim_blocks(input_path)
        prepared = _prepare_claim_pieces(original_blocks)
        rows = _write_pieces(run_dir, prepared)
        write_progress(run_dir, rows)
        cut = Counter()
        for path in sorted((run_dir / "pieces").glob("p*.md")):
            cut.update(atoms(piece_body(path), "claims"))
        if Counter(original_blocks) != cut:
            raise RuntimeError("phase 1 failed its lossless JSON-claim cut check")
        run["split_mode"] = "claims"
        run["input"]["claims"] = len(original_blocks)
        run["pieces"] = len(rows)
        run["sections_set_aside"] = 0
        run["status"] = "split"
        write_json(run_dir / "run.json", run)
        return

    sections = split_sections(source)
    mode = "facts" if fact_blocks(source) else "sections"
    kept, skipped = _partition_sections(sections)

    skipped_dir = run_dir / "pieces" / "_skipped"
    skipped_dir.mkdir(exist_ok=True)
    for section, reason in skipped:
        path = skipped_dir / f"{slug(section.title)}.md"
        atomic_write_text(path, f"<!-- skipped: {reason} -->\n\n{section.raw}\n")

    if mode == "sections":
        prepared = [([section.title], section.raw, "1/1", 1) for section in kept]
    else:
        prepared = _prepare_fact_pieces(kept)
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
