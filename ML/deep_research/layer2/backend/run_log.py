"""One append-only operational log for a Layer 2 run."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


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
