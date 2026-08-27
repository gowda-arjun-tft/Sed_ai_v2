"""Isolated local Docling worker for one retained source."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import atomic_write_text, now_iso, write_json

from .document_extraction import (
    document_root,
    extraction_policy,
    load_manifest,
    manifest_path,
    process_pass_through,
)
from .docling_backend import (
    convert_docling as _convert_docling,
    docling_converter as _docling_converter,
    extractor_versions as _extractor_versions,
    input_suffix as _input_suffix,
)


_WRITE_LOCK = threading.RLock()
_MISSING_PAGE_TEXT = "[Page unavailable after Docling extraction.]"


class PermanentDocumentError(RuntimeError):
    """A retained source cannot become processable by repeating the worker."""


def _update(run_dir: Path, source_id: str, **values: Any) -> dict[str, Any]:
    with _WRITE_LOCK:
        manifest = load_manifest(run_dir, source_id)
        if manifest is None:
            raise RuntimeError(f"document job {source_id} is missing")
        manifest.update(values, updated_at=now_iso())
        write_json(manifest_path(run_dir, source_id), manifest)
        return manifest


class _Heartbeat:
    def __init__(self, run_dir: Path, source_id: str, seconds: int) -> None:
        self.run_dir = run_dir
        self.source_id = source_id
        self.seconds = max(1, seconds)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._beat, daemon=True)

    def _beat(self) -> None:
        while not self.stop.wait(self.seconds):
            try:
                _update(self.run_dir, self.source_id, heartbeat_at=now_iso())
            except (OSError, RuntimeError, ValueError):
                return

    def __enter__(self) -> "_Heartbeat":
        self.thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.stop.set()
        self.thread.join(timeout=self.seconds + 1)


def _pdf_pages(path: Path) -> int:
    try:
        import pypdfium2
    except ImportError as error:  # Docling installs this; keep module import cheap in tests.
        raise RuntimeError("pypdfium2 is required to count PDF pages") from error
    document = pypdfium2.PdfDocument(path)
    try:
        return len(document)
    finally:
        document.close()


def _write_batch(
    run_dir: Path,
    source_id: str,
    start: int,
    end: int,
    pages: dict[int, str],
    payload: dict[str, Any],
) -> None:
    root = document_root(run_dir, source_id)
    page_root = root / "pages"
    batch_root = root / "batches" / f"{start:04d}-{end:04d}"
    for number, text in sorted(pages.items()):
        atomic_write_text(page_root / f"{number:04d}.md", text.strip() + "\n")
    atomic_write_text(
        batch_root / "docling.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def _batch_is_complete(run_dir: Path, source_id: str, start: int, end: int) -> bool:
    root = document_root(run_dir, source_id)
    if not (root / "batches" / f"{start:04d}-{end:04d}" / "docling.json").is_file():
        return False
    return all((root / "pages" / f"{page:04d}.md").is_file() for page in range(start, end + 1))


def _publish(run_dir: Path, source_id: str, total_pages: int) -> None:
    root = document_root(run_dir, source_id)
    parts = []
    for number in range(1, total_pages + 1):
        path = root / "pages" / f"{number:04d}.md"
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else _MISSING_PAGE_TEXT
        parts.append(f"## Page {number}\n\n{text.strip()}")
    combined = "\n\n".join(parts).strip() + "\n"
    atomic_write_text(root / "document.md", combined)
    atomic_write_text(run_dir / "sources" / "text" / f"{source_id}.txt", combined)


def _process_pdf_batch(
    converter: Any,
    input_path: Path,
    run_dir: Path,
    source_id: str,
    start: int,
    end: int,
    page_attempts: dict[str, int],
    warnings: list[str],
) -> list[int]:
    page_root = document_root(run_dir, source_id) / "pages"
    expected = list(range(start, end + 1))
    while True:
        missing = [page for page in expected if not (page_root / f"{page:04d}.md").is_file()]
        eligible = [page for page in missing if page_attempts.get(str(page), 0) < 3]
        if not eligible:
            return missing
        existing = len(expected) - len(missing)
        requested = (eligible[0], eligible[-1]) if not existing else (eligible[0], eligible[0])
        for page in range(requested[0], requested[1] + 1):
            page_attempts[str(page)] = page_attempts.get(str(page), 0) + 1
        _update(run_dir, source_id, page_attempts=page_attempts, heartbeat_at=now_iso())
        pages, payload, issues = _convert_docling(converter, input_path, requested)
        for issue in issues:
            if issue and issue not in warnings:
                warnings.append(issue)
        _update(run_dir, source_id, warnings=warnings, heartbeat_at=now_iso())
        _write_batch(run_dir, source_id, start, end, pages, payload)


def process_document_job(run_dir: Path, source_id: str) -> dict[str, Any]:
    """Convert one job, reusing every atomically completed PDF batch."""
    policy = extraction_policy(run_dir)
    manifest = load_manifest(run_dir, source_id)
    if policy is None or manifest is None:
        raise RuntimeError(f"document extraction policy or job {source_id} is missing")
    if manifest.get("status") == "complete":
        return manifest
    if manifest.get("kind") == "pass_through":
        return process_pass_through(run_dir, source_id)

    _update(
        run_dir,
        source_id,
        status="running",
        attempt=int(manifest.get("attempt", 0)) + 1,
        worker_pid=os.getpid(),
        heartbeat_at=now_iso(),
        extractor_versions=_extractor_versions(),
        error_type="",
        error="",
        retryable=True,
    )
    raw_path = run_dir / str(manifest["raw_path"])
    if not raw_path.is_file():
        raise PermanentDocumentError(f"retained source is missing: {raw_path}")
    if raw_path.stat().st_size > policy.max_document_bytes:
        raise PermanentDocumentError(
            f"document exceeds the {policy.max_document_bytes // (1024 * 1024)} MiB limit"
        )

    root = document_root(run_dir, source_id)
    input_path = root / f"input{_input_suffix(manifest)}"
    if not input_path.exists():
        try:
            os.link(raw_path, input_path)
        except OSError:
            shutil.copyfile(raw_path, input_path)

    media_type = str(manifest.get("content_type", "")).partition(";")[0].casefold()
    is_pdf = media_type == "application/pdf" or input_path.suffix.casefold() == ".pdf"
    total_pages = _pdf_pages(input_path) if is_pdf else 1
    if total_pages > policy.max_pdf_pages:
        raise PermanentDocumentError(
            f"PDF has {total_pages} pages; the limit is {policy.max_pdf_pages}"
        )

    _update(
        run_dir,
        source_id,
        total_pages=total_pages,
    )
    completed = list(manifest.get("completed_batches") or [])
    page_attempts = dict(manifest.get("page_attempts") or {})
    warnings = list(manifest.get("warnings") or [])
    missing_pages = list(manifest.get("missing_pages") or [])
    with _Heartbeat(run_dir, source_id, policy.worker_heartbeat_seconds):
        converter = _docling_converter(list(policy.ocr_languages))
        if is_pdf:
            ranges = [
                (start, min(start + policy.pdf_batch_pages - 1, total_pages))
                for start in range(1, total_pages + 1, policy.pdf_batch_pages)
            ]
        else:
            ranges = [(1, 1)]
        for start, end in ranges:
            if _batch_is_complete(run_dir, source_id, start, end):
                if not any(item.get("start") == start and item.get("end") == end for item in completed):
                    completed.append({"start": start, "end": end})
                continue
            if is_pdf:
                missing_pages.extend(
                    _process_pdf_batch(
                        converter, input_path, run_dir, source_id,
                        start, end, page_attempts, warnings,
                    )
                )
            else:
                pages, payload, issues = _convert_docling(converter, input_path, None)
                warnings.extend(issue for issue in issues if issue and issue not in warnings)
                _write_batch(run_dir, source_id, start, end, pages, payload)
        if not is_pdf:
            page_files = list((root / "pages").glob("[0-9][0-9][0-9][0-9].md"))
            total_pages = max(1, len(page_files))
        usable_pages = total_pages - len(set(missing_pages))
        if usable_pages <= 0 or not any((root / "pages").glob("[0-9][0-9][0-9][0-9].md")):
            raise RuntimeError("Docling produced no usable page text")
        _update(
            run_dir,
            source_id,
            missing_pages=sorted(set(missing_pages)),
            warnings=warnings,
            page_attempts=page_attempts,
            heartbeat_at=now_iso(),
        )
        for page in sorted(set(missing_pages)):
            atomic_write_text(root / "pages" / f"{page:04d}.md", _MISSING_PAGE_TEXT + "\n")
            warning = f"Docling omitted page {page} after three attempts"
            if warning not in warnings:
                warnings.append(warning)
        completed = [
            {"start": start, "end": end}
            for start, end in ranges
            if _batch_is_complete(run_dir, source_id, start, end)
        ]
        _publish(run_dir, source_id, total_pages)

    return _update(
        run_dir,
        source_id,
        status="complete",
        result="partial" if missing_pages or warnings else "complete",
        missing_pages=sorted(set(missing_pages)),
        warnings=warnings,
        page_attempts=page_attempts,
        total_pages=total_pages,
        completed_batches=completed,
        completed_at=now_iso(),
        heartbeat_at=now_iso(),
        artifacts={"markdown": "document.md", "pages": "pages", "docling_json": "batches"},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one retained Layer 3 document")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ocr-languages", default="de,en")
    args = parser.parse_args(argv)
    if args.check:
        try:
            __import__("easyocr")
            _docling_converter([item for item in args.ocr_languages.split(",") if item])
        except Exception as error:
            parser.exit(1, f"{type(error).__name__}: {str(error) or repr(error)}\n")
        return 0
    if args.run_dir is None or not args.source_id:
        parser.error("--run-dir and --source-id are required unless --check is used")
    try:
        process_document_job(args.run_dir.resolve(), args.source_id)
    except Exception as error:
        if load_manifest(args.run_dir, args.source_id) is not None:
            _update(
                args.run_dir,
                args.source_id,
                status="failed",
                error_type=type(error).__name__,
                error=str(error) or repr(error),
                retryable=not isinstance(error, PermanentDocumentError),
                heartbeat_at=now_iso(),
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
