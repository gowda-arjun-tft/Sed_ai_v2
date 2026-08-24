"""Create, run, resume, and check the parallel structured Layer 2 workflow."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from .agent import chunk_request, create_chunk_agent, domain_key, response_value
from .create_run import create_run
from .fs import load_json, now_iso, read_text, slug, write_json
from .mission_markdown import write_mission_markdown
from .report import run_checks
from .settings import (
    CHUNK_ENCODING,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SEPARATORS,
    CHUNK_SIZE_TOKENS,
    LAYER2_SCHEMA_VERSION,
    MAX_CHUNK_CONCURRENCY,
    AGENT_NAMES,
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


def _saved_chunk(path: Path) -> dict[str, Any] | None:
    """Reuse any saved JSON object, regardless of its internal shape."""
    if not path.is_file():
        return None
    try:
        value = load_json(path)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _record_chunks(run_dir: Path, chunks: list[str]) -> None:
    record = load_json(run_dir / "run.json")
    previous = {
        item.get("index"): item
        for item in record.get("chunking", {}).get("chunks", [])
        if isinstance(item, dict)
    }
    record["status"] = "running"
    record["chunking"]["chunks"] = [
        {
            "index": index,
            "file": f"chunks/chunk_{index:04d}.json",
            "status": "complete" if _saved_chunk(_chunk_path(run_dir, index)) else "pending",
            "attempt": int(previous.get(index, {}).get("attempt", 0) or 0),
            "error_type": "",
            "error": "",
        }
        for index in range(1, len(chunks) + 1)
    ]
    completed = sum(
        item["status"] == "complete" for item in record["chunking"]["chunks"]
    )
    record["chunking"].update(
        result="running",
        summary={"total": len(chunks), "completed": completed, "failed": 0},
    )
    write_json(run_dir / "run.json", record)


async def _start_chunk(
    run_dir: Path,
    index: int,
    lock: asyncio.Lock,
) -> int:
    async with lock:
        record = load_json(run_dir / "run.json")
        entry = record["chunking"]["chunks"][index - 1]
        attempt = int(entry.get("attempt", 0) or 0) + 1
        entry.update(
            status="running", attempt=attempt, error_type="", error=""
        )
        write_json(run_dir / "run.json", record)
        return attempt


async def _finish_chunk(
    run_dir: Path,
    index: int,
    status: str,
    error_type: str,
    error: str,
    lock: asyncio.Lock,
) -> None:
    async with lock:
        record = load_json(run_dir / "run.json")
        entry = record["chunking"]["chunks"][index - 1]
        entry.update(status=status, error_type=error_type, error=error)
        write_json(run_dir / "run.json", record)


def _finish_chunking(run_dir: Path) -> None:
    record = load_json(run_dir / "run.json")
    chunks = record["chunking"]["chunks"]
    completed = sum(item.get("status") == "complete" for item in chunks)
    failed = sum(item.get("status") == "failed" for item in chunks)
    record["chunking"].update(
        result="partial" if failed else "complete",
        summary={"total": len(chunks), "completed": completed, "failed": failed},
    )
    write_json(run_dir / "run.json", record)


async def _run_chunk(
    graph: Any,
    run_dir: Path,
    chunk: str,
    index: int,
    total: int,
    semaphore: asyncio.Semaphore,
    lock: asyncio.Lock,
) -> dict[str, Any]:
    path = _chunk_path(run_dir, index)
    saved = _saved_chunk(path)
    if saved is not None:
        return saved
    async with semaphore:
        attempt = await _start_chunk(run_dir, index, lock)
        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": chunk_request(chunk, index, total)}]},
                config={
                    "callbacks": [
                        UsageCallback(
                            run_dir, f"chunk-{index:04d}-attempt-{attempt}"
                        )
                    ]
                },
            )
            value = response_value(result)
            write_json(path, value)
            await _finish_chunk(run_dir, index, "complete", "", "", lock)
            return value
        except Exception as exc:
            await _finish_chunk(
                run_dir, index, "failed", type(exc).__name__, str(exc), lock
            )
            raise


def _contribution(value: dict[str, Any], name: str) -> dict[str, Any] | None:
    for key in (domain_key(name), name):
        item = value.get(key)
        if isinstance(item, dict):
            return item
    missions = value.get("missions")
    if isinstance(missions, list):
        return next(
            (
                item
                for item in missions
                if isinstance(item, dict) and item.get("agent") == name
            ),
            None,
        )
    return None


def merge_chunks(run_dir: Path, values: list[dict[str, Any]]) -> None:
    """Append every domain contribution in chunk order without deduplication."""
    for name in AGENT_NAMES:
        parts: list[str] = []
        context: list[Any] = []
        for value in values:
            contribution = _contribution(value, name)
            if contribution is None:
                continue
            mission = contribution.get("mission")
            if isinstance(mission, str) and mission:
                parts.append(mission)
            entries = contribution.get("context")
            if isinstance(entries, list):
                context.extend(entries)
        mission = {"agent": name, "mission": "\n\n".join(parts), "context": context}
        filename = slug(name)
        write_json(run_dir / "missions" / f"{filename}.json", mission)
        write_mission_markdown(run_dir / "mission_md" / f"{filename}.md", mission)


async def write_missions(run_dir: Path) -> dict[str, int]:
    """Run missing chunks concurrently, save them, and append their outputs."""
    chunks = split_fact_sheet(read_text(run_dir / "inputs" / "fact_sheet.md"))
    graph = create_chunk_agent(run_dir)
    _record_chunks(run_dir, chunks)
    semaphore = asyncio.Semaphore(MAX_CHUNK_CONCURRENCY)
    lock = asyncio.Lock()
    results = await asyncio.gather(
        *(
            _run_chunk(graph, run_dir, chunk, index, len(chunks), semaphore, lock)
            for index, chunk in enumerate(chunks, start=1)
        ),
        return_exceptions=True,
    )
    merge_chunks(run_dir, [item for item in results if isinstance(item, dict)])
    _finish_chunking(run_dir)
    return summarize_usage(run_dir)


def run_all(run_dir: Path) -> dict[str, int]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'}")
    usage = asyncio.run(write_missions(run_dir))
    record = load_json(run_dir / "run.json")
    record.update(status="complete", usage=usage, finished_at=now_iso())
    write_json(run_dir / "run.json", record)
    return usage


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


def _print_summary(run_dir: Path) -> None:
    record = load_json(run_dir / "run.json")
    chunking = record.get("chunking", {})
    chunks = chunking.get("chunks", [])
    summary = chunking.get("summary", {})
    completed = int(summary.get("completed", 0) or 0)
    failed = [item for item in chunks if item.get("status") == "failed"]
    print(f"Run {run_dir.name}: {completed}/{len(chunks)} chunks returned JSON")
    if failed:
        print("WARNING: Layer 2 published partial missions with failed chunks.")
        for item in failed:
            print(
                f"  Chunk {item.get('index')} attempt {item.get('attempt', 0)}: "
                f"{item.get('error_type') or 'Error'}: {item.get('error') or 'unknown error'}"
            )
        print(f'.\\run.ps1 -Resume "{run_dir}"')
    print(f"Missions: {run_dir / 'missions'}")


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
    run_all(run_dir)
    _print_summary(run_dir)
    return 0
