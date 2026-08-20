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
from .fs import atomic_write_text, load_json, read_text, write_json
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


async def write_missions(run_dir: Path) -> tuple[str, dict[str, int]]:
    """Step 2: hand the job to the agent and return its closing account.

    One `ainvoke` with one user message. Everything that happens inside -- how
    the sheet is read, whether helpers are spawned, how the work is checked -- is
    the agent's, and this function does not inspect or judge it.

    It does keep the final message. `agent.mission_request` asks the agent to say
    what it wrote and how it checked itself, and that answer is the *only* record
    of the self-verification: the report that follows counts files and keys and
    cannot see reasoning, and the checkpoint database is not something a human
    reads. Discarding it, as this function previously did, threw away the one
    artefact that explains whether the agent actually proved anything.

    `thread_id` is derived from the run folder name, which is what makes the run
    resumable and keeps two different properties from sharing a conversation.

    `recursion_limit` belongs in this config rather than on the agent, because
    LangGraph reads it per invocation. Without it the framework's own step
    ceiling would end a long run mid-way with nothing to show.

    Returns:
        `(the agent's final message as text, the usage summary)`. The text is
        `""` if the agent ended without one.
    """
    async with checkpoint_saver(run_dir) as saver:
        agent = create_mission_agent(run_dir, saver)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": mission_request()}]},
            config={
                "configurable": {"thread_id": f"{run_dir.name}:missions"},
                "recursion_limit": RECURSION_LIMIT,
            },
        )
    return final_message(result), usage_summary(result)


def usage_summary(result: Any) -> dict[str, int]:
    """Count what the run actually cost, from the messages it came back with.

    Recording is not limiting. Nothing here caps, rejects or retries anything --
    a run that costs ten times what this records still completes. It exists
    because Layer 2 previously recorded *nothing* about its own cost, so "how
    many model requests does a run take" could only be guessed. Layer 3 has
    `usage.jsonl`; this is Layer 2's much smaller equivalent.

    **Read the field names literally.** `top_level_model_calls` counts the
    assistant turns in the *main* agent's message list. Work done inside a
    `slice-reader` or `mission-writer` runs on its own message list and does not
    appear here, so on a delegating run the true total is higher -- possibly much
    higher. Undercounting is stated rather than hidden; a number labelled
    "model_calls" that silently omitted every subagent would be worse than none.

    Token counts come from `usage_metadata`, which providers populate
    inconsistently; a zero means "not reported", not "none used".
    """
    messages = (result or {}).get("messages") or []
    summary = {
        "top_level_model_calls": 0,
        "top_level_tool_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            summary["top_level_model_calls"] += 1
            summary["input_tokens"] += int(usage.get("input_tokens") or 0)
            summary["output_tokens"] += int(usage.get("output_tokens") or 0)
        summary["top_level_tool_calls"] += len(getattr(message, "tool_calls", None) or [])
    return summary


def final_message(result: Any) -> str:
    """Pull the text out of an agent result's last message.

    Deliberately forgiving rather than strict. Content arrives as a plain string
    on some providers and as a list of typed blocks on the Responses API, and a
    reasoning model interleaves blocks this does not want. Anything unrecognised
    yields `""` -- losing the account is a shame, but raising here would fail a
    run whose missions are already written and correct.

    This is not validation of the model's output: nothing is rejected, nothing is
    retried, and the text is never inspected for content. It is a read.
    """
    messages = (result or {}).get("messages") or []
    if not messages:
        return ""
    content = getattr(messages[-1], "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
        ]
        return "\n".join(part for part in parts if part)
    return ""


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
    account, usage = asyncio.run(write_missions(run_dir))
    _save_account(run_dir, account)
    # Written before the report, because `run_checks` loads run.json, adds its own
    # keys and writes it back -- so anything stamped here survives and anything
    # stamped after would be overwritten.
    record = load_json(run_dir / "run.json")
    record["usage"] = usage
    write_json(run_dir / "run.json", record)
    return run_checks(run_dir)


def _save_account(run_dir: Path, account: str) -> None:
    """Persist and print the agent's closing account, if it left one.

    Written beside `check_report.md` so the two sit together: what the agent says
    it did, and what the code could confirm. Printed as well, because on a run
    that a human is watching this is the part worth reading.

    An empty account is not an error -- the agent may end on a tool call -- so
    nothing is written rather than an empty file being left behind.
    """
    if not account.strip():
        return
    atomic_write_text(
        run_dir / "agent_report.md",
        f"# Run {run_dir.name} — the agent's own account\n\n"
        "What the agent says it wrote and how it says it checked itself. Its words,\n"
        "unedited. `check_report.md` beside this file is what the code could confirm.\n\n"
        f"{account.strip()}\n",
    )
    print(f"\n{account.strip()}\n", flush=True)


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
        # Resuming sends the task again -- the checkpoint continues the same
        # conversation, it does not decide that the work is done. The prompt tells
        # the agent to look at what already exists and carry on, so this is
        # usually one cheap turn rather than a full re-run. Said out loud anyway,
        # because spending money on a finished run should never be a surprise.
        if load_json(run_dir / "run.json").get("status") == "complete":
            print(
                f"Note: {run_dir.name} already reports complete. Resuming asks the "
                "agent again; it will see the existing missions.",
                flush=True,
            )
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
    if (run_dir / "agent_report.md").is_file():
        print(f"Agent account: {run_dir / 'agent_report.md'}")
    return 0 if passed == len(checks) else 1
