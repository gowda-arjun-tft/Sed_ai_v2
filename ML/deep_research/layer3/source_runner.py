"""Bounded native source discovery with immediate persistence and independent recovery."""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

from langchain_core.runnables import RunnableLambda

from ML.deep_research.layer2.ML.context import InputSizeError
from ML.deep_research.layer2.ML.harness import build_model
from ML.deep_research.layer2.backend.fs import now_iso, storage_path, write_json
from ML.deep_research.layer2.backend.run_log import (
    DispatchLog, diagnostic_identifier, log_failure, operational_logger, stop_progress, waiting_progress,
)
from ML.deep_research.layer2.backend.usage import UsageCallback, summarize_usage
from .pipeline.create_run import local_path, require_current, verify_inputs
from .source_finder import prepare, recover, request_options, save_response
from .source_publication import publish


def _save(run: Path, record: dict) -> None:
    """Persist execution metadata and separately attributed provider token usage."""
    record.update(updated_at=now_iso(), usage=summarize_usage(run / "_internal/trace"))
    write_json(run / "run.json", record)


async def _batch(run, record, model, domains, logger, retry_failed):
    """Dispatch at most five independent jobs and save each yielded completion immediately."""
    inputs, configs, pending, starts = [], [], [], {}
    previous = dict(record["jobs"])
    for domain in domains:
        key = domain["key"]
        request, fingerprint, count, ceiling = prepare(
            run, record, domain, getattr(model, "profile", None) or {})
        entry, reused = recover(run, key, fingerprint, previous)
        entry.update(stage="source_finder", fingerprint=fingerprint, reused=reused,
                     updated_at=now_iso(), input_estimate=count, input_ceiling=ceiling)
        record["jobs"][key] = entry
        if reused:
            logger.info("job_reused stage=source_finder job=%s attempt=%s", key, entry["attempt"])
            continue
        if entry.get("status") == "failed" and not retry_failed:
            logger.info("job_skipped stage=source_finder job=%s reason=retry_not_requested", key)
            continue
        if count > ceiling:
            entry.update(status="failed", error_type="InputSizeError")
            log_failure(logger, "job_failed", InputSizeError("Mandatory input exceeds ceiling"),
                        stage="source_finder", job=key, input_estimate=count, ceiling=ceiling)
            continue
        attempt = entry.get("attempt", 0) + 1
        folder = run / "_internal/trace/responses" / key / fingerprint
        while (folder / f"{attempt:03d}").exists():
            attempt += 1
        # Discard old attempt attribution; its raw response and completion remain in history.
        entry = {"stage": "source_finder", "fingerprint": fingerprint, "attempt": attempt,
                 "status": "running", "error_type": "", "reused": False,
                 "request_id": str(uuid4()), "input_estimate": count, "input_ceiling": ceiling,
                 "response_path": f"_internal/trace/responses/{key}/{fingerprint}/{attempt:03d}/response.txt"}
        record["jobs"][key] = entry
        scheduled = time.perf_counter()
        inputs.append(request)
        configs.append({
            "run_id": uuid4(), "max_concurrency": record["max_concurrency"],
            "metadata": {"lc_agent_name": key},
            "callbacks": [UsageCallback(run / "_internal/trace", entry["request_id"]),
                          DispatchLog(logger, "source_finder", key, scheduled, starts)],
        })
        pending.append((key, scheduled))
        logger.info("job_scheduled stage=source_finder job=%s attempt=%d input_estimate=%d ceiling=%d",
                    key, attempt, count, ceiling)
    _save(run, record)
    if not pending:
        return
    outstanding = {key for key, _ in pending}
    progress = asyncio.create_task(waiting_progress(
        logger, "source_finder", outstanding, starts, time.perf_counter()))
    caller = model.bind(**request_options(record))
    workers = set()

    async def invoke(request, config):
        """Own in-flight calls so notebook interruption cannot leave duplicate local workers."""
        task = asyncio.current_task()
        workers.add(task)
        try:
            return await caller.ainvoke(request, config)
        finally:
            workers.discard(task)

    # Native batching does not cancel its children when its iterator is closed.
    completions = RunnableLambda(invoke).abatch_as_completed(inputs, configs, return_exceptions=True)
    try:
        async for index, result in completions:
            key, started = pending[index]
            entry = record["jobs"][key]
            outstanding.discard(key)
            try:
                if isinstance(result, BaseException):
                    raise result
                entry["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                save_response(run, entry, result)
                logger.info("response_saved stage=source_finder job=%s", key)
            except Exception as error:
                entry.update(status="failed", error_type=type(error).__name__)
                log_failure(logger, "job_failed", error, stage="source_finder", job=key,
                            attempt=entry["attempt"], request_id=entry["request_id"])
            entry["updated_at"] = now_iso()
            _save(run, record)
            logger.info("job_finished stage=source_finder job=%s status=%s elapsed_seconds=%.3f "
                        "web_actions=%s response_id=%s",
                        key, entry["status"], time.perf_counter() - started,
                        entry.get("web_actions", {}), diagnostic_identifier(entry.get("response_id")))
            if key in starts:
                logger.info("job_timing job=%s queued_seconds=%.3f dispatch_to_handled_seconds=%.3f",
                            key, starts[key] - started, time.perf_counter() - starts[key])
    finally:
        await completions.aclose()
        active = list(workers)
        for worker in active:
            worker.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        await stop_progress(progress)


async def run_sources(run_dir: Path, *, retry_failed: bool = False) -> None:
    """Execute source discovery only; historical runs and frozen inputs are checked before writes."""
    run = storage_path(run_dir)
    record = require_current(run)
    verify_inputs(run, record)
    started = time.perf_counter()
    with operational_logger(run) as logger:
        logger.info("run_started layer=3 stage=source_finder domains=%d", len(record["domains"]))
        record["status"] = "running"
        _save(run, record)
        try:
            model = build_model(record["reasoning_effort"])
            model.max_retries = record["provider_max_retries"]
            model.request_timeout = record["timeout_seconds"]
            size = record["max_concurrency"]
            for offset in range(0, len(record["domains"]), size):
                await _batch(run, record, model, record["domains"][offset:offset + size],
                             logger, retry_failed)
            complete = sum(j.get("status") == "complete" for j in record["jobs"].values())
            record["status"] = ("complete" if complete == len(record["domains"])
                                else "partial" if complete else "failed")
        except asyncio.CancelledError:
            record["status"] = "interrupted"
            logger.warning("run_interrupted stage=source_finder")
            raise
        except Exception as error:
            record["status"] = "failed"
            log_failure(logger, "run_failed", error, stage="source_finder")
            raise
        finally:
            _save(run, record)
            publication_started = time.perf_counter()
            try:
                record["publication"] = publish(run)
                logger.info("publication_finished elapsed_seconds=%.3f",
                            time.perf_counter() - publication_started)
            except Exception as error:
                record["status"] = "failed"
                log_failure(logger, "publication_failed", error, stage="source_finder")
                raise
            finally:
                record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                _save(run, record)
                logger.info("run_finished status=%s completed=%d reused=%d failed=%d elapsed_seconds=%.3f",
                            record["status"],
                            sum(j.get("status") == "complete" for j in record["jobs"].values()),
                            sum(j.get("reused", False) for j in record["jobs"].values()),
                            sum(j.get("status") == "failed" for j in record["jobs"].values()),
                            record["elapsed_seconds"])
