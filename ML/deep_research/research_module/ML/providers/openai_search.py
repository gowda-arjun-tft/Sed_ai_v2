"""Native search records and bounded, public-only source reads."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import replace
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from ML.deep_research.domain_decider.backend.fs import now_iso

from ...backend.contracts import Document, SearchHit
from ...backend.retrieval import hit_id, validate_public_url
from ...backend.settings import (
    FETCH_TIMEOUT_SECONDS,
    MAX_SOURCE_BYTES,
)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Encode and validate every redirect before allowing another request."""
        return super().redirect_request(req, fp, code, msg, headers, encoded_url(newurl))


class SourceSizeError(ValueError):
    """A declared or streamed response exceeds the frozen source-read allowance."""


def encoded_url(url: str) -> str:
    """Encode Unicode components without altering escaped bytes or meaningful query separators."""
    validate_public_url(url)
    parts = urlsplit(url)
    host = parts.hostname.encode("idna").decode("ascii")
    if ":" in host:
        host = f"[{host}]"
    authority = host + (f":{parts.port}" if parts.port else "")
    result = urlunsplit((parts.scheme, authority, quote(parts.path, safe="/%:@!$&'()*+,;=-._~"),
                        quote(parts.query, safe="%/?@:!$&'()*+,;=-._~"), ""))
    validate_public_url(result)
    return result


def access_failure(error: Exception) -> dict:
    """Return observations only; do not guess a paywall from an inaccessible endpoint."""
    code = getattr(error, "code", None)
    if isinstance(error, urllib.error.HTTPError):
        kind = "http_restriction" if code in {401, 403, 407, 429, 451} else (
            "missing_endpoint" if code in {404, 410} else "http_failure")
        return {"kind": kind, "http_status": code}
    if isinstance(error, SourceSizeError):
        return {"kind": "size_limit"}
    if isinstance(error, UnicodeError):
        return {"kind": "encoding_failure"}
    return {"kind": "request_failed", "error_type": type(error).__name__}


def _fetch(url: str, max_bytes: int | None = None) -> Document:
    """Bound both advertised and actual response bytes, retaining historical defaults."""
    max_bytes = MAX_SOURCE_BYTES if max_bytes is None else max_bytes
    url = encoded_url(url)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CDI-Deep-Research/1.0",
            "Accept": "text/html,text/plain,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.2",
            # No language preference is expressed. Official sources are published
            # in the jurisdiction's own language, and asking for English first
            # would push every non-English country down to secondary reporting.
            "Accept-Language": "*",
        },
    )
    with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        final_url = response.geturl()
        validate_public_url(final_url)
        declared_length = response.headers.get("Content-Length")
        try:
            declared_bytes = int(declared_length) if declared_length else 0
        except ValueError:
            declared_bytes = 0
        if declared_bytes > max_bytes:
            raise SourceSizeError("source exceeds the frozen download allowance")
        chunks, size = [], 0
        while chunk := response.read(min(65_536, max_bytes + 1 - size)):
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                raise SourceSizeError("source exceeds the frozen download allowance")
        body = b"".join(chunks)
        return Document(
            url=final_url,
            content_type=response.headers.get_content_type()
            + (
                f"; charset={response.headers.get_content_charset()}"
                if response.headers.get_content_charset()
                else ""
            ),
            body=body,
            fetched_at=now_iso(),
            publisher=urlsplit(final_url).hostname or "",
            publication_date=response.headers.get("Last-Modified", ""),
        )


def _response_dict(response: Any) -> dict[str, Any]:
    """Project an SDK response without changing its separately retained original."""
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return json.loads(response.json())


def _hits(response: Any) -> list[SearchHit]:
    """Keep exact URL order while filling information absent from earlier records."""
    payload = _response_dict(response)
    found: dict[str, SearchHit] = {}
    def merge(url, title, snippet):
        """Fill missing fields only, preserving conflicting earlier provider information."""
        if not url:
            return
        title, snippet = str(title or url), str(snippet or "")
        if url not in found:
            found[url] = SearchHit(hit_id(url), url, title, urlsplit(url).hostname or "", snippet)
        else:
            old = found[url]
            found[url] = replace(old, title=title if not old.title or old.title == url else old.title,
                                 snippet=old.snippet or snippet)
    for item in payload.get("output", []):
        for content in item.get("content", []) or []:
            snippet = str(content.get("text", ""))
            for annotation in content.get("annotations", []) or []:
                if annotation.get("type") != "url_citation":
                    continue
                url = str(annotation.get("url", ""))
                merge(url, annotation.get("title"), snippet)
        action = item.get("action") or {}
        for source in action.get("sources", []) or []:
            url = str(source.get("url", ""))
            merge(url, source.get("title"), source.get("snippet"))
    return list(found.values())
