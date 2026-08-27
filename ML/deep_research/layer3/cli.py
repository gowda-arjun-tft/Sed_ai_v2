from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ML.deep_research.layer2.cli import load_dotenv_key
from ML.deep_research.layer2.fs import load_json

from .pipeline.create_run import create_run
from .pipeline.run_checks import Check, run_checks
from .runner import run_research
from .settings import DEFAULT_OCR_LANGUAGES, REPO_ROOT, RUNS_DIR, SCHEMA_VERSION


async def run_all(run_dir: Path, *, retry_failed: bool = False) -> None:
    schema = load_json(run_dir / "run.json").get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 3 schema {schema!r} cannot resume in schema {SCHEMA_VERSION}; "
            "start a fresh Layer 3 run"
        )
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} and resume."
        )
    await run_research(run_dir, retry_failed=retry_failed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research one CDI property with eight sequential domain-scoped STORM coordinators."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--research", type=Path, help="source runs/<fact-sheet>/L2_* folder")
    action.add_argument("--resume-l3", type=Path, help="existing runs/<fact-sheet>/L3_* folder")
    action.add_argument("--check-only", type=Path, help="rerun Layer 3 checks only")
    parser.add_argument("--online", action="store_true", help="enable public web research")
    parser.add_argument(
        "--public-input-confirmed",
        action="store_true",
        help="confirm the Layer 2 input contains only public or invented material",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="resume failed invocations from their durable checkpoints",
    )
    parser.add_argument(
        "--ocr-languages",
        metavar="LANGUAGES",
        help=(
            "comma-separated EasyOCR languages for a new run "
            f"(default: {','.join(DEFAULT_OCR_LANGUAGES)})"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.check_only:
        if (
            args.online
            or args.public_input_confirmed
            or args.retry_failed
            or args.ocr_languages is not None
        ):
            parser.error("--check-only does not accept run options")
        try:
            checks = run_checks(args.check_only.resolve())
        except ValueError as error:
            parser.error(str(error))
        return 0 if all(ok for _, _, ok, _ in checks) else 1
    load_dotenv_key()
    if args.research:
        if not args.online:
            parser.error("--research requires --online")
        if not args.public_input_confirmed:
            parser.error("--research requires --public-input-confirmed")
        if args.retry_failed:
            parser.error("--retry-failed applies only to --resume-l3")
        if not os.getenv("OPENAI_API_KEY"):
            parser.error(f"OPENAI_API_KEY is empty; add it to {REPO_ROOT / '.env'}")
        try:
            run_dir = create_run(
                args.research,
                RUNS_DIR,
                public_input_confirmed=args.public_input_confirmed,
                ocr_languages=(
                    args.ocr_languages or ",".join(DEFAULT_OCR_LANGUAGES)
                ),
            )
        except ValueError as error:
            parser.error(str(error))
        print(f"Created {run_dir}", flush=True)
    else:
        if args.online or args.public_input_confirmed or args.ocr_languages is not None:
            parser.error("new-run options are recorded by the existing Layer 3 run")
        run_dir = args.resume_l3.resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("--resume-l3 must point to a CDI Layer 3 run folder")
    try:
        asyncio.run(run_all(run_dir, retry_failed=args.retry_failed))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Run {run_dir.name}: model responses saved")
    print(f"Answer: {run_dir / 'research' / 'final.md'}")
    return 0
