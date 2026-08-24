from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


LENS_NAMES = (
    "practitioner",
    "academic",
    "skeptic",
    "economist",
    "historian",
)
VERIFIER_NAME = "citation-verifier"


@dataclass(frozen=True)
class SearchHit:
    hit_id: str
    url: str
    title: str
    publisher: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class Document:
    url: str
    content_type: str
    body: bytes
    fetched_at: str
    publisher: str = ""
    publication_date: str = ""


@dataclass(frozen=True)
class ResearchContext:
    run_dir: Path
    agent: str
    session_id: str
    retriever: Any
