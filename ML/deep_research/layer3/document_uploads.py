"""Sequential, resumable document ingestion following source discovery; no model calls."""

import asyncio
import os
import time
from contextlib import contextmanager
from pathlib import Path

from openai import AsyncOpenAI

from ML.deep_research.layer2.backend.fs import load_json, now_iso, storage_path, text_hash, write_json
from ML.deep_research.layer2.backend.jobs import saved_text
from ML.deep_research.layer2.backend.run_log import log_failure, operational_logger
from .document_download import download_document
from .document_files import failure, reconcile, upload, verify_existing
from .document_records import REGISTRY_PATH, UPLOAD_POLICY, candidate, source_entries
from .pipeline.create_run import local_path, require_current, verify_inputs
from .source_publication import parse_json, publish


@contextmanager
def run_writer(run):
    """Hold one OS-released writer lock across public discovery/upload entrypoints."""
    path = run / "_internal/trace/writer.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("This Layer 3 run already has an active writer") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def collect(run, record):
    """Read preserved completed responses once, returning candidate URLs and source versions."""
    urls, versions, issues = {}, {}, []
    for domain in record["domains"]:
        job = record["jobs"].get(domain["key"], {})
        if job.get("status") != "complete" or not job.get("response_path"):
            continue
        raw = saved_text(local_path(run, job["response_path"]))
        if raw is None or text_hash(raw) != job.get("response_sha256"):
            raise ValueError("Saved source response changed or is missing; restore it before uploading")
        version = f"{domain['key']}:{text_hash(raw)}"
        versions[version] = job["response_path"]
        try:
            entries = list(source_entries(parse_json(raw)))
        except (ValueError, RecursionError):
            entries = []
        if not entries:
            issues.append({"source": version, "reason": "no_interpretable_source_entries"})
        for location, entry, ambiguous in entries:
            url, reason = candidate(entry, ambiguous)
            if reason:
                issues.append({"source": version, "entry": location, "reason": reason})
            if url:
                urls.setdefault(url, []).append({"source": version, "entry": location})
    return urls, versions, issues


async def _reuse(item, registry, client, logger, persist, checked, retry_failed):
    """Resolve a known hash once per pass; return whether no create request should follow."""
    digest = item.get("sha256")
    entry = registry["files"].get(digest)
    if not entry:
        return False
    if digest not in checked:
        checked.add(digest)
        try:
            if entry["status"] in {"complete", "unavailable"}:
                await verify_existing(client, entry)
            elif entry["status"] in {"intent", "uncertain"}:
                await reconcile(client, entry, digest)
        except Exception as error:
            entry.update(status="unavailable" if entry.get("file_id") else "uncertain",
                         error=failure(error))
            raise
        finally:
            persist()
    if entry["status"] == "pending" or (entry["status"] == "rejected" and retry_failed):
        return False
    item["status"] = entry["status"]
    logger.info("document_reuse_checked content_id=%s status=%s", digest[:12], entry["status"])
    return True


async def _process(url, registry, client, policy, logger, persist, checked, retry_failed):
    """Reuse a known upload or fetch/hash/upload one document, preserving every prior receipt."""
    item = registry["urls"].setdefault(url, {"status": "pending"})
    if item.get("status") == "failed" and not retry_failed and not item.get("sha256"):
        return
    if await _reuse(item, registry, client, logger, persist, checked, retry_failed):
        return
    async with download_document(url, policy, logger) as (handle, info):
        digest = info["sha256"]
        item.update(info, fetched_at=now_iso(), status="downloaded")
        if await _reuse(item, registry, client, logger, persist, checked, retry_failed):
            return
        entry = registry["files"].get(digest)
        if entry is None:
            entry = {"filename": f"l3-{registry['run_identity']}-{digest}{info['extension']}",
                     "bytes": info["bytes"], "status": "pending", "attempts": []}
            registry["files"][digest] = entry
        persist()
        await upload(client, handle, entry, persist)
        checked.add(digest)
        item["status"] = "complete"
        logger.info("document_uploaded content_id=%s bytes=%d", digest[:12], info["bytes"])


