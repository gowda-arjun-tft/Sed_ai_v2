"""One append-only operational log for a Layer 2 run."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import traceback
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Iterator

from openai import APIStatusError
from langchain_core.callbacks import BaseCallbackHandler


class DispatchLog(BaseCallbackHandler):
    """Observe native dispatch without changing the model scheduler or logging its messages."""

    run_inline = True

    def __init__(self, logger, stage, job, scheduled, starts):
        """Input trusted job context and a shared dispatch clock map."""
        self.logger, self.stage, self.job = logger, stage, job
        self.scheduled, self.starts = scheduled, starts

    def on_chat_model_start(self, serialized, messages, **kwargs):
        """Record local queue time when the native model actually starts, ignoring payloads."""
        started = time.perf_counter()
        self.starts[self.job] = started
        self.logger.info("job_dispatched stage=%s job=%s queued_seconds=%.3f",
                         self.stage, self.job, started - self.scheduled)


async def waiting_progress(logger, stage, pending, starts, started):
    """Report outstanding bounded-batch jobs every 30 seconds, without claiming model progress."""
    while True:
        await asyncio.sleep(30)
        if pending:
            active = sorted(pending & starts.keys())
            queued = sorted(pending - starts.keys())
            logger.info("waiting_for_provider stage=%s pending=%s queued=%s batch_elapsed_seconds=%.3f",
                        stage, active, queued, time.perf_counter() - started)


async def stop_progress(task):
    """Cancel and join the single batch progress task, including on caller cancellation."""
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@contextmanager
def stage_log(run, logger, stage, expected):
    """Record wall-clock stage duration and observed outcomes, including interrupted work."""
    from .fs import load_json

    started = time.perf_counter()
    logger.info("stage_started stage=%s expected_jobs=%d", stage, expected)
    try:
        yield
    finally:
        jobs = [job for job in load_json(run / "run.json")["jobs"].values() if job["stage"] == stage]
        complete = sum(job["status"] == "complete" for job in jobs)
        failed = sum(job["status"] == "failed" for job in jobs)
        logger.info("stage_finished stage=%s completed=%d reused=%d failed=%d outstanding=%d wall_seconds=%.3f",
                    stage, complete, sum(job.get("reused", False) for job in jobs), failed,
                    expected - complete - failed, time.perf_counter() - started)


def diagnostic_identifier(value):
    """Input a provider diagnostic identifier; return bounded log-safe text, never arbitrary payloads."""
    if value is None:
        return None
    if (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,128}", value)
            and not value.lower().startswith(("sk-", "sk_", "bearer"))):
        return value
    return "[redacted]"


def log_failure(logger, event, exc, **context):
    """Input an exception and trusted identifiers; log safe frames, never values or source lines."""
    frames = [{"file": frame.filename, "line": frame.lineno, "function": frame.name}
              for frame in traceback.extract_tb(exc.__traceback__)]
    if isinstance(exc, APIStatusError):
        context = {**context, "http_status": exc.status_code,
                   "provider_code": diagnostic_identifier(exc.code),
                   "provider_parameter": diagnostic_identifier(exc.param),
                   "provider_request_id": diagnostic_identifier(exc.request_id)}
        if (isinstance(exc.body, dict)
                and exc.body.get("message") == "Web Search cannot be used with JSON mode."):
            context["diagnostic"] = "web_search_incompatible_with_json_mode"
    logger.error("%s context=%s error_type=%s frames=%s", event, context, type(exc).__name__, frames)


@contextmanager
def operational_logger(run_dir: Path) -> Iterator[logging.Logger]:
    """Input a run path; yield its UTF-8 logger and close the handler after execution."""
    path = (run_dir / "run.log").resolve()
    logger = logging.getLogger(f"cdi.layer2.{path}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)sZ %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S"
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    try:
        yield logger
    finally:
        logger.removeHandler(handler)
        handler.close()
