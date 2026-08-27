"""Durable document jobs and bounded source responses for ``read_source``.

The model sees one tool.  This module owns the application side of that tool:
content-addressed extraction jobs, their retained artifacts, and the small
supervisor bridge used when LangGraph pauses for a local conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import atomic_write_text, load_json, now_iso, write_json

from .document_response import render_document


PASS_THROUGH_TYPES = frozenset({"text/plain", "text/markdown", "application/json"})
IMAGE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"}
)
DOCLING_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html",
        "application/xhtml+xml",
    }
)
_DOCLING_SUFFIXES = frozenset(
    {".pdf", ".docx", ".pptx", ".html", ".htm", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)
_PASS_THROUGH_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".json"})
MAX_DOCUMENT_ATTEMPTS = 3


@dataclass(frozen=True)
class ExtractionPolicy:
    policy_version: int
    ocr_languages: tuple[str, ...]
    max_document_bytes: int
    max_pdf_pages: int
    pdf_batch_pages: int
    full_document_response_tokens: int
    max_requested_pages: int
    find_max_hits: int
    worker_heartbeat_seconds: int
    worker_stale_seconds: int


@dataclass(frozen=True)
class PendingDocument:
    source_id: str
    url: str

    def payload(self) -> dict[str, str]:
        return {"type": "document_extraction", "source_id": self.source_id, "url": self.url}


def extraction_policy(run_dir: Path) -> ExtractionPolicy | None:
    """Load the run-frozen policy; absent/unknown policies keep legacy behavior."""
    try:
        value = load_json(run_dir / "run.json").get("document_extraction")
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("policy_version") != 1:
        return None
    return ExtractionPolicy(
        policy_version=1,
        ocr_languages=tuple(value.get("ocr_languages") or ("de", "en")),
        max_document_bytes=int(value.get("max_document_bytes", 50 * 1024 * 1024)),
        max_pdf_pages=int(value.get("max_pdf_pages", 2_000)),
        pdf_batch_pages=int(value.get("pdf_batch_pages", 25)),
        full_document_response_tokens=int(value.get("full_response_token_threshold", 16_000)),
        max_requested_pages=int(value.get("max_requested_pages", 30)),
        find_max_hits=int(value.get("max_find_hits", 40)),
        worker_heartbeat_seconds=int(value.get("worker_heartbeat_seconds", 10)),
        worker_stale_seconds=int(value.get("worker_stale_seconds", 60)),
    )


def document_root(run_dir: Path, source_id: str) -> Path:
    return run_dir / "sources" / "documents" / source_id


def manifest_path(run_dir: Path, source_id: str) -> Path:
    return document_root(run_dir, source_id) / "manifest.json"


def load_manifest(run_dir: Path, source_id: str) -> dict[str, Any] | None:
    path = manifest_path(run_dir, source_id)
    try:
        value = load_json(path)
    except (OSError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def extraction_kind(content_type: str, url: str) -> str | None:
    media_type = content_type.partition(";")[0].strip().casefold()
    suffix = Path(url.split("?", 1)[0]).suffix.casefold()
    if suffix in _DOCLING_SUFFIXES:
        return "docling"
    if media_type in DOCLING_TYPES or media_type in IMAGE_TYPES:
        return "docling"
    if media_type in PASS_THROUGH_TYPES:
        return "pass_through"
    if suffix in _PASS_THROUGH_SUFFIXES:
        return "pass_through"
    return None


def ensure_document_job(
    run_dir: Path,
    record: dict[str, Any],
    policy: ExtractionPolicy,
) -> dict[str, Any] | None:
    """Create one immutable-identity job for a retained source, if supported."""
    source_id = str(record["source_sha256"])
    existing = load_manifest(run_dir, source_id)
    if existing is not None:
        return existing
    kind = extraction_kind(str(record.get("content_type", "")), str(record.get("url", "")))
    if kind is None:
        return None
    manifest = {
        "policy_version": policy.policy_version,
        "source_id": source_id,
        "url": str(record.get("url", "")),
        "content_type": str(record.get("content_type", "")),
        "raw_path": str(record.get("raw_path", "")),
        "kind": kind,
        "status": "pending",
        "attempt": 0,
        "ocr_languages": list(policy.ocr_languages),
        "total_pages": None,
        "completed_batches": [],
        "error_type": "",
        "error": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "heartbeat_at": "",
        "worker_pid": None,
        "artifacts": {},
    }
    write_json(manifest_path(run_dir, source_id), manifest)
    return manifest


def process_pass_through(run_dir: Path, source_id: str) -> dict[str, Any]:
    """Finish a cheap text job inline; no worker or agent interruption is needed."""
    manifest = load_manifest(run_dir, source_id)
    if manifest is None or manifest.get("kind") != "pass_through":
        raise ValueError(f"{source_id} is not a pass-through document job")
    if manifest.get("status") == "complete":
        return manifest
    from .text_extraction import canonical_text, detect_encoding

    raw_path = run_dir / str(manifest["raw_path"])
    body = raw_path.read_bytes()
    content_type = str(manifest["content_type"])
    text = canonical_text(body, content_type)
    if text is None:  # A text-like URL served as application/octet-stream.
        text = body.decode(detect_encoding(body, content_type), errors="replace")
    root = document_root(run_dir, source_id)
    pages = root / "pages"
    atomic_write_text(pages / "0001.md", text)
    atomic_write_text(root / "document.md", text)
    atomic_write_text(run_dir / "sources" / "text" / f"{source_id}.txt", text)
    manifest.update(
        status="complete",
        result="complete",
        missing_pages=[],
        warnings=[],
        total_pages=1,
        completed_batches=[{"start": 1, "end": 1}],
        updated_at=now_iso(),
        completed_at=now_iso(),
        artifacts={"markdown": "document.md", "pages": "pages"},
    )
    write_json(manifest_path(run_dir, source_id), manifest)
    return manifest

