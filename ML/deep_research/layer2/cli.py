r"""Layer 2's entry point -- the three steps, in order.

```
create_run   ->  the agent  ->  run_checks
(no model)       (the model)    (no model)
```

That is the whole of Layer 2. There are no phases between those three: the
splitting, routing and per-subject mission passes that used to sit in the middle
are now decisions the agent makes for itself.

Reached from the command line as `python -m ML.deep_research.layer2`, or through
`run.ps1`:

```powershell
.\run.ps1 -FactSheet 'C:\path\to\fact_sheet.md'   # new run
.\run.ps1 -Resume '.\runs\L2_20260820_a1b2'       # continue one
```
"""

from __future__ import annotations

import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from .agent import RECURSION_LIMIT, create_mission_agent, mission_request
from .create_run import create_run
from .fs import read_text
from .report import Check, run_checks
from .settings import PLANNER_PATH, REPO_ROOT, RUNS_DIR


def load_dotenv_key(project_dir: Path = REPO_ROOT) -> None:
    """Put `OPENAI_API_KEY` from `.env` into the environment, if it is not there.

    A deliberately minimal reader: one key, no dependency on python-dotenv, and
    an existing environment variable always wins so CI or a shell export can
    override the file. Surrounding quotes are stripped, since `.env` files are
    commonly written both ways.

    The key is the only secret this project has, and it stays in `.env` -- never
    in a prompt, a checkpoint, or a run artefact. Layer 3's CLI imports this
    function rather than repeating it.
    """
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


@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    """Open the run's SQLite checkpointer. This is what replaces a progress file.

    LangGraph writes the conversation -- every message, tool call and tool result
    -- into `checkpoints.sqlite3` inside the run folder after each step. Because
    `write_missions` always uses the same `thread_id`, rerunning a folder resumes
    that same conversation: the agent picks up with everything it had already
    read and decided, rather than starting the sheet again.

    The old design tracked progress in a CSV that the code maintained and the
    agent could not see. This is durable in the framework, needs no bookkeeping,
    and covers reasoning as well as files.

    `LANGGRAPH_STRICT_MSGPACK` is set so serialisation failures raise at write
    time instead of silently storing something that cannot be read back --
    a checkpoint that fails to load is a checkpoint that is not there.
    `setdefault`, so an explicit environment setting is respected.

    Yields:
        The saver, for `create_mission_agent(run_dir, saver)`. Closed on exit.
    """
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(
        str(run_dir / "checkpoints.sqlite3")
    ) as saver:
        await saver.setup()
        yield saver


async def write_missions(run_dir: Path) -> None:
    """Step 2: hand the job to the agent and wait.

    One `ainvoke` with one user message. Everything that happens inside -- how
    the sheet is read, whether helpers are spawned, how the work is checked -- is
    the agent's, and this function does not inspect the result. The files on disk
    and the report that follows are the outcome; the final message is for the
    human reading the console.

    `thread_id` is derived from the run folder name, which is what makes the run
    resumable and keeps two different properties from sharing a conversation.

    `recursion_limit` belongs in this config rather than on the agent, because
    LangGraph reads it per invocation. Without it the framework's own step
    ceiling would end a long run mid-way with nothing to show.
    """
    async with checkpoint_saver(run_dir) as saver:
        agent = create_mission_agent(run_dir, saver)
        await agent.ainvoke(
            {"messages": [{"role": "user", "content": mission_request()}]},
            config={
                "configurable": {"thread_id": f"{run_dir.name}:missions"},
                "recursion_limit": RECURSION_LIMIT,
            },
        )


def run_all(run_dir: Path) -> list[Check]:
    """Steps 2 and 3: run the agent, then write the report.

    The key is checked before the agent starts, and the error names `--resume`,
    because a run folder already exists at this point -- a missing key should cost
    the setup, not the run.

    Returns:
        The checks, for the caller's exit code.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            f"OPENAI_API_KEY is empty. Add it to {REPO_ROOT / '.env'} "
            f"and resume with --resume {run_dir}"
        )
    asyncio.run(write_missions(run_dir))
    return run_checks(run_dir)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one of the three modes, and return an exit code.

    Args:
        argv: Command-line arguments. `None` reads `sys.argv`; tests pass a list.

    Returns:
        0 when every check passed, 1 otherwise.

    The three modes:

    * **a fact sheet path** -- create a run folder, run the agent, report.
    * **`--resume <run folder>`** -- skip creation and continue the existing
      conversation from its checkpoint. The same command whether the run was
      interrupted, ran out of key, or simply needs another pass.
    * **`--check-only <run folder>`** -- rewrite the report with no model call.
      For completing a run whose report was interrupted, or re-reading one after
      a check was added.
    """
    parser = argparse.ArgumentParser(
        description="Turn one CDI fact sheet into fourteen research missions."
    )
    parser.add_argument("fact_sheet", nargs="?", type=Path)
    parser.add_argument(
        "--resume", type=Path, help="resume an existing runs/L2_* folder"
    )
    parser.add_argument(
        "--check-only", type=Path, help="rewrite the report for an existing run"
    )
    args = parser.parse_args(argv)
    load_dotenv_key()

    if args.check_only:
        checks = run_checks(args.check_only.resolve())
        return 0 if all(ok for _, _, ok, _ in checks) else 1

    if args.resume:
        run_dir = args.resume.resolve()
        # run.json is the marker of a real run folder; without it there is no
        # thread to resume and no record to complete.
        if not (run_dir / "run.json").is_file():
            parser.error("--resume must point to a CDI run folder")
    else:
        if not args.fact_sheet:
            parser.error("provide a fact_sheet.md path or --resume")
        run_dir = create_run(args.fact_sheet, PLANNER_PATH, RUNS_DIR)
        # Printed before the agent starts, so the folder to resume is on screen
        # even if the run is interrupted or the process is killed.
        print(f"Created {run_dir}", flush=True)

    checks = run_all(run_dir)
    passed = sum(ok for _, _, ok, _ in checks)
    print(f"Run {run_dir.name}: {passed}/{len(checks)} checks passed")
    print(f"Missions: {run_dir / 'missions'}")
    print(f"Report: {run_dir / 'check_report.md'}")
    return 0 if passed == len(checks) else 1
