from __future__ import annotations

from pathlib import Path

from ML.deep_research.layer2.fs import load_json, now_iso, slug

from ..contracts import SessionSpec
from ..mission import load_inputs
from ..providers import from_run
from ..question_files import read_questions
from ..register import read_rows, researcher_id, update_row
from ..research_tools import session_result_path
from ..sessions import run_fixture_sessions, run_online_sessions
from ..settings import LENSES, TERMINAL_STATUSES
from .state import mark_phase


async def run_second_round(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    rows = {item["row_id"]: item for item in read_rows(run_dir)}
    specs: list[SessionSpec] = []
    for mission, definition in load_inputs(run_dir):
        agent = mission["agent"]
        for lens in LENSES:
            row_id = researcher_id(agent, lens)
            questions = read_questions(
                run_dir / "questions" / slug(agent) / f"{lens}.md"
            )
            if not questions:
                update_row(
                    run_dir,
                    row_id,
                    second_status="skipped",
                    second_at=now_iso(),
                    second_questions=0,
                )
                continue
            status = rows[row_id]["second_status"]
            if status in TERMINAL_STATUSES and not retry_failed:
                continue
            thread = rows[row_id]["second_thread_id"]
            if retry_failed:
                session_result_path(run_dir, thread).unlink(missing_ok=True)
            specs.append(
                SessionSpec(
                    agent=agent,
                    lens=lens,
                    round_name="second",
                    thread_id=thread,
                    target=run_dir / "lenses" / slug(agent) / f"{lens}.md",
                    mission=mission,
                    definition=definition,
                    questions=tuple(questions),
                )
            )
    retriever = from_run(run, run_dir)
    if run["provider"] == "fixture":
        await run_fixture_sessions(run_dir, specs, retriever)
    else:
        await run_online_sessions(run_dir, specs, retriever)
    mark_phase(run_dir, 3)
