from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ML.deep_research.layer2.cli import load_dotenv_key
from ML.deep_research.layer2.fs import load_json

from .pipeline.create_run import create_run
from .pipeline.run_checks import Check, run_checks
from .pipeline.run_researchers import run_researchers
from .pipeline.run_second_round import run_second_round
from .pipeline.write_answers import write_answers
from .pipeline.write_questions import write_questions
from .settings import REPO_ROOT, RUNS_DIR


async def run_all(run_dir: Path, *, retry_failed: bool = False) -> list[Check]:
    run = load_json(run_dir / "run.json")
    if run.get("provider") == "online" and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} and resume the Layer 3 run."
        )
    phases = run.get("phases", {})
    if phases.get("1") != "complete" or retry_failed:
        await run_researchers(run_dir, retry_failed=retry_failed)
    if phases.get("2") != "complete" or retry_failed:
        await write_questions(run_dir, retry_failed=retry_failed)
    if phases.get("3") != "complete" or retry_failed:
        await run_second_round(run_dir, retry_failed=retry_failed)
    if phases.get("4") != "complete" or retry_failed:
        await write_answers(run_dir, retry_failed=retry_failed)
    return run_checks(run_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research fourteen checked CDI Layer 2 missions through five independent lenses."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--research", type=Path, help="source runs/L2_* folder")
    action.add_argument("--resume-l3", type=Path, help="existing runs/L3_* folder")
    action.add_argument("--check-only", type=Path, help="rerun Layer 3 checks only")
    provider = parser.add_mutually_exclusive_group()
    provider.add_argument("--fixtures", type=Path, help="offline fixture provider root")
    provider.add_argument("--online", action="store_true", help="enable public web research")
    parser.add_argument(
        "--public-input-confirmed",
        action="store_true",
        help="confirm the Layer 2 input contains only public or invented material",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="retry failed sessions and regenerate dependent aggregation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    load_dotenv_key()
    if args.check_only:
        checks = run_checks(args.check_only.resolve())
        return 0 if all(ok for _, _, ok, _ in checks) else 1
    if args.research:
        if args.fixtures is None and not args.online:
            parser.error("--research requires either --fixtures or --online")
        try:
            run_dir = create_run(
                args.research,
                RUNS_DIR,
                fixture_root=args.fixtures,
                online=args.online,
                public_input_confirmed=args.public_input_confirmed,
            )
        except ValueError as error:
            parser.error(str(error))
        print(f"Created {run_dir}", flush=True)
    else:
        if args.fixtures or args.online or args.public_input_confirmed:
            parser.error("provider options are recorded by the existing Layer 3 run")
        run_dir = args.resume_l3.resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("--resume-l3 must point to a CDI Layer 3 run folder")
    checks = asyncio.run(run_all(run_dir, retry_failed=args.retry_failed))
    passed = sum(ok for _, _, ok, _ in checks)
    print(f"Run {run_dir.name}: {passed}/{len(checks)} checks passed")
    print(f"Answers: {run_dir / 'research'}")
    print(f"Report: {run_dir / 'check_report.md'}")
    return 0 if passed == len(checks) else 1
