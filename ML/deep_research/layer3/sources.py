from __future__ import annotations

import hashlib
import json
import secrets
import threading
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import atomic_write_text, read_text, text_hash

from .contracts import Document
from .retrieval import normalize_url
from .text_extraction import canonical_text, detect_encoding, encoding_was_declared


_LOCK = threading.RLock()


def _normalize_whitespace(value: str) -> str:
    """Collapse whitespace without changing words, case, or punctuation."""
    return " ".join(value.split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in read_text(path).splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _append_unique(path: Path, record: dict[str, Any], key: str) -> None:
    with _LOCK:
        if any(item.get(key) == record.get(key) for item in load_jsonl(path)):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()


class SourceStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.root = run_dir / "sources"

    def store(self, document: Document) -> dict[str, Any]:
        source_id = hashlib.sha256(document.body).hexdigest()
        raw_path = self.root / "raw" / source_id[:2] / f"{source_id}.bin"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if not raw_path.exists():
            temporary = raw_path.with_name(f".{raw_path.name}.{secrets.token_hex(4)}.tmp")
            temporary.write_bytes(document.body)
            temporary.replace(raw_path)
        text = canonical_text(document.body, document.content_type)
        text_path = self.root / "text" / f"{source_id}.txt"
        if text is not None and not text_path.exists():
            atomic_write_text(text_path, text)
        record = {
            "index_id": text_hash(f"{normalize_url(document.url)}\n{source_id}"),
            "source_sha256": source_id,
            "url": document.url,
            "normalized_url": normalize_url(document.url),
            "fetched_at": document.fetched_at,
            "content_type": document.content_type,
            "bytes": len(document.body),
            "publisher": document.publisher,
            "publication_date": document.publication_date,
            "raw_path": str(raw_path.relative_to(self.run_dir)).replace("\\", "/"),
            "text_path": (
                str(text_path.relative_to(self.run_dir)).replace("\\", "/")
                if text is not None
                else ""
            ),
            "text_sha256": text_hash(text) if text is not None else "",
            "citation_supported": text is not None,
            # Recorded so an unexplained citation failure can be traced back to a
            # decoding guess rather than looking like the model invented a quote.
            "encoding": detect_encoding(document.body, document.content_type),
            "encoding_declared": encoding_was_declared(
                document.body, document.content_type
            ),
        }
        _append_unique(self.root / "index.jsonl", record, "index_id")
        return record

    def record_query(
        self,
        *,
        session_id: str,
        agent: str,
        lens: str,
        query: str,
        new_sources: int = 0,
    ) -> None:
        normalized_query = _normalize_whitespace(query)
        query_id = text_hash(
            f"{session_id}\n{agent}\n{lens}\n{normalized_query}"
        )
        _append_unique(
            self.root / "queries.jsonl",
            {
                "query_id": query_id,
                "session_id": session_id,
                "agent": agent,
                "lens": lens,
                "query": query,
                "new_sources": new_sources,
            },
            "query_id",
        )

    def record_citation(
        self,
        *,
        source_id: str,
        quote: str,
        tier: int,
        agent: str,
        lens: str,
        session_id: str,
    ) -> str:
        """Verify a retained exact quote and record it once."""
        citation = {
            "source_sha256": source_id,
            "quote": quote,
            "tier": tier,
            "agent": agent,
            "lens": lens,
            "session_id": session_id,
        }
        valid, detail = self.validate_citation(citation)
        if not valid:
            raise ValueError(detail)
        normalized_quote = _normalize_whitespace(quote)
        citation_id = text_hash(
            f"{session_id}\n{agent}\n{lens}\n{source_id}\n{normalized_quote}\n{tier}"
        )
        citation["citation_id"] = citation_id
        _append_unique(
            self.root / "citations.jsonl",
            citation,
            "citation_id",
        )
        return f"[citation:{citation_id}]"

    def validate_citation(self, citation: dict[str, Any]) -> tuple[bool, str]:
        """Revalidate a citation record against retained canonical source text."""
        source_id = str(citation.get("source_sha256", ""))
        record = self.source_record(source_id)
        if record is None:
            return False, f"unknown source: {source_id}"
        quote = citation.get("quote")
        if not isinstance(quote, str) or not _normalize_whitespace(quote):
            return False, "citation quote cannot be empty"
        tier = citation.get("tier")
        if type(tier) is not int or tier not in range(1, 5):
            return False, "citation tier must be an integer from 1 through 4"
        if not all(
            str(citation.get(field, "")).strip()
            for field in ("session_id", "agent", "lens")
        ):
            return False, "citation identity fields cannot be empty"
        text = self.source_text(source_id)
        if not record.get("citation_supported") or text is None:
            return False, "source has no canonical text and cannot be cited"
        if _normalize_whitespace(quote) not in _normalize_whitespace(text):
            return False, "citation quote does not occur in the canonical source text"
        expected_id = text_hash(
            f"{citation.get('session_id', '')}\n{citation.get('agent', '')}\n"
            f"{citation.get('lens', '')}\n{source_id}\n"
            f"{_normalize_whitespace(quote)}\n{tier}"
        )
        if citation.get("citation_id") not in (None, expected_id):
            return False, "citation ID does not match its evidence record"
        return True, ""

    def source_record(self, source_id: str) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in load_jsonl(self.root / "index.jsonl")
                if item.get("source_sha256") == source_id
            ),
            None,
        )

    def record_for_url(self, url: str) -> dict[str, Any] | None:
        normalized = normalize_url(url)
        return next(
            (
                item
                for item in load_jsonl(self.root / "index.jsonl")
                if item.get("normalized_url") == normalized
            ),
            None,
        )

    def source_text(self, source_id: str) -> str | None:
        record = self.source_record(source_id)
        if not record or not record.get("text_path"):
            return None
        path = self.run_dir / str(record["text_path"])
        return read_text(path) if path.is_file() else None

    def citations(self) -> list[dict[str, Any]]:
        return load_jsonl(self.root / "citations.jsonl")

    def cache_path(self, query: str) -> Path:
        return self.root / "query_cache" / f"{text_hash(' '.join(query.split()))}.json"
