from __future__ import annotations

from dataclasses import dataclass



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
