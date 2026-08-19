from __future__ import annotations

import argparse
import os
from pathlib import Path

from .settings import PLANNER_PATH, REPO_ROOT, RUNS_DIR
from .fs import load_json, read_text
from .progress import read_progress
from .pipeline.create_run import create_run
from .pipeline.split_fact_sheet import split_fact_sheet
from .pipeline.route_facts import route_facts, validate_routing
from .pipeline.write_missions import write_missions
from .pipeline.run_checks import Check, run_checks


def load_dotenv_key(project_dir: Path = REPO_ROOT) -> None:
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


def run_all(run_dir: Path) -> list[Check]:
    if "split_mode" not in load_json(run_dir / "run.json"):
        split_fact_sheet(run_dir)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} "
            f"and resume with --resume {run_dir}"
        )
    if any(row["status"] != "done" for row in read_progress(run_dir)):
        route_facts(run_dir)
    validate_routing(run_dir)
    write_missions(run_dir)
    return run_checks(run_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Turn one CDI fact sheet into fourteen checked research missions."
    )
    parser.add_argument("fact_sheet", nargs="?", type=Path)
    parser.add_argument(
        "--resume",
        type=Path,
        help="resume an existing runs/L2_* folder",
    )
    parser.add_argument(
        "--check-only",
        type=Path,
        help="rerun deterministic phase-4 checks only",
    )
    args = parser.parse_args(argv)
    load_dotenv_key()
    if args.check_only:
        checks = run_checks(args.check_only.resolve())
        return 0 if all(ok for _, _, ok, _ in checks) else 1
    if args.resume:
        run_dir = args.resume.resolve()
        if not (run_dir / "run.json").is_file():
            parser.error("--resume must point to a CDI run folder")
    else:
        if not args.fact_sheet:
            parser.error("provide a fact_sheet.md path or --resume")
        run_dir = create_run(args.fact_sheet, PLANNER_PATH, RUNS_DIR)
        print(f"Created {run_dir}", flush=True)
    checks = run_all(run_dir)
    passed = sum(ok for _, _, ok, _ in checks)
    print(f"Run {run_dir.name}: {passed}/19 checks passed")
    print(f"Missions: {run_dir / 'missions'}")
    print(f"Report: {run_dir / 'check_report.md'}")
    return 0 if passed == 19 else 1
