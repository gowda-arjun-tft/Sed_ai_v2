"""Thin command-line adapter for the Layer 2 runner."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .create_run import create_run
from .fs import load_json, read_text
from .report import run_checks
from .runner import run_all
from .settings import LAYER2_SCHEMA_VERSION, PLANNER_PATH, REPO_ROOT, RUNS_DIR


def load_dotenv_key(project_dir: Path = REPO_ROOT) -> None:
    """Input a project root; load its API key into the process for all layer CLIs."""
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


def _require_current_run(parser: argparse.ArgumentParser, run_dir: Path) -> None:
    """Input a CLI parser and run; stop CLI execution unless the run is schema 3."""
    try:
        record = load_json(run_dir / "run.json")
    except (OSError, ValueError):
        parser.error("the run folder has no readable run.json")
    if record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        parser.error("Layer 2 schema 3 is required; start a fresh fact-sheet run")


def _print_summary(run_dir: Path) -> None:
    """Input a completed run; print its compact operator summary and resume hint."""
    record = load_json(run_dir / "run.json")
    chunks = record.get("chunking", {}).get("chunks", [])
    summary = record.get("chunking", {}).get("summary", {})
    failed = [item for item in chunks if item.get("status") == "failed"]
    print(
        f"Run {run_dir.name}: {int(summary.get('completed', 0) or 0)}/"
        f"{len(chunks)} chunks returned JSON"
    )
    if failed:
        print("WARNING: Layer 2 published partial domain context with failed chunks.")
        for item in failed:
            print(
                f"  Chunk {item.get('index')} attempt {item.get('attempt', 0)}: "
                f"{item.get('error_type') or 'Error'}: {item.get('error') or 'unknown error'}"
            )
        print(f'.\\run.ps1 -Resume "{run_dir}"')
    print(f"Domain context: {run_dir / 'missions'}")


def main(argv: list[str] | None = None) -> int:
    """Input optional CLI arguments; create, resume or inspect one Layer 2 run."""
    parser = argparse.ArgumentParser(
        description="Route one CDI fact sheet into eight domain-context files."
    )
    parser.add_argument("fact_sheet", nargs="?", type=Path)
    parser.add_argument("--resume", type=Path, help="resume a schema-3 Layer 2 run")
    parser.add_argument("--check-only", type=Path, help="inspect a schema-3 Layer 2 run")
    args = parser.parse_args(argv)
    load_dotenv_key()
    if args.check_only:
        run_dir = args.check_only.resolve()
        _require_current_run(parser, run_dir)
        checks = run_checks(run_dir)
        for _, label, ok, detail in checks:
            print(f"[{'x' if ok else ' '}] {label} — {detail}")
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
