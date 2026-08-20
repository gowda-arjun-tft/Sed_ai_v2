from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(text: str) -> str:
    """Filename-safe identifier that survives every writing system.

    Latin scripts fold to their unaccented form, so ``Bauträger`` becomes
    ``bautrager`` and ``Marché`` becomes ``marche``. Scripts with no Latin form
    keep a stable hashed identifier instead of collapsing to an empty string.
    Pure ASCII input is returned unchanged.
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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))
