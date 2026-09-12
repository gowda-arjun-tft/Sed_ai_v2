from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path

from ML.deep_research.layer2.backend.cli import load_dotenv_key
from ML.deep_research.layer2.backend.settings import REASONING_EFFORTS

from .pipeline.create_run import create_run, require_current, verify_inputs
from .document_uploads import _run_uploads, run_writer, upload_documents
from ML.deep_research.layer2.backend.fs import storage_path, write_json
from ML.deep_research.layer2.backend.run_log import operational_logger, log_failure
from .pipeline.run_checks import run_checks
from .runner import run_research
from .research_run import checkpoint_root, create_research_run
from .settings import (
    REPO_ROOT, RUNS_DIR, SOURCE_REASONING_EFFORT, SOURCE_SEARCH_DEPTH,
    SOURCE_SEARCH_VERBOSITY, SOURCE_SUGGESTION_PATH, RESEARCH_INSTRUCTION_PATH, WEB_SEARCH_LEVELS,
)


async def run_all(run_dir: Path, *, retry_failed: bool = False) -> None:
    """Run frozen phases; only capability-enabled runs proceed into persistent domain research."""
    run_dir = storage_path(run_dir)
    record = require_current(run_dir)
    verify_inputs(run_dir, record)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} and resume."
        )
    with run_writer(run_dir):
        started = time.perf_counter()
        research = record.get("research")
        with operational_logger(run_dir) as logger:
            try:
                root = checkpoint_root(record) if research else None
            except Exception as error:
                log_failure(logger, "research_storage_preflight_failed", error)
                raise
        try:
            prepare = not research or (research["mode"] == "full" and research["status"] == "pending")
            if prepare:
                await run_research(run_dir, retry_failed=retry_failed)
            record = require_current(run_dir)
            if prepare and record.get("document_uploads", {}).get("policy", {}).get("enabled"):
                record["discovery_status"] = record["status"]
                write_json(run_dir / "run.json", record)
                await _run_uploads(run_dir, retry_failed=retry_failed)
            if research:
                from .domain_research import run_domains

                await run_domains(run_dir, root, retry_failed=retry_failed)
        finally:
            record = require_current(run_dir)
            record["total_elapsed_seconds"] = round(time.perf_counter() - started, 3)
            write_json(run_dir / "run.json", record)
            with operational_logger(run_dir) as logger:
                logger.info("layer3_finished status=%s total_elapsed_seconds=%.3f",
                            record["status"], record["total_elapsed_seconds"])


def _parser() -> argparse.ArgumentParser:
    """Build the thin preparation, linked research, resume and diagnostic interface."""
    parser = argparse.ArgumentParser(
        description="Prepare sources and run independent persistent domain researchers."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--research", type=Path, help="source runs/<fact-sheet>/L2_* folder")
    action.add_argument("--research-from", type=Path, help="create a linked research-only run from settled Layer 3 preparation")
    action.add_argument("--resume-l3", type=Path, help="existing runs/<fact-sheet>/L3_* folder")
    action.add_argument("--upload-documents", type=Path, help="enrich an existing L3 run without model calls")
    action.add_argument("--check-only", type=Path, help="inspect Layer 3 without changing files")
    parser.add_argument("--source-suggestion", type=Path, help="editable source guidance Markdown")
    parser.add_argument("--research-instruction", type=Path, help="editable research purpose and report instructions")
    parser.add_argument("--reasoning-effort", choices=sorted(REASONING_EFFORTS))
    parser.add_argument("--research-reasoning-effort", choices=sorted(REASONING_EFFORTS))
    parser.add_argument("--web-search-depth", choices=sorted(WEB_SEARCH_LEVELS))
    parser.add_argument("--web-search-verbosity", choices=sorted(WEB_SEARCH_LEVELS))
    parser.add_argument("--online", action="store_true", help="enable public web research")
    parser.add_argument(
        "--public-input-confirmed",
        action="store_true",
        help="confirm the Layer 2 input contains only public or invented material",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="retry failed source jobs/downloads or rejected uploads; uncertain uploads are reconciled only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Create/resume frozen Layer 3 phases or print non-mutating observations."""
    parser = _parser()
    args = parser.parse_args(argv)
    new_options = any((args.source_suggestion, args.research_instruction, args.reasoning_effort, args.research_reasoning_effort,
                       args.web_search_depth, args.web_search_verbosity))
    if args.check_only:
        if args.online or args.public_input_confirmed or args.retry_failed or new_options:
            parser.error("--check-only does not accept run or provider options")
        try:
            checks = run_checks(args.check_only.resolve())
        except ValueError as error:
            parser.error(str(error))
        for _, label, ok, detail in checks:
            print(f"{label}: {ok}. {detail}")
        return 0 if all(ok for _, _, ok, _ in checks) else 1
    load_dotenv_key()
    if args.research or args.research_from:
        if not args.online:
            parser.error("--research requires --online")
        if not args.public_input_confirmed:
            parser.error("--research requires --public-input-confirmed")
        if args.retry_failed:
            parser.error("--retry-failed applies only to --resume-l3 or --upload-documents")
        if not os.getenv("OPENAI_API_KEY"):
            parser.error(f"OPENAI_API_KEY is empty; add it to {REPO_ROOT / '.env'}")
        try:
            if args.research_from:
                if args.source_suggestion or args.reasoning_effort:
                    parser.error("--research-from preserves preparation inputs and reasoning")
                run_dir = create_research_run(args.research_from, RUNS_DIR,
                    research_instruction=args.research_instruction or RESEARCH_INSTRUCTION_PATH,
                    public_input_confirmed=args.public_input_confirmed,
                    research_reasoning_effort=args.research_reasoning_effort or "max",
                    web_search_context_size=args.web_search_depth,
                    web_search_verbosity=args.web_search_verbosity)
            else:
                run_dir = create_run(args.research, RUNS_DIR,
                    research_instruction=args.research_instruction or RESEARCH_INSTRUCTION_PATH,
                    source_suggestion=args.source_suggestion or SOURCE_SUGGESTION_PATH,
                    public_input_confirmed=args.public_input_confirmed,
                    reasoning_effort=args.reasoning_effort or SOURCE_REASONING_EFFORT,
                    research_reasoning_effort=args.research_reasoning_effort or "max",
                    web_search_context_size=args.web_search_depth or SOURCE_SEARCH_DEPTH,
                    web_search_verbosity=args.web_search_verbosity or SOURCE_SEARCH_VERBOSITY)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"Created {run_dir}", flush=True)
    else:
        if args.online or args.public_input_confirmed or new_options:
            parser.error("provider options are recorded by the existing Layer 3 run")
        run_dir = (args.upload_documents or args.resume_l3).resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("Existing-run action must point to a CDI Layer 3 run folder")
    try:
        action = upload_documents if args.upload_documents else run_all
        asyncio.run(action(run_dir, retry_failed=args.retry_failed))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Run {run_dir.name}: model responses saved")
    print(f"Sources: {run_dir / 'sources'}")
    print(f"Research: {run_dir / 'research'}")
    print(f"Log: {run_dir / 'run.log'}")
    return 0
