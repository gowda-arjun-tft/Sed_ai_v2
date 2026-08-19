from __future__ import annotations

import csv
import json
import re
import secrets
from pathlib import Path

from .fs import read_text


PROGRESS_FIELDS = [
    "piece_id",
    "section",
    "part",
    "tokens",
    "facts_in_piece",
    "status",
    "facts_routed",
    "facts_unrouted",
    "routed_at",
]


def read_progress(run_dir: Path) -> list[dict[str, str]]:
    with (run_dir / "progress.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def write_progress(run_dir: Path, rows: list[dict[str, str]]) -> None:
    target = run_dir / "progress.csv"
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROGRESS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(target)


def bucket_entries(path: Path) -> list[tuple[dict[str, str], str]]:
    if not path.exists():
        return []
    entries = []
    pattern = r"<!-- route (\{.*?\}) -->\n(.*?)\n<!-- /route -->"
    for match in re.finditer(pattern, read_text(path), re.S):
        entries.append((json.loads(match.group(1)), match.group(2).strip()))
    return entries
