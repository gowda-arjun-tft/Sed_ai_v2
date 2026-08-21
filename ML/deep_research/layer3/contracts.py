from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class ResearchOutcome(BaseModel):
    """Small terminal status after report fragments have already been persisted."""

    status: Literal["answered", "cannot_be_answered"]
    unknowns: list[str] = Field(default_factory=list)
    reason: str = ""


class DomainQuestions(BaseModel):
    """Bare questions for one known domain."""

    domain: str
    questions: list[str]


class ReviewOutcome(BaseModel):
    """One written review and its optional grouped clarification questions."""

    review_markdown: str
    questions: list[DomainQuestions] = Field(default_factory=list)
