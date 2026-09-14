from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.parse import urlsplit

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
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str) -> Document:
    validate_public_url(url)
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
        if declared_bytes > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds the 10 MiB download limit")
        body = response.read(MAX_SOURCE_BYTES + 1)
        if len(body) > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds the 10 MiB download limit")
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
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return json.loads(response.json())


def _hits(response: Any) -> list[SearchHit]:
    payload = _response_dict(response)
    found: dict[str, SearchHit] = {}
    for item in payload.get("output", []):
        for content in item.get("content", []) or []:
            snippet = str(content.get("text", ""))
            for annotation in content.get("annotations", []) or []:
                if annotation.get("type") != "url_citation":
                    continue
                url = str(annotation.get("url", ""))
                if url and url not in found:
                    found[url] = SearchHit(
                        hit_id=hit_id(url),
                        url=url,
                        title=str(annotation.get("title", url)),
                        publisher=urlsplit(url).hostname or "",
                        snippet=snippet,
                    )
        action = item.get("action") or {}
        for source in action.get("sources", []) or []:
            url = str(source.get("url", ""))
            if url and url not in found:
                found[url] = SearchHit(
                    hit_id=hit_id(url),
                    url=url,
                    title=str(source.get("title") or url),
                    publisher=urlsplit(url).hostname or "",
                    snippet=str(source.get("snippet") or ""),
                )
    return list(found.values())
