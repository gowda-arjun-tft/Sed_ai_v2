from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

@dataclass(frozen=True)
class SearchHit:
    hit_id: str
    url: str
    title: str
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


class MissionOutcome(BaseModel):
    """The small machine-readable result returned after all Markdown is staged."""

    status: Literal["answered", "cannot_be_answered"]
    reason: str = ""
    additional_lens: str = ""
    additional_focus: str = ""
