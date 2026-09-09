"""One append-only operational log for a Layer 2 run."""

from __future__ import annotations

import logging
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def log_failure(logger, event, exc, **context):
    """Input an exception and trusted identifiers; log safe frames, never values or source lines."""
    frames = [{"file": frame.filename, "line": frame.lineno, "function": frame.name}
              for frame in traceback.extract_tb(exc.__traceback__)]
    logger.error("%s context=%s error_type=%s sqlite_code=%s sqlite_name=%s frames=%s",
                 event, context, type(exc).__name__, getattr(exc, "sqlite_errorcode", None),
                 getattr(exc, "sqlite_errorname", None), frames)


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
