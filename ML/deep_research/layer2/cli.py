"""Create, run, resume, and check the parallel structured Layer 2 workflow."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .agent import chunk_request, create_chunk_agent, domain_key, structured_value
from .create_run import create_run
from .fs import load_json, read_text, slug, write_json
from .planner import load_planner
from .report import Check, run_checks
from .settings import (
    CHUNK_ENCODING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SEPARATORS,
    CHUNK_SIZE_TOKENS,
    LAYER2_SCHEMA_VERSION,
    MAX_CHUNK_CONCURRENCY,
    PLANNER_PATH,
    REPO_ROOT,
    RUNS_DIR,
)
from .usage import UsageCallback, summarize_usage


def load_dotenv_key(project_dir: Path = REPO_ROOT) -> None:
    """Load only OPENAI_API_KEY from the repository .env when needed."""
    if os.getenv("OPENAI_API_KEY"):
        return
    env_path = project_dir / ".env"
    if not env_path.exists():
        return
    for raw_line in read_text(env_path).splitlines():
        key, separator, value = raw_line.partition("=")
        if separator and key.strip() == "OPENAI_API_KEY":
            os.environ["OPENAI_API_KEY"] = value.strip().strip("\"'")
            return


def split_fact_sheet(text: str) -> list[str]:
    """Split Markdown by model tokens, preferring heading and paragraph boundaries."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=CHUNK_ENCODING,
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        separators=list(CHUNK_SEPARATORS),
        keep_separator="start",
    )
    return splitter.split_text(text)


def _chunk_path(run_dir: Path, index: int) -> Path:
    return run_dir / "chunks" / f"chunk_{index:04d}.json"


def _saved_chunk(path: Path, schema: type[BaseModel]) -> BaseModel | None:
    """Return one valid saved structured response, otherwise schedule it again."""
    if not path.is_file():
        return None
    try:
        return schema.model_validate(load_json(path))
    except (OSError, ValueError, ValidationError):
        return None


def _record_chunks(run_dir: Path, chunks: list[str], schema: type[BaseModel]) -> None:
    record = load_json(run_dir / "run.json")
    record["status"] = "running"
    record["chunking"]["chunks"] = [
        {
            "index": index,
            "file": f"chunks/chunk_{index:04d}.json",
            "status": "complete" if _saved_chunk(_chunk_path(run_dir, index), schema) else "pending",
            "error": "",
        }
        for index in range(1, len(chunks) + 1)
    ]
    write_json(run_dir / "run.json", record)


async def _set_chunk_status(
    run_dir: Path,
    index: int,
    status: str,
    error: str,
    lock: asyncio.Lock,
) -> None:
    async with lock:
        record = load_json(run_dir / "run.json")
        entry = record["chunking"]["chunks"][index - 1]
        entry.update(status=status, error=error)
        write_json(run_dir / "run.json", record)


async def _run_chunk(
    graph: Any,
    schema: type[BaseModel],
    run_dir: Path,
    chunk: str,
    index: int,
    total: int,
    semaphore: asyncio.Semaphore,
    lock: asyncio.Lock,
) -> BaseModel:
    path = _chunk_path(run_dir, index)
    saved = _saved_chunk(path, schema)
    if saved is not None:
        return saved
    async with semaphore:
        await _set_chunk_status(run_dir, index, "running", "", lock)
        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": chunk_request(chunk, index, total)}]},
                config={"callbacks": [UsageCallback(run_dir, f"chunk-{index:04d}")]},
            )
            value = structured_value(result, schema)
            write_json(path, value.model_dump())
            await _set_chunk_status(run_dir, index, "complete", "", lock)
            return value
        except Exception as exc:
            await _set_chunk_status(run_dir, index, "failed", str(exc), lock)
            raise


def merge_chunks(run_dir: Path, values: list[BaseModel]) -> None:
    """Append every domain contribution in chunk order without deduplication."""
    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    for definition in definitions:
        name = definition["name"]
        key = domain_key(name)
        parts: list[str] = []
        context: list[dict[str, Any]] = []
        for value in values:
            contribution = getattr(value, key)
            if contribution.mission:
                parts.append(contribution.mission)
            context.extend(item.model_dump() for item in contribution.context)
        write_json(
            run_dir / "missions" / f"{slug(name)}.json",
            {"agent": name, "mission": "\n\n".join(parts), "context": context},
        )


async def write_missions(run_dir: Path) -> dict[str, int]:
    """Run missing chunks concurrently, save them, and append their outputs."""
    chunks = split_fact_sheet(read_text(run_dir / "inputs" / "fact_sheet.md"))
    graph, schema = create_chunk_agent(run_dir)
    _record_chunks(run_dir, chunks, schema)
    semaphore = asyncio.Semaphore(MAX_CHUNK_CONCURRENCY)
    lock = asyncio.Lock()
    results = await asyncio.gather(
        *(
            _run_chunk(graph, schema, run_dir, chunk, index, len(chunks), semaphore, lock)
            for index, chunk in enumerate(chunks, start=1)
        ),
        return_exceptions=True,
    )
    failures = [item for item in results if isinstance(item, BaseException)]
    if failures:
        raise RuntimeError(f"{len(failures)} Layer 2 chunk call(s) failed") from failures[0]
    merge_chunks(run_dir, list(results))
    return summarize_usage(run_dir)


def run_all(run_dir: Path) -> list[Check]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'}")
    usage = asyncio.run(write_missions(run_dir))
    record = load_json(run_dir / "run.json")
    record["usage"] = usage
    write_json(run_dir / "run.json", record)
    return run_checks(run_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn one CDI fact sheet into eight missions.")
    parser.add_argument("fact_sheet", nargs="?", type=Path)
    parser.add_argument("--resume", type=Path, help="resume a schema-2 Layer 2 run")
    parser.add_argument("--check-only", type=Path, help="recheck a schema-2 Layer 2 run")
    return parser


def _require_current_run(parser: argparse.ArgumentParser, run_dir: Path) -> None:
    try:
        record = load_json(run_dir / "run.json")
    except (OSError, ValueError):
        parser.error("the run folder has no readable run.json")
    if record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        parser.error("legacy Layer 2 runs cannot resume; start a fresh fact-sheet run")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    load_dotenv_key()
    if args.check_only:
        run_dir = args.check_only.resolve()
        _require_current_run(parser, run_dir)
        checks = run_checks(run_dir)
        return 0 if all(ok for _, _, ok, _ in checks) else 1
    if args.resume:
        run_dir = args.resume.resolve()
        _require_current_run(parser, run_dir)
    else:
        if not args.fact_sheet:
            parser.error("provide a fact_sheet.md path or --resume")
        run_dir = create_run(args.fact_sheet, PLANNER_PATH, RUNS_DIR)
        print(f"Created {run_dir}", flush=True)
    checks = run_all(run_dir)
    passed = sum(ok for _, _, ok, _ in checks)
    print(f"Run {run_dir.name}: {passed}/{len(checks)} checks passed")
    print(f"Missions: {run_dir / 'missions'}")
    print(f"Report: {run_dir / 'check_report.md'}")
    return 0 if passed == len(checks) else 1
