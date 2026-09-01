"""Split, run, resume, merge, and publish Layer 2 domain context."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from .agent import chunk_request, create_chunk_agent, response_value
from .fs import load_json, now_iso, read_text, slug, write_json
from .mission_markdown import write_mission_markdown
from .run_log import operational_logger
from .settings import (
    AGENT_NAMES,
    CHUNK_ENCODING,
    CHUNK_INPUT_PARTITIONING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    CHUNK_STRATEGY,
    LAYER2_SCHEMA_VERSION,
    REPO_ROOT,
)
from .usage import UsageCallback, summarize_usage


def split_fact_sheet(
    text: str,
    *,
    encoding: str = CHUNK_ENCODING,
    size_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """Input source text and token settings; return fixed overlapping model windows."""
    if size_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= size_tokens:
        raise ValueError("invalid Layer 2 chunk size or overlap")
    from langchain_text_splitters import TokenTextSplitter

    splitter = TokenTextSplitter(
        encoding_name=encoding,
        chunk_size=size_tokens,
        chunk_overlap=overlap_tokens,
    )
    return splitter.split_text(text)


def _split_run_fact_sheet(run_dir: Path) -> list[str]:
    """Input a schema-3 run; return chunks made with its frozen current policy."""
    record = load_json(run_dir / "run.json")
    chunking = record.get("chunking", {})
    if record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        raise ValueError("Layer 2 schema 3 is required; start a fresh fact-sheet run")
    if (
        chunking.get("strategy") != CHUNK_STRATEGY
        or chunking.get("input_partitioning") != CHUNK_INPUT_PARTITIONING
    ):
        raise ValueError("Layer 2 run does not use the current fixed-window contract")
    return split_fact_sheet(
        read_text(run_dir / "inputs" / "fact_sheet.md"),
        encoding=str(chunking["encoding"]),
        size_tokens=int(chunking["size_tokens"]),
        overlap_tokens=int(chunking["overlap_tokens"]),
    )


def _chunk_path(run_dir: Path, index: int) -> Path:
    """Input a run and one-based index; return that chunk's JSON path."""
    return run_dir / "chunks" / f"chunk_{index:04d}.json"


def _saved_chunk(path: Path) -> dict[str, Any] | None:
    """Input a chunk path; return its JSON object or None so resume can retry it."""
    if not path.is_file():
        return None
    try:
        value = load_json(path)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _update_summary(record: dict[str, Any], *, result: str | None = None) -> None:
    """Input mutable run metadata; update its operational chunk summary in place."""
    entries = record["chunking"]["chunks"]
    record["chunking"]["summary"] = {
        "total": len(entries),
        "completed": sum(item.get("status") == "complete" for item in entries),
        "failed": sum(item.get("status") == "failed" for item in entries),
    }
    if result is not None:
        record["chunking"]["result"] = result


def _prepare_chunks(
    run_dir: Path, chunks: list[str]
) -> tuple[dict[str, Any], list[tuple[int, str, int]], int]:
    """Input current chunks; persist attempts and return record, pending work and concurrency."""
    record = load_json(run_dir / "run.json")
    previous = {
        item.get("index"): item
        for item in record.get("chunking", {}).get("chunks", [])
        if isinstance(item, dict)
    }
    concurrency = int(record["chunking"]["max_concurrency"])
    if concurrency <= 0:
        raise ValueError("Layer 2 max_concurrency must be positive")
    pending: list[tuple[int, str, int]] = []
    entries = []
    for index, chunk in enumerate(chunks, start=1):
        saved = _saved_chunk(_chunk_path(run_dir, index)) is not None
        attempt = int(previous.get(index, {}).get("attempt", 0) or 0)
        if not saved:
            attempt += 1
            pending.append((index, chunk, attempt))
        entries.append({
            "index": index,
            "file": f"chunks/chunk_{index:04d}.json",
            "status": "complete" if saved else "running",
            "attempt": attempt,
            "error_type": "",
            "error": "",
        })
    record["status"] = "running"
    record["chunking"]["chunks"] = entries
    _update_summary(record, result="running")
    write_json(run_dir / "run.json", record)
    return record, pending, concurrency


def _finish_chunk(
    run_dir: Path,
    index: int,
    status: str,
    error_type: str = "",
    error: str = "",
) -> None:
    """Input one chunk outcome; atomically persist its status for resume and monitoring."""
    record = load_json(run_dir / "run.json")
    record["chunking"]["chunks"][index - 1].update(
        status=status, error_type=error_type, error=error
    )
    _update_summary(record)
    write_json(run_dir / "run.json", record)


