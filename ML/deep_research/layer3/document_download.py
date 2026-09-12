"""Bounded public document downloads; no extraction, cookies, credentials or persistent copy."""

import asyncio
import hashlib
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from tempfile import TemporaryFile
from urllib.parse import urljoin, urlsplit

import httpx

from ML.deep_research.layer2.backend.run_log import log_failure
from .retrieval import validate_public_url


def document_extension(handle, content_type, url):
    """Check transport representation, rejecting HTML/error pages and unsupported binaries."""
    handle.seek(0)
    head = handle.read(4096)
    handle.seek(0)
    mime = content_type.split(";", 1)[0].strip().lower()
    probe = head.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
    if mime in {"text/html", "application/xhtml+xml"} or any(
        marker in probe for marker in (b"<!doctype html", b"<html", b"<body", b"<head")
    ):
        raise ValueError("html_not_document")
    if head.startswith(b"%PDF-"):
        return ".pdf"
    if head.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(handle) as archive:
            names = archive.namelist()
        handle.seek(0)
        for prefix, extension in (("word/", ".docx"), ("xl/", ".xlsx"), ("ppt/", ".pptx")):
            if any(name.startswith(prefix) for name in names):
                return extension
        raise ValueError("unsupported_archive")
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") and suffix in {".doc", ".xls", ".ppt"}:
        return suffix
    if probe.startswith(b"{\\rtf"):
        return ".rtf"
    if suffix in {".txt", ".md", ".csv", ".tsv"} and mime in {
        "text/plain", "text/markdown", "text/csv", "text/tab-separated-values", "application/octet-stream"
    } and b"\x00" not in head:
        return suffix
    raise ValueError("unsupported_document_representation")


async def _download(client, url, handle, maximum):
    """Validate every redirect and stream at most the frozen byte limit into a temporary file."""
    for _ in range(11):
        try:
            await asyncio.to_thread(validate_public_url, url)
        except ValueError as error:
            raise ValueError("unsafe_or_unresolvable_document_url") from error
        client.cookies.clear()
        async with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("redirect_without_location")
                url = urljoin(url, location)
                continue
            response.raise_for_status()
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > maximum:
                raise ValueError("document_exceeds_upload_limit")
            digest, size = hashlib.sha256(), 0
            async for chunk in response.aiter_bytes(64 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise ValueError("document_exceeds_upload_limit")
                handle.write(chunk)
                digest.update(chunk)
            if not size:
                raise ValueError("empty_document")
            extension = document_extension(handle, response.headers.get("content-type", ""), url)
            handle.seek(0)
            return {"sha256": digest.hexdigest(), "bytes": size, "extension": extension,
                    "final_url": url, "content_type": response.headers.get("content-type", "")}
    raise ValueError("too_many_redirects")


@asynccontextmanager
async def download_document(url, policy, logger):
    """Yield a verified document and close/delete its temporary bytes even on interruption."""
    with TemporaryFile("w+b") as handle:
        # No environment proxies/cookies: the application only fetches validated public URLs.
        async with httpx.AsyncClient(timeout=30, trust_env=False, headers={
            "User-Agent": "CDI-Deep-Research/1.0", "Accept-Encoding": "identity",
        }) as client:
            for attempt in range(1, policy["download_attempts"] + 1):
                started = time.perf_counter()
                try:
                    info = await _download(client, url, handle, policy["max_bytes"])
                    logger.info("document_downloaded attempt=%d bytes=%d elapsed_seconds=%.3f",
                                attempt, info["bytes"], time.perf_counter() - started)
                    break
                except (httpx.TransportError, httpx.HTTPStatusError) as error:
                    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                    retry = status is None or status in {408, 429} or status >= 500
                    if not retry or attempt == policy["download_attempts"]:
                        raise
                    delay = 0.25 * 2 ** (attempt - 1)
                    log_failure(logger, "download_attempt_failed", error, attempt=attempt, http_status=status)
                    logger.warning("download_retry attempt=%d backoff_seconds=%.2f", attempt, delay)
                    handle.seek(0)
                    handle.truncate()
                    await asyncio.sleep(delay)
        yield handle, info
