from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ML.deep_research.layer2.cli import load_dotenv_key
from ML.deep_research.layer2.fs import load_json

from .create_run import create_run
from .runner import run_external_research
from .settings import REPO_ROOT, SCHEMA_VERSION


async def run_all(run_dir: Path, *, retry_failed: bool = False) -> None:
    schema = load_json(run_dir / "run.json").get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 4 schema {schema!r} cannot resume in schema {SCHEMA_VERSION}; "
            "start a fresh Layer 4 run"
        )
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} and resume."
        )
    await run_external_research(run_dir, retry_failed=retry_failed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research external influences over eight Layer 3 domain reports."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--external-research",
        type=Path,
        help="source runs/<fact-sheet>/L3_* folder",
    )
    action.add_argument(
        "--resume-l4",
        type=Path,
        help="existing runs/<fact-sheet>/L4_* folder",
    )
    parser.add_argument("--online", action="store_true", help="enable public web research")
    parser.add_argument(
        "--public-input-confirmed",
        action="store_true",
        help="confirm the Layer 3 input contains only public or invented material",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="resume failed invocations from their durable checkpoints",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    load_dotenv_key()
    if args.external_research:
        if not args.online:
            parser.error("--external-research requires --online")
        if not args.public_input_confirmed:
            parser.error("--external-research requires --public-input-confirmed")
        if args.retry_failed:
            parser.error("--retry-failed applies only to --resume-l4")
        if not os.getenv("OPENAI_API_KEY"):
            parser.error(f"OPENAI_API_KEY is empty; add it to {REPO_ROOT / '.env'}")
        try:
            run_dir = create_run(
                args.external_research,
                public_input_confirmed=True,
            )
        except ValueError as error:
            parser.error(str(error))
        print(f"Created {run_dir}", flush=True)
    else:
        if args.online or args.public_input_confirmed:
            parser.error("provider options are recorded by the existing Layer 4 run")
        run_dir = args.resume_l4.resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("--resume-l4 must point to a CDI Layer 4 run folder")
    try:
        asyncio.run(run_all(run_dir, retry_failed=args.retry_failed))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Run {run_dir.name}: model responses saved")
    print(f"External landscape: {run_dir / 'research' / 'final.md'}")
    return 0


__all__ = ["main", "run_all"]