def merge_chunks(run_dir: Path, values: list[dict[str, Any]]) -> None:
    """Input chunk JSON in source order; publish eight context-only JSON and Markdown files."""
    for name in AGENT_NAMES:
        context: list[Any] = []
        for value in values:
            collection = value.get("missions")
            contribution = (
                next((
                    item
                    for item in collection
                    if isinstance(item, dict) and item.get("agent") == name
                ), None)
                if isinstance(collection, list)
                else None
            )
            if contribution is None:
                continue
            entries = contribution.get("context")
            if isinstance(entries, list):
                context.extend(entries)
        domain = {"agent": name, "context": context}
        filename = slug(name)
        write_json(run_dir / "missions" / f"{filename}.json", domain)
        write_mission_markdown(run_dir / "mission_md" / f"{filename}.md", domain)


async def write_missions(
    run_dir: Path, logger: logging.Logger | None = None
) -> dict[str, int]:
    """Input a current run; execute missing chunks and return cumulative usage."""
    logger = logger or logging.getLogger(__name__)
    chunks = _split_run_fact_sheet(run_dir)
    record, pending, concurrency = _prepare_chunks(run_dir, chunks)
    chunking = record["chunking"]
    logger.info(
        "chunking_started strategy=%s size_tokens=%s overlap_tokens=%s "
        "stride_tokens=%s input_partitioning=%s chunks=%d concurrency=%d",
        chunking["strategy"],
        chunking.get("size_tokens"),
        chunking.get("overlap_tokens"),
        chunking.get("stride_tokens"),
        chunking["input_partitioning"],
        len(chunks),
        concurrency,
    )
    values = {
        index: saved
        for index in range(1, len(chunks) + 1)
        if (saved := _saved_chunk(_chunk_path(run_dir, index))) is not None
    }
    if pending:
        graph = create_chunk_agent(run_dir)
        inputs = []
        configs = []
        started: dict[int, float] = {}
        for index, chunk, attempt in pending:
            logger.info("chunk_scheduled index=%d attempt=%d", index, attempt)
            started[index] = time.perf_counter()
            inputs.append(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": chunk_request(
                                chunk,
                                index,
                                len(chunks),
                                str(chunking["encoding"]),
                                int(chunking["overlap_tokens"]),
                            ),
                        }
                    ]
                }
            )
            configs.append(
                {
                    "callbacks": [
                        UsageCallback(run_dir, f"chunk-{index:04d}-attempt-{attempt}")
                    ],
                    "max_concurrency": concurrency,
                }
            )
        returned: set[int] = set()
        try:
            async for batch_index, result in graph.abatch_as_completed(
                inputs, configs, return_exceptions=True
            ):
                index, _, attempt = pending[batch_index]
                returned.add(index)
                try:
                    if isinstance(result, Exception):
                        raise result
                    value = response_value(result)
                    write_json(_chunk_path(run_dir, index), value)
                    values[index] = value
                    _finish_chunk(run_dir, index, "complete")
                    logger.info(
                        "chunk_completed index=%d attempt=%d elapsed_seconds=%.3f",
                        index,
                        attempt,
                        time.perf_counter() - started[index],
                    )
                except Exception as exc:
                    _finish_chunk(
                        run_dir, index, "failed", type(exc).__name__, str(exc)
                    )
                    logger.error(
                        "chunk_failed index=%d attempt=%d error_type=%s elapsed_seconds=%.3f",
                        index,
                        attempt,
                        type(exc).__name__,
                        time.perf_counter() - started[index],
                    )
        except Exception as exc:
            for index, _, attempt in pending:
                if index in returned:
                    continue
                _finish_chunk(run_dir, index, "failed", type(exc).__name__, str(exc))
                logger.error(
                    "chunk_failed index=%d attempt=%d error_type=%s "
                    "elapsed_seconds=%.3f",
                    index,
                    attempt,
                    type(exc).__name__,
                    time.perf_counter() - started[index],
                )
    merge_chunks(run_dir, [values[index] for index in sorted(values)])
    record = load_json(run_dir / "run.json")
    failed = any(
        item.get("status") == "failed" for item in record["chunking"]["chunks"]
    )
    _update_summary(record, result="partial" if failed else "complete")
    write_json(run_dir / "run.json", record)
    logger.info(
        "contexts_published completed=%d failed=%d",
        record["chunking"]["summary"]["completed"],
        record["chunking"]["summary"]["failed"],
    )
    return summarize_usage(run_dir)


def run_all(run_dir: Path) -> dict[str, int]:
    """Input a schema-3 run; execute it synchronously and return recorded usage."""
    record = load_json(run_dir / "run.json")
    if record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        raise ValueError("Layer 2 schema 3 is required; start a fresh fact-sheet run")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'}")
    with operational_logger(run_dir) as logger:
        event = "run_started" if record.get("status") == "started" else "run_resumed"
        logger.info("%s run_id=%s", event, record.get("run_id", run_dir.name))
        try:
            usage = asyncio.run(write_missions(run_dir, logger))
        except Exception as exc:
            logger.error("run_failed error_type=%s", type(exc).__name__)
            raise
        record = load_json(run_dir / "run.json")
        record.update(status="complete", usage=usage, finished_at=now_iso())
        write_json(run_dir / "run.json", record)
        logger.info("run_complete result=%s", record.get("chunking", {}).get("result"))
        return usage
