"""Native read-only filesystem tools over registered evidence, never a host mount."""

import logging
import sqlite3
import time
from contextlib import closing
from functools import wraps
from pathlib import PurePosixPath

from deepagents.backends.protocol import BackendProtocol, GlobResult, GrepResult, LsResult, ReadResult
from deepagents.backends.utils import create_file_data, slice_read_response
from langgraph.config import get_config
from wcmatch import glob as wcglob

from ..backend.evidence import EvidenceStore
from ..backend.run_log import log_failure


def recover_read(operation):
    """Input a native read method; retry transient database failures before returning any result."""
    @wraps(operation)
    def invoke(self, *args, **kwargs):
        """Input native tool arguments; return a complete result or propagate a bounded read failure."""
        logger = logging.getLogger(f"cdi.layer2.{(self.store.run / 'run.log').resolve()}")
        try:
            config = get_config().get("configurable", {})
        except RuntimeError:
            config = {}
        context = {"database": "_internal/trace/evidence.sqlite3",
                   "operation": "read_file" if operation.__name__ == "read" else operation.__name__,
                   "stage": config.get("stage"), "job": config.get("job"),
                   "thread": self.thread or config.get("thread_id")}
        start = time.perf_counter()
        if self.history_only:
            # Index writes are not retried as part of a model-visible read.
            try:
                self.store.index_history(self.scope()[1])
            except Exception as exc:
                log_failure(logger, "sqlite_history_index_failed", exc, **context,
                            phase="history_index", elapsed=time.perf_counter() - start)
                raise
        for attempt in range(1, 4):
            try:
                result = operation(self, *args, **kwargs)
            except sqlite3.Error as exc:
                code = getattr(exc, "sqlite_errorcode", None)
                retryable = isinstance(code, int) and code & 255 in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_PROTOCOL}
                if not retryable or attempt == 3:
                    log_failure(logger, "sqlite_read_failed", exc, **context, attempt=attempt,
                                elapsed=time.perf_counter() - start, exhausted=retryable)
                    raise
                delay = 0.25 * attempt
                logger.warning("sqlite_read_retry context=%s attempt=%d elapsed=%.3f backoff=%.2f "
                               "sqlite_code=%s sqlite_name=%s", context, attempt,
                               time.perf_counter() - start, delay, code, getattr(exc, "sqlite_errorname", None))
                time.sleep(delay)
            else:
                if attempt > 1:
                    logger.info("sqlite_read_recovered context=%s attempt=%d elapsed=%.3f",
                                context, attempt, time.perf_counter() - start)
                return result
    return invoke


class EvidenceBackend(BackendProtocol):
    """Read indexed evidence or session history through the pinned native tool protocol."""

    def __init__(self, run, *, history=False, version=None, thread=None):
        """Input run and optional offline scope; retain no corpus or mutable invocation state."""
        self.store = EvidenceStore(run)
        self.history_only, self.version, self.thread = history, version, thread

    def scope(self):
        """Input none; resolve the frozen evidence version and thread from application config."""
        try:
            config = get_config().get("configurable", {})
        except RuntimeError:
            config = {}
        return self.version or config.get("evidence_version", ""), self.thread or config.get("thread_id", "")

    def valid(self, path):
        """Input model path; accept virtual absolute names without traversal or Windows paths."""
        return isinstance(path, str) and path.startswith("/") and not any(
            part == ".." for part in PurePosixPath(path).parts
        ) and "\\" not in path and ":" not in path and "\0" not in path

    def documents(self, prefix="/"):
        """Input virtual prefix; stream the invocation's approved evidence or history."""
        version, thread = self.scope()
        if self.history_only:
            yield from self.store.history(thread, prefix)
        else:
            yield from self.store.documents(version, prefix)

    @recover_read
    def read(self, file_path, offset=0, limit=2000):
        """Input virtual file and line window; return exact text using native pagination."""
        if not self.valid(file_path):
            return ReadResult(error="Invalid virtual path")
        version, _ = self.scope()
        if self.history_only:
            with closing(self.documents(file_path)) as documents:
                body = next((body for path, body in documents if path == file_path), None)
        else:
            body = self.store.body(version, file_path)
        if body is None:
            return ReadResult(error="File not found in this run/session")
        return slice_read_response(create_file_data(body), offset, limit)

    def names(self, prefix):
        """Input directory; enumerate index metadata, or this session's bounded history pages."""
        version, thread = self.scope()
        if self.history_only:
            yield from self.store.history(thread, prefix, names_only=True)
        else:
            yield from self.store.names(version, prefix)

    @recover_read
    def ls(self, path):
        """Input a virtual directory; return its immediate children, exposing navigable shards."""
        if not self.valid(path):
            return LsResult(error="Invalid virtual path")
        prefix, entries = path.rstrip("/") + "/", {}
        with closing(self.names(prefix)) as names:
            for name in names:
                tail = name[len(prefix):]
                child = tail.split("/", 1)[0]
                entries[child] = {"path": prefix + child, "is_dir": "/" in tail}
        return LsResult(entries=list(entries.values()))

    @recover_read
    def glob(self, pattern, path=None):
        """Input a glob and scope; return literal registered paths without reading host files."""
        path = path or "/"
        if not self.valid(path) or ".." in PurePosixPath(pattern).parts or "\\" in pattern:
            return GlobResult(error="Invalid virtual path")
        prefix = path.rstrip("/") + "/"
        matches = []
        with closing(self.names(prefix)) as names:
            for name in names:
                target = name if pattern.startswith("/") else name[len(prefix):]
                if "/" not in pattern:
                    target = PurePosixPath(name).name
                if wcglob.globmatch(target, pattern, flags=wcglob.GLOBSTAR | wcglob.BRACE):
                    matches.append({"path": name, "is_dir": False})
        return GlobResult(matches=matches)

    @recover_read
    def grep(self, pattern, path=None, glob=None, *, max_count=None):
        """Input literal text and scope; stream exact substring matches with explicit truncation."""
        path = path or "/"
        if not self.valid(path):
            return GrepResult(error="Invalid virtual path")
        matches = []
        prefix = path.rstrip("/") + "/"
        is_file = bool(PurePosixPath(path).suffix)
        with closing(self.documents(path if is_file else prefix)) as documents:
            for name, body in documents:
                if is_file and name != path:
                    continue
                if glob and not wcglob.globmatch(name[len(prefix):] if "/" in glob else PurePosixPath(name).name,
                                                glob, flags=wcglob.GLOBSTAR | wcglob.BRACE):
                    continue
                for number, line in enumerate(body.splitlines(), 1):
                    if pattern in line:
                        if max_count is not None and len(matches) >= max_count:
                            return GrepResult(matches=matches, truncated=True)
                        matches.append({"path": name, "line": number, "text": line})
        return GrepResult(matches=matches)
