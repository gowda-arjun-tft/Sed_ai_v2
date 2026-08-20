from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ML.deep_research.layer2.cli import load_dotenv_key

from .pipeline.create_run import create_run
from .pipeline.run_checks import Check, run_checks
from .runner import run_missions
from .settings import REPO_ROOT, RUNS_DIR


async def run_all(run_dir: Path, *, retry_failed: bool = False) -> list[Check]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} and resume."
        )
    await run_missions(run_dir, retry_failed=retry_failed)
    return run_checks(run_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research fourteen CDI missions with mission-scoped Deep Agent supervisors."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--research", type=Path, help="source runs/L2_* folder")
    action.add_argument("--resume-l3", type=Path, help="existing runs/L3_* folder")
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
        help="retry failed missions in clean checkpoint threads",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.check_only:
        if args.online or args.public_input_confirmed or args.retry_failed:
            parser.error("--check-only does not accept run or provider options")
        checks = run_checks(args.check_only.resolve())
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
            )
        except ValueError as error:
            parser.error(str(error))
        print(f"Created {run_dir}", flush=True)
    else:
        if args.online or args.public_input_confirmed:
            parser.error("provider options are recorded by the existing Layer 3 run")
        run_dir = args.resume_l3.resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("--resume-l3 must point to a CDI Layer 3 run folder")
    try:
        checks = asyncio.run(run_all(run_dir, retry_failed=args.retry_failed))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    passed = sum(ok for _, _, ok, _ in checks)
    print(f"Run {run_dir.name}: {passed}/{len(checks)} checks passed")
    print(f"Answers: {run_dir / 'research'}")
    print(f"Report: {run_dir / 'check_report.md'}")
    return 0 if passed == len(checks) else 1
