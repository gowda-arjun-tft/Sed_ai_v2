"""Schema-6 six-stage execution over disk evidence and bounded jobs."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..ML.agent import Layer2Response
from ..ML.context import dump
from .create_run import require_current
from .evidence import EvidenceStore
from .fs import load_json, now_iso, read_text, sha256, write_json, storage_path
from .projections import audit, load_ledger, write_arrays
from .publish import publish
from .run_log import log_failure, operational_logger
from .stages import assign, distribute, plan_domains, review, understand
from .usage import summarize_usage


async def execute(run: Path, logger) -> dict:
    """Input a schema-6 run; execute finite phase jobs and publish every available result."""
    record = require_current(run)
    for name, info in record["inputs"].items():
        if sha256(run / "_internal/inputs" / name) != info["sha256"]:
            raise OSError("frozen input hash changed; create a new run")
    if sha256(run / "_internal/trace/source/manifest.json") != record["source_manifest_sha256"]:
        raise OSError("frozen source manifest changed; create a new run")
    record["execution_id"] = uuid4().hex
    write_json(run / "run.json", record)
    store = EvidenceStore(run)
    load_ledger(store)
    store.clear("understanding", "needs_owners", "domains", "initial_domains", "dispositions", "comparisons")
    with store.connect() as db:
        db.execute("DELETE FROM paths")
        db.commit()
        # ponytail: retain this idle connection during tool execution to avoid last-close
        # WAL cleanup racing new reads. No held transaction, global lock or shared cursor.
        instructions = {name: read_text(run / "_internal/inputs" / f"{name}.md")
                        for name in ("domain_plugin", "requirements")}
        async with aiosqlite.connect(str(run / "_internal/trace/checkpoints.sqlite3")) as connection:
            saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[Layer2Response]))
            await understand(store, saver, logger)
            # Instructions enter only after independent original-source understanding.
            for label, text in instructions.items():
                store.add_text(label, text)
            await plan_domains(store, "design", store.rows("understanding"), instructions, saver, logger)
            for domain in store.rows("domains"):
                store.put("initial_domains", domain["domain_id"], domain)
            write_arrays(run / "_internal/domains.json", initial=store.rows("initial_domains"), final=[])
            await distribute(store, saver, logger)
            await review(store, instructions, saver, logger)
            await plan_domains(store, "catalogue", store.rows("observations"), instructions, saver, logger)
            await assign(store, saver, logger)
    latest = load_json(run / "run.json")
    for key in list(latest["jobs"]):
        entry = latest["jobs"][key]
        if entry.get("execution_id") != record["execution_id"]:
            write_json(run / "_internal/trace/responses" / key / entry["fingerprint"] / "job.json", entry)
            del latest["jobs"][key]
        elif entry["status"] == "failed":
            audit(store, "operational_failure", job=key, error_type=entry["error_type"])
    write_json(run / "run.json", latest)
    coverage = publish(store)
    logger.info("published domains=%d recorded_facts=%d unresolved_facts=%d",
                coverage["domain_count"], coverage["recorded_facts"], coverage["unresolved_facts"])
    return coverage


def run_all(run_dir: Path) -> dict:
    """Input a schema-6 run; synchronously execute/resume and return provider-reported usage."""
    run_dir = storage_path(run_dir)
    record = require_current(run_dir)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is empty")
    with operational_logger(run_dir) as logger:
        logger.info("run_%s run_id=%s", "started" if record["status"] == "started" else "resumed",
                    record["run_id"])
        logger.info("frozen_policy chunking=%s context=%s", dump(record["chunking"]), dump(record["context_policy"]))
        try:
            coverage = asyncio.run(execute(run_dir, logger))
        except Exception as exc:
            record = load_json(run_dir / "run.json")
            record.update(status="failed", error_type=type(exc).__name__, updated_at=now_iso())
            write_json(run_dir / "run.json", record)
            log_failure(logger, "run_failed", exc, stage=record.get("current_stage"))
            raise
        record = load_json(run_dir / "run.json")
        failed = sum(job["status"] == "failed" for job in record["jobs"].values())
        usage = summarize_usage(run_dir / "_internal/trace")
        record.update(status="partial" if failed else "complete", current_stage=None,
                      coverage=coverage, usage=usage, finished_at=now_iso(), error_type="")
        write_json(run_dir / "run.json", record)
        logger.info("run_%s failed_jobs=%d", record["status"], failed)
        return usage
