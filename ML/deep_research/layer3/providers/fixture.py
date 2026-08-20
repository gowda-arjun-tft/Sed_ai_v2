from __future__ import annotations

import json
from pathlib import Path

from ML.deep_research.layer2.fs import now_iso, text_hash


from ..contracts import Document, SearchHit
from ..retrieval import hit_id


class FixtureRetriever:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def search(self, query: str) -> list[SearchHit]:
        path = self.root / "queries" / f"{text_hash(' '.join(query.split()))}.json"
        if not path.is_file():
            return []
        values = json.loads(path.read_text(encoding="utf-8"))
        return [
            SearchHit(
                hit_id=hit_id(str(item["url"])),
                url=str(item["url"]),
                title=str(item.get("title", item["url"])),
                snippet=str(item.get("snippet", "")),
            )
            for item in values
        ]

    async def fetch(self, url: str) -> Document:
        key = text_hash(url)
        body_path = self.root / "pages" / f"{key}.bin"
        if not body_path.is_file():
            raise FileNotFoundError(f"fixture page missing for {url}")
        meta_path = self.root / "pages" / f"{key}.json"
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return Document(
            url=url,
            content_type=str(metadata.get("content_type", "text/html; charset=utf-8")),
            body=body_path.read_bytes(),
            fetched_at=str(metadata.get("fetched_at", now_iso())),
            publisher=str(metadata.get("publisher", "fixture")),
            publication_date=str(metadata.get("publication_date", "")),
        )
