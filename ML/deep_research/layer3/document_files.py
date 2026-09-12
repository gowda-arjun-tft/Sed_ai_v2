"""Files API receipts and conservative recovery of uploads with uncertain acceptance."""

import hashlib

import httpx
from openai import APIStatusError

from ML.deep_research.layer2.backend.fs import now_iso
from ML.deep_research.layer2.backend.run_log import diagnostic_identifier


def failure(error):
    """Record only safe operational identifiers, never arbitrary provider payloads."""
    result = {"error_type": type(error).__name__, "at": now_iso()}
    if isinstance(error, APIStatusError):
        result.update(http_status=error.status_code, code=diagnostic_identifier(error.code),
                      request_id=diagnostic_identifier(error.request_id))
    elif isinstance(error, httpx.HTTPStatusError):
        result["http_status"] = error.response.status_code
    elif isinstance(error, ValueError) and str(error) in {
        "html_not_document", "unsupported_archive", "unsupported_document_representation",
        "document_exceeds_upload_limit", "empty_document", "too_many_redirects",
        "redirect_without_location",
        "unsafe_or_unresolvable_document_url",
    }:
        result["reason"] = str(error)
    return result


def accepted(receipt, expected):
    """Check the operational upload receipt, not document contents or model quality."""
    return (isinstance(receipt.id, str) and receipt.id.startswith("file-")
            and receipt.filename == expected["filename"] and receipt.bytes == expected["bytes"]
            and receipt.purpose == "user_data")


def remember(receipt, entry):
    """Keep the full successful Files receipt and immediately reusable identity."""
    entry.update(status="complete", file_id=receipt.id, verified_at=now_iso(),
                 receipt=receipt.model_dump(mode="json"))
    entry.pop("error", None)


async def verify_existing(client, entry):
    """Verify a stored ID still refers to the expected project-scoped file before reuse."""
    receipt = await client.files.retrieve(entry["file_id"])
    if not accepted(receipt, entry):
        raise ValueError("Stored Files receipt no longer matches")
    remember(receipt, entry)


async def reconcile(client, entry, digest):
    """Find the exact upload intent and verify remote bytes; never resend an uncertain create."""
    matches = []
    async for receipt in client.files.list(purpose="user_data", limit=100):
        if accepted(receipt, entry):
            matches.append(receipt)
    if len(matches) != 1:
        entry.update(status="uncertain", recovery_reason="no_unique_remote_receipt")
        return
    receipt = matches[0]
    remote_hash, size = hashlib.sha256(), 0
    async with client.files.with_streaming_response.content(receipt.id) as response:
        async for chunk in response.iter_bytes(chunk_size=64 * 1024):
            size += len(chunk)
            if size > entry["bytes"]:
                break
            remote_hash.update(chunk)
    if size != entry["bytes"] or remote_hash.hexdigest() != digest:
        entry.update(status="uncertain", recovery_reason="remote_bytes_mismatch")
        return
    remember(receipt, entry)


async def upload(client, handle, entry, persist):
    """Persist intent before the single create request and receipt before returning to callers."""
    attempt = {"started_at": now_iso(), "status": "intent"}
    entry.setdefault("attempts", []).append(attempt)
    entry["status"] = "intent"
    persist()
    try:
        # A timed-out POST can already have succeeded. Never let SDK transport retries duplicate it.
        receipt = await client.with_options(max_retries=0).files.create(
            file=(entry["filename"], handle), purpose="user_data")
        if not accepted(receipt, entry):
            raise ValueError("Upload receipt could not be confirmed")
        remember(receipt, entry)
        attempt.update(status="complete", finished_at=now_iso())
    except Exception as error:
        definite = isinstance(error, APIStatusError) and 400 <= error.status_code < 500 and error.status_code not in {408, 409}
        entry.update(status="rejected" if definite else "uncertain", error=failure(error))
        attempt.update(status=entry["status"], finished_at=now_iso(), error=failure(error))
        raise
    finally:
        persist()
