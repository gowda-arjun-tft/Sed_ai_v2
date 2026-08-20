from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents.graph import DeepAgentState
from pydantic import BaseModel, Field



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


class ResearchState(DeepAgentState):
    query_count: int


@dataclass(frozen=True)
class ResearchContext:
    run_dir: Path
    agent: str
    lens: str
    round_name: str
    session_id: str
    retriever: Any


@dataclass(frozen=True)
class SessionSpec:
    agent: str
    lens: str
    round_name: str
    thread_id: str
    target: Path
    mission: dict[str, Any]
    definition: dict[str, Any]
    questions: tuple[str, ...] = ()
    focus: str = ""


class QuestionSet(BaseModel):
    """Questions for each lens.

    Attribution cannot leak because the schema has nowhere to put it: a question
    is a bare string, and no field records which lens raised it.
    """

    practitioner: list[str] = Field(default_factory=list)
    academic: list[str] = Field(default_factory=list)
    economist: list[str] = Field(default_factory=list)
    historian: list[str] = Field(default_factory=list)
    skeptic: list[str] = Field(default_factory=list)


class GapDecision(BaseModel):
    """Whether the aggregator wants a sixth lens, and what it should look at.

    No length limit, no required-field rule, no clearing of fields the model
    chose to fill. It is recorded as given.
    """

    needed: bool
    name: str = ""
    focus: str = ""
    reason: str = ""


class AnswerDraft(BaseModel):
    """The aggregator's answer, exactly as written."""

    markdown: str = ""
