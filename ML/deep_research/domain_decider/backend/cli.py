"""Thin command-line adapter for the Layer 2 runner."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .create_run import create_run, require_current
from .fs import load_json, read_text
from .report import run_checks
from .runner import run_all
from .settings import (
    REPO_ROOT, RUNS_DIR, WEB_SEARCH_CONTEXT_SIZE, WEB_SEARCH_LEVELS,
    WEB_SEARCH_VERBOSITY,
)


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
    """Input a CLI parser and run; stop CLI execution unless the run is schema 9."""
    try:
        require_current(run_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


def _print_summary(run_dir: Path) -> None:
    """Input a completed run; print its compact operator summary and resume hint."""
    record = load_json(run_dir / "run.json")
    failed = [key for key, item in record["jobs"].items() if item["status"] == "failed"]
    print(f"Layer 2: {record['status']} — {len(failed)} failed jobs")
    if failed:
        print(f'.\\run.ps1 -Resume "{run_dir}"')
    print(f"Run: {run_dir}\nLog: {run_dir / 'run.log'}")


def main(argv: list[str] | None = None) -> int:
    """Input optional CLI arguments; create, resume or inspect one Layer 2 run."""
    parser = argparse.ArgumentParser(
        description="Prepare metadata and ID-routed research Markdown (Layer 2 schema 9)."
    )
    parser.add_argument("fact_sheet", nargs="?", type=Path)
    parser.add_argument("--domain-plugin", type=Path)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--web-search-depth", choices=sorted(WEB_SEARCH_LEVELS),
                        default=WEB_SEARCH_CONTEXT_SIZE)
    parser.add_argument("--web-search-verbosity", choices=sorted(WEB_SEARCH_LEVELS),
                        default=WEB_SEARCH_VERBOSITY)
    parser.add_argument("--public-input-confirmed", action="store_true",
                        help="confirm supplied context is suitable for public web-assisted planning")
    parser.add_argument("--resume", type=Path, help="resume a schema-9 Layer 2 run")
    parser.add_argument("--check-only", type=Path, help="inspect a schema-9 Layer 2 run")
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
        if not (args.fact_sheet and args.domain_plugin and args.requirements):
            parser.error("provide fact_sheet.md, --domain-plugin and --requirements, or --resume")
        run_dir = create_run(args.fact_sheet, args.domain_plugin, args.requirements, RUNS_DIR,
                             web_search_context_size=args.web_search_depth,
                             web_search_verbosity=args.web_search_verbosity,
                             public_input_confirmed=args.public_input_confirmed)
        print(f"Created {run_dir}", flush=True)
    run_all(run_dir)
    _print_summary(run_dir)
    return 0
