"""Schema-9 direct workflow; file snapshots and stable IDs preserve routing and recovery."""

import asyncio
import json
import os
import time
from itertools import islice
from pathlib import Path
from uuid import uuid4

from ..ML.harness import build_model
from .create_run import require_current
from .fs import load_json, now_iso, sha256, storage_path, write_json
from .jobs import run_jobs, saved_text
from .publication import domain_definitions, publish
from .run_log import log_failure, operational_logger, stage_log
from .usage import summarize_usage


class UnusableDomainPlanError(ValueError):
    """No usable domain identities exist for distribution; the completed raw plan remains reusable."""


def source_sections(run: Path, window: dict) -> dict[str, str]:
    """Input a frozen source range; seek its exact UTF-8 overlap/new text without loading the corpus."""
    start, boundary, end = (window[key] for key in ("start_byte", "new_start_byte", "end_byte"))
    with (run / "_internal/inputs/fact_sheet.md").open("rb") as handle:
        handle.seek(start + window["input_bom_bytes"])
        raw = handle.read(end - start)
    if len(raw) != end - start:
        raise OSError("incomplete frozen source range")
    return {"overlap_context": raw[:boundary - start].decode("utf-8"),
            "new_content": raw[boundary - start:].decode("utf-8")}


def verify_inputs(run: Path, record: dict) -> None:
    """Input run metadata; reject changed frozen inputs before logging, writing or dispatch."""
    for name, info in record["inputs"].items():
        if sha256(run / "_internal/inputs" / name) != info["sha256"]:
            raise OSError("frozen input hash changed; create a new run")
    if sha256(run / "_internal/trace/source/manifest.json") != record["source_manifest_sha256"]:
        raise OSError("frozen source manifest changed; create a new run")


async def execute(run: Path, previous: dict, logger) -> None:
    """Input a validated run; build metadata sequentially, decide once, then distribute in bounded batches."""
    record = load_json(run / "run.json")
    model = build_model(record["reasoning_effort"])
    windows = load_json(run / "_internal/trace/source/manifest.json")
    metadata = ""
    with stage_log(run, logger, "metadata", len(windows)):
        for index, window in enumerate(windows):
            result = await run_jobs(run, model, "metadata", [
                {"previous_metadata": metadata, **source_sections(run, window)}
            ], previous, logger, offset=index)
            if not result:
                return
            metadata = saved_text(result[0])
    with stage_log(run, logger, "design", 1):
        result = await run_jobs(run, model, "design", [{
            "asset_metadata": metadata,
            "domain_plugin": saved_text(run / "_internal/inputs/domain_plugin.md"),
            "requirements": saved_text(run / "_internal/inputs/requirements.md"),
        }], previous, logger)
        if not result:
            return
        plan = saved_text(result[0])
        definitions, _ = domain_definitions(plan, result[0].relative_to(run).as_posix())
        if not definitions:
            raise UnusableDomainPlanError("saved domain plan has no usable routing identities")
        plan = json.dumps({"domains": [{"domain_id": identifier, **definition}
                                       for identifier, definition in definitions.items()]}, ensure_ascii=False)
    with stage_log(run, logger, "distribution", len(windows)):
        iterator, offset = iter(windows), 0
        while batch := list(islice(iterator, record["chunking"]["max_concurrency"] * 2)):
            await run_jobs(run, model, "distribution", [
                {"asset_metadata": metadata, "domain_plan": plan, **source_sections(run, window)}
                for window in batch
            ], previous, logger, offset=offset)
            offset += len(batch)


def run_all(run_dir: Path) -> dict:
    """Input a schema-9 run; execute/resume direct calls and publish available current-version Markdown."""
    started = time.perf_counter()
    run = storage_path(run_dir)
    record = require_current(run)
    verify_inputs(run, record)
    if record.get("public_input_confirmed") is not True:
        raise ValueError("Layer 2 web-assisted design requires frozen public-input confirmation")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is empty")
    if record["chunking"]["max_concurrency"] < 1:
        raise ValueError("max_concurrency must be positive")
    previous = record["jobs"]
    write_json(run / "_internal/trace/history" / uuid4().hex / "run.json", record)
    record.update(jobs={}, status="running", current_stage="metadata", error_type="")
    write_json(run / "run.json", record)
    failure = None
    with operational_logger(run) as logger:
        logger.info("run_%s run_id=%s", "resumed" if previous else "started", record["run_id"])
        logger.info("frozen_policy chunking=%s context=%s", record["chunking"], record["context_policy"])
        logger.info("retry_policy provider_transport_retries=%d observed_transport_attempts=unavailable",
                    record["provider_max_retries"])
        try:
            asyncio.run(execute(run, previous, logger))
        except Exception as exc:
            failure = exc
            log_failure(logger, "run_failed", exc)
        finally:
            record = load_json(run / "run.json")
            done = sum(job["status"] == "complete" for job in record["jobs"].values())
            expected = record["source_windows"] * 2 + 1
            distributed = any(job["status"] == "complete" and job["stage"] == "distribution"
                              for job in record["jobs"].values())
            status = "complete" if done == expected and not failure else "partial" if distributed else "failed"
            record.update(status=status, usage=summarize_usage(run / "_internal/trace"),
                          finished_at=now_iso(), error_type=type(failure).__name__ if failure else "")
            write_json(run / "run.json", record)
            publication_started = time.perf_counter()
            try:
                logger.info("publication_started")
                record["publication"] = publish(run)
                logger.info("publication_complete domains=%d routing_issues=%d",
                            record["publication"]["domain_count"], record["publication"]["routing_issues"])
                if record["publication"]["routing_issues"]:
                    logger.warning("publication_observations count=%d details=_internal/trace/routing_issues.json",
                                   record["publication"]["routing_issues"])
            except Exception as exc:
                failure = failure or exc
                record.update(status="failed", error_type=type(failure).__name__)
                log_failure(logger, "publication_failed", exc)
            logger.info("publication_finished wall_seconds=%.3f", time.perf_counter() - publication_started)
            record["finished_at"] = now_iso()
            write_json(run / "run.json", record)
            logger.info("run_%s completed_jobs=%d expected_jobs=%d reused_jobs=%d wall_seconds=%.3f",
                        record["status"], done, expected,
                        sum(job.get("reused", False) for job in record["jobs"].values()), time.perf_counter() - started)
    if failure:
        raise failure
    return record["usage"]