async def _run_uploads(run, *, retry_failed=False):
    """Execute under the caller's writer lock; preserve source-job status and raw bytes."""
    record = require_current(run)
    verify_inputs(run, record)
    urls, versions, issues = collect(run, record)
    policy = record.get("document_uploads", {}).get("policy", UPLOAD_POLICY)
    if policy != UPLOAD_POLICY:
        raise ValueError("Unsupported frozen document upload policy")
    path = run / REGISTRY_PATH
    registry = load_json(path) if path.exists() else {
        "version": 1, "run_identity": text_hash(str(run.resolve()))[:16],
        "policy": dict(policy), "urls": {}, "files": {}, "source_versions": {},
    }
    if registry["policy"] != policy:
        raise ValueError("Document upload registry policy changed")
    registry["source_versions"].update(versions)
    registry.update(active_sources=list(versions), issues=issues, status="running")
    for url, references in urls.items():
        registry["urls"].setdefault(url, {"status": "pending"})["references"] = references
    started = time.perf_counter()

    def persist():
        """Atomically persist the single authoritative registry before any derived view."""
        registry["updated_at"] = now_iso()
        write_json(path, registry)

    record.setdefault("document_uploads", {"policy": dict(policy)})["status"] = "running"
    record.setdefault("discovery_status", record["status"])
    persist()
    write_json(run / "run.json", record)
    with operational_logger(run) as logger:
        logger.info("uploads_started candidate_entries=%d unique_urls=%d",
                    sum(len(v) for v in urls.values()), len(urls))
        try:
            checked = set()
            async with AsyncOpenAI(timeout=120, max_retries=policy["read_retries"]) as client:
                for index, url in enumerate(urls, 1):
                    began = time.perf_counter()
                    logger.info("document_started index=%d total=%d", index, len(urls))
                    try:
                        await _process(url, registry, client, policy, logger, persist, checked, retry_failed)
                    except Exception as error:
                        registry["urls"][url].update(status="failed", error=failure(error))
                        log_failure(logger, "document_failed", error, index=index,
                                    http_status=failure(error).get("http_status"))
                    persist()
                    logger.info("document_finished index=%d status=%s elapsed_seconds=%.3f",
                                index, registry["urls"][url]["status"], time.perf_counter() - began)
            registry["status"] = "complete" if all(
                registry["urls"][url]["status"] == "complete" for url in urls) else "partial"
        except asyncio.CancelledError:
            registry["status"] = "interrupted"
            raise
        except Exception as error:
            registry["status"] = "failed"
            log_failure(logger, "uploads_failed", error)
            raise
        finally:
            registry["counts"] = {
                "candidate_entries": sum(len(v) for v in urls.values()), "unique_urls": len(urls),
                "uploaded_files": sum(f["status"] == "complete" for f in registry["files"].values()),
                "failed_urls": sum(registry["urls"][u]["status"] != "complete" for u in urls),
                "observations": len(issues),
            }
            registry["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            persist()
            record["document_uploads"].update(status=registry["status"], counts=registry["counts"])
            record["status"] = record["discovery_status"]
            record["updated_at"] = now_iso()
            write_json(run / "run.json", record)
            try:
                record["publication"] = publish(run)
            except Exception as error:
                record["status"] = "failed"
                log_failure(logger, "publication_failed", error, stage="document_uploads")
                raise
            finally:
                record["document_uploads"]["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                write_json(run / "run.json", record)
                logger.info("uploads_finished status=%s counts=%s elapsed_seconds=%.3f",
                            registry["status"], registry["counts"], record["document_uploads"]["elapsed_seconds"])


async def upload_documents(run_dir: Path, *, retry_failed: bool = False) -> None:
    """Explicit upload-only entrypoint; never schedules discovery or any model call."""
    run = storage_path(run_dir)
    record = require_current(run)
    verify_inputs(run, record)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is empty; configure runtime credentials before uploading")
    with run_writer(run):
        await _run_uploads(run, retry_failed=retry_failed)
