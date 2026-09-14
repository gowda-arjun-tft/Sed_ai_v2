"""Shared normalized-read, atomic-write, hashing and path helpers."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def storage_path(path: Path) -> Path:
    """Input a local path; return its Windows extended form for deeply versioned Layer 2 storage."""
    path = Path(path).resolve()
    text = str(path)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return Path("\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text)
    return path


def now_iso() -> str:
    """Input none; return a sortable UTC timestamp for run metadata."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(text: str) -> str:
    """Input display text; return a stable cross-layer filename identifier."""
    import re
    import unicodedata

    value = text.casefold().replace("&", " and ")
    decomposed = unicodedata.normalize("NFKD", value)
    folded = "".join(item for item in decomposed if not unicodedata.combining(item))
    result = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if result:
        return result
    return f"x-{text_hash(text)[:12]}" if text.strip() else ""


def run_group_name(source: Path) -> str:
    """Input a source path; return its readable, path-stable run-group name."""
    label = "-".join(
        part for part in (slug(source.parent.name)[:32], slug(source.stem)[:48]) if part
    )
    identity = text_hash(str(source.resolve()).casefold())[:8]
    return f"{label or 'fact-sheet'}-{identity}"


def sha256(path: Path) -> str:
    """Input a file path; return its streaming SHA-256 digest for provenance checks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    """Input text; return its UTF-8 SHA-256 digest for stable identities."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    """Input a UTF-8 path; return BOM-free text with normalized line endings."""
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def atomic_write_text(path: Path, text: str) -> None:
    """Input a path and text; atomically replace the file for crash-safe persistence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    """Input a path and value; atomically save readable UTF-8 JSON artifacts."""
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> Any:
    """Input a JSON path; return its parsed value for run orchestration."""
    return json.loads(read_text(path))
