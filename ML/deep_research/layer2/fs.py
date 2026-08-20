"""Filesystem, hashing and JSON helpers.

Shared infrastructure, not Layer 2 logic: eighteen Layer 3 modules import from
here as well. Nothing in this module knows what a fact sheet or a mission is.

Two properties everything here is built around:

* **Text is normalised on the way in, never on the way out.** `read_text` strips
  a BOM and collapses CRLF, so a file written by Notepad on Windows and the same
  file from `git` hash identically. This is file IO, not content policing — no
  function here inspects, filters or rejects what it is given.
* **Writes are atomic.** `atomic_write_text` writes a sibling temp file and
  renames it, so a crash mid-write leaves the previous version intact rather
  than a half-written one. Every JSON artefact in a run goes through it.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    """UTC timestamp as `2026-08-20T14:30:00Z`.

    Seconds resolution and a `Z` suffix rather than `+00:00`, so timestamps sort
    lexically and read the same in every run record.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(text: str) -> str:
    """Filename-safe identifier that survives every writing system.

    This is the join between the layers: `slug(agent_name)` names the mission
    file that Layer 3 later looks up, so the same name must always produce the
    same slug.

    Latin scripts fold to their unaccented form, so ``Bauträger`` becomes
    ``bautrager`` and ``Marché`` becomes ``marche``. Scripts with no Latin form
    keep a stable hashed identifier instead of collapsing to an empty string —
    without that, two Arabic or Chinese headings would overwrite each other's
    file. Pure ASCII input is returned unchanged, which is why the fourteen
    roster slugs did not move when the folding was added.

    `&` becomes ` and ` first, so "Legal, title & encumbrance" reads as
    ``legal-title-and-encumbrance`` rather than losing the conjunction.
    """
    import re
    import unicodedata

    value = text.casefold().replace("&", " and ")
    decomposed = unicodedata.normalize("NFKD", value)
    folded = "".join(item for item in decomposed if not unicodedata.combining(item))
    result = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if result:
        return result
    return f"x-{text_hash(text)[:12]}" if text.strip() else ""


def sha256(path: Path) -> str:
    """Hex digest of a file's bytes, read in 1 MiB chunks.

    Chunked so a large source document is hashed without being held in memory.
    Used to prove the two input copies in a run folder still match their
    originals — Layer 3 re-checks the planner copy's digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    """Hex digest of a string's UTF-8 bytes.

    The in-memory counterpart to `sha256`. Used for identity, not integrity —
    `slug` falls back to it, and Layer 3 keys stored pages by it.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    """Read a UTF-8 text file with line endings and BOM normalised.

    `utf-8-sig` drops a byte-order mark if one is present. CRLF and lone CR
    become LF, so line offsets and regex matches behave identically whatever
    wrote the file. Every text read in both layers goes through this.
    """
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def atomic_write_text(path: Path, text: str) -> None:
    """Write text so that the file is either the old version or the new one.

    Creates parent directories, writes `.{name}.{8 hex}.tmp` beside the target
    and renames it over the target — a rename within one directory is atomic on
    every platform this runs on. `newline="\n"` keeps written files LF even on
    Windows, matching what `read_text` expects.

    One Windows caveat: the temp name is 14 characters longer than the target,
    so a path within 14 characters of the 260-character MAX_PATH limit fails
    here with a `FileNotFoundError` naming a directory that plainly exists. Keep
    run folders near the drive root.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    """Write pretty-printed UTF-8 JSON atomically, with a trailing newline.

    `ensure_ascii=False` keeps non-Latin text readable in the file instead of
    escaped, and the two-space indent means a run artefact diffs line by line.
    """
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    """Parse a JSON file written by `write_json` (or by the agent).

    Raises `json.JSONDecodeError` on malformed input. Callers that are inspecting
    something the agent wrote catch that and record it as a failed check rather
    than crashing the run.
    """
    return json.loads(read_text(path))
