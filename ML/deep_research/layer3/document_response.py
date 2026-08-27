"""Bounded, deterministic views over retained document pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ML.deep_research.layer2.fs import load_json, read_text

if TYPE_CHECKING:
    from .document_extraction import ExtractionPolicy


def _root(run_dir: Path, source_id: str) -> Path:
    return run_dir / "sources" / "documents" / source_id


def _parse_pages(value: str, maximum: int) -> list[int]:
    pages: list[int] = []
    for item in value.split(","):
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", item.strip())
        if not match:
            raise ValueError("pages must look like '3', '3-7', or '1,4-6'")
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        if start < 1 or end < start:
            raise ValueError("page numbers must be positive and ranges ascending")
        for page in range(start, end + 1):
            if page not in pages:
                pages.append(page)
            if len(pages) > maximum:
                raise ValueError(f"one read_source call may request at most {maximum} pages")
    return pages


def _page_paths(run_dir: Path, source_id: str) -> list[Path]:
    return sorted((_root(run_dir, source_id) / "pages").glob("[0-9][0-9][0-9][0-9].md"))


def _header(manifest: dict[str, Any], source_url: str | None = None) -> str:
    header = f"SOURCE {manifest['source_id']}\nURL {source_url or manifest['url']}"
    if manifest.get("result") == "partial":
        missing = ", ".join(str(page) for page in manifest.get("missing_pages") or [])
        detail = f" Unavailable pages: {missing}." if missing else ""
        header += f"\nEXTRACTION PARTIAL.{detail} See the retained manifest for warnings."
    return header


def _selected_pages(
    manifest: dict[str, Any],
    known: dict[int, str],
    selected: list[int],
    token_budget: int,
    source_url: str | None,
) -> str:
    header = _header(manifest, source_url)
    # The source locator is fixed overhead; bound the evidence body itself.
    character_budget = max(64, token_budget * 4)
    parts: list[str] = []
    used = 0
    remaining: list[int] = []
    for index, number in enumerate(selected):
        part = f"## Page {number}\n\n{known.get(number, '[Page is not available.]')}"
        if parts and used + len(part) > character_budget:
            remaining = selected[index:]
            break
        if not parts and len(part) > character_budget:
            part = part[:character_budget].rstrip() + "\n\n[Page truncated; use find='terms' to locate specific evidence.]"
        parts.append(part)
        used += len(part)
    continuation = ""
    if remaining:
        page_arg = ",".join(str(number) for number in remaining)
        continuation = f"\n\nCONTINUE: call read_source with pages='{page_arg}'."
    return f"{header}\n\n" + "\n\n".join(parts) + continuation


def render_document(
    run_dir: Path,
    source_id: str,
    policy: "ExtractionPolicy",
    *,
    pages: str | None = None,
    find: str | None = None,
    source_url: str | None = None,
) -> str:
    path = _root(run_dir, source_id) / "manifest.json"
    try:
        manifest = load_json(path)
    except (OSError, TypeError, ValueError):
        return f"Stored source {source_id}, but its extraction manifest is unavailable."
    if manifest.get("status") == "failed":
        return (
            f"{_header(manifest, source_url)}\n\nDocument extraction failed: "
            f"{manifest.get('error_type')}: {manifest.get('error')}. "
            "The original file remains retained, but its contents are unavailable."
        )
    if manifest.get("status") != "complete":
        raise RuntimeError(f"document {source_id} is not ready")
    if pages and find:
        return f"{_header(manifest, source_url)}\n\nUse either pages or find in one read_source call, not both."

    if pages:
        try:
            selected = _parse_pages(pages, policy.max_requested_pages)
        except ValueError as error:
            return f"{_header(manifest, source_url)}\n\nInvalid page request: {error}"
        page_root = _root(run_dir, source_id) / "pages"
        known = {
            number: read_text(path)
            for number in selected
            if (path := page_root / f"{number:04d}.md").is_file()
        }
        return _selected_pages(
            manifest,
            known,
            sorted(selected),
            policy.full_document_response_tokens,
            source_url,
        )
    if find:
        needle = " ".join(find.casefold().split())
        hits: list[str] = []
        for path in _page_paths(run_dir, source_id):
            number, text = int(path.stem), read_text(path)
            compact = " ".join(text.split())
            folded = compact.casefold()
            position = 0
            while needle and (index := folded.find(needle, position)) >= 0:
                start = max(0, min(index - 200, len(compact) - 500))
                hits.append(f"- Page {number}: {compact[start:start + 500]}")
                position = index + len(needle)
                if len(hits) >= policy.find_max_hits:
                    break
            if len(hits) >= policy.find_max_hits:
                break
        body = "\n".join(hits) or "No retained page text matched that search."
        return f"{_header(manifest, source_url)}\n\nSearch: {find}\n\n{body}"

    document_path = _root(run_dir, source_id) / "document.md"
    byte_budget = policy.full_document_response_tokens * 4
    if document_path.is_file() and document_path.stat().st_size <= byte_budget:
        text = read_text(document_path)
        return f"{_header(manifest, source_url)}\n\n{text}"
    paths = _page_paths(run_dir, source_id)
    page_count = int(manifest.get("total_pages") or len(paths))
    samples = []
    for path in paths[:40]:
        number, page_text = int(path.stem), read_text(path)
        first = next((line for line in page_text.splitlines() if line.strip()), "[No text]")
        samples.append(f"- Page {number}: {first[:160]}")
    return (
        f"{_header(manifest, source_url)}\n\nDocument map: {page_count} pages. The complete document "
        "is retained outside active context. Call read_source with pages='start-end' "
        "or find='search terms'.\n\n" + "\n".join(samples)
    )
