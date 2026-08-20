from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    read_text,
    slug,
    write_json,
)

from ..aggregator_runner import invoke_structured
from ..contracts import AnswerDraft, GapDecision, SessionSpec
from ..llm import create_structured_agent
from ..mission import load_inputs
from ..providers import from_run
from ..register import (
    add_sixth_row,
    aggregator_id,
    increment_attempts,
    read_rows,
    researcher_id,
    row as register_row,
    thread_id,
    update_row,
)
from ..research_tools import session_result_path
from ..sessions import checkpoint_saver, run_online_sessions
from ..settings import LENSES, WORKERS
from .state import mark_phase


def _base_reports(run_dir: Path, agent: str) -> dict[str, str]:
    root = run_dir / "lenses" / slug(agent)
    return {lens: read_text(root / f"{lens}.md") for lens in LENSES}


def _write_answer(run_dir: Path, agent: str, body: str) -> None:
    """Write the answer exactly as the aggregator wrote it.

    No title is prepended and no disclosure is appended. If either belongs in
    the answer, the aggregator's prompt asks for it and the aggregator writes it.
    """
    atomic_write_text(run_dir / "research" / f"{slug(agent)}.md", body)


def _fixture_answers(run_dir: Path) -> None:
    for mission, _ in load_inputs(run_dir):
        agent = mission["agent"]
        write_json(
            run_dir / "gap_decisions" / f"{slug(agent)}.json",
            GapDecision(needed=False).model_dump(),
        )
        _write_answer(
            run_dir,
            agent,
            "The offline fixture produced no citable evidence for this subject. "
            "The result remains cannot be answered until suitable public sources are supplied.",
        )
        update_row(
            run_dir,
            aggregator_id(agent),
            second_status="answered",
            second_at=now_iso(),
            second_detail="",
            detail="",
        )


async def _collect_gaps(run_dir: Path, pending: list[dict]) -> dict[str, GapDecision]:
    run = load_json(run_dir / "run.json")
    semaphore = asyncio.Semaphore(WORKERS)
    decisions: dict[str, GapDecision] = {}
    async with checkpoint_saver(run_dir) as saver:
        graph = create_structured_agent("gap_decision", saver)

        async def one(mission: dict) -> None:
            agent = mission["agent"]
            row_id = aggregator_id(agent)
            async with semaphore:
                try:
                    decision = await invoke_structured(
                        graph,
                        "Mission and five completed reports:\n"
                        + json.dumps(
                            {"mission": mission, "reports": _base_reports(run_dir, agent)},
                            ensure_ascii=False,
                            indent=2,
                        ),
                        thread_id(run["run_id"], row_id, "gap"),
                        GapDecision,
                        run_dir,
                        "gap_decision",
                    )
                except Exception as error:
                    decision = GapDecision(needed=False)
                    current = register_row(run_dir, row_id)
                    reason = f"Gap scan failed: {type(error).__name__}: {error}"
                    update_row(
                        run_dir,
                        row_id,
                        second_detail=reason,
                        detail="; ".join(
                            filter(None, (current.get("first_detail", ""), reason))
                        ),
                    )
                decisions[agent] = decision
                write_json(
                    run_dir / "gap_decisions" / f"{slug(agent)}.json",
                    decision.model_dump(),
                )

        await asyncio.gather(*(one(mission) for mission in pending))
    return decisions


def _sixth_specs(
    run_dir: Path,
    decisions: dict[str, GapDecision],
    inputs: list[tuple[dict, dict]],
    retry_failed: bool,
) -> list[SessionSpec]:
    run = load_json(run_dir / "run.json")
    rows = {item["row_id"]: item for item in read_rows(run_dir)}
    existing_sixth = {
        item["agent"]: item
        for item in rows.values()
        if item["row_type"] == "researcher" and item["lens"] not in LENSES
    }
    specs = []
    for mission, _ in inputs:
        agent = mission["agent"]
        decision = decisions.get(agent, GapDecision(needed=False))
        name = decision.name
        # The name is kept verbatim in the register and the report. The only
        # thing checked here is that it does not resolve to the same file as one
        # of the five base lenses, which would overwrite that lens's report.
        if not decision.needed or not slug(name) or slug(name) in {
            slug(item) for item in LENSES
        }:
            continue
        if agent in existing_sixth:
            name = existing_sixth[agent]["lens"]
        status_row = rows.get(researcher_id(agent, name))
        status = status_row["first_status"] if status_row else "never started"
        if status in {"answered", "failed"} and not retry_failed:
            continue
        # Only claim the register row once the session is actually going to run,
        # so an interrupted phase cannot strand a row with no lens file.
        new_row = add_sixth_row(run_dir, run["run_id"], agent, name)
        if retry_failed:
            session_result_path(run_dir, new_row["thread_id"]).unlink(missing_ok=True)
        specs.append(
            SessionSpec(
                agent=agent,
                lens=name,
                focus=decision.focus,
                round_name="first",
                thread_id=new_row["thread_id"],
                target=run_dir / "lenses" / slug(agent) / f"{slug(name)}.md",
                mission=mission,
                definition={
                    "name": agent,
                    "establishes": [decision.focus],
                    "do_not_cover": [],
                    "take_as_given": [],
                    "web_sources": [],
                },
            )
        )
    return specs


async def _write_online_answers(
    run_dir: Path,
    pending: list[dict],
    decisions: dict[str, GapDecision],
) -> None:
    run = load_json(run_dir / "run.json")
    semaphore = asyncio.Semaphore(WORKERS)
    async with checkpoint_saver(run_dir) as saver:
        graph = create_structured_agent("aggregator_pass2", saver)

        async def one(mission: dict) -> None:
            agent = mission["agent"]
            row_id = aggregator_id(agent)
            async with semaphore:
                increment_attempts(run_dir, row_id)
                update_row(run_dir, row_id, second_status="running")
                reports = _base_reports(run_dir, agent)
                decision = decisions.get(agent, GapDecision(needed=False))
                if decision.needed:
                    sixth = run_dir / "lenses" / slug(agent) / f"{slug(decision.name)}.md"
                    if sixth.is_file():
                        reports[decision.name] = read_text(sixth)
                payload = json.dumps(
                    {"mission": mission, "reports": reports},
                    ensure_ascii=False,
                    indent=2,
                )
                try:
                    draft = await invoke_structured(
                        graph,
                        payload,
                        thread_id(run["run_id"], row_id, "answer"),
                        AnswerDraft,
                        run_dir,
                        "aggregator_pass2",
                    )
                    _write_answer(run_dir, agent, draft.markdown)
                    current = register_row(run_dir, row_id)
                    update_row(
                        run_dir,
                        row_id,
                        second_status="answered",
                        second_at=now_iso(),
                        second_detail="",
                        detail=current.get("first_detail", ""),
                    )
                except Exception as error:
                    # The failure is recorded in the register. No stub answer is
                    # written in the aggregator's place.
                    reason = f"{type(error).__name__}: {error}"
                    current = register_row(run_dir, row_id)
                    update_row(
                        run_dir,
                        row_id,
                        second_status="failed",
                        second_at=now_iso(),
                        second_detail=reason,
                        detail="; ".join(
                            filter(None, (current.get("first_detail", ""), reason))
                        ),
                    )

        await asyncio.gather(*(one(mission) for mission in pending))


async def write_answers(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    if run["provider"] == "fixture":
        _fixture_answers(run_dir)
        mark_phase(run_dir, 4)
        return
    inputs = load_inputs(run_dir)
    rows = {item["row_id"]: item for item in read_rows(run_dir)}
    pending = [
        mission
        for mission, _ in inputs
        if rows[aggregator_id(mission["agent"])]["second_status"] != "answered"
        or retry_failed
    ]
    decisions = await _collect_gaps(run_dir, pending)
    sixth = _sixth_specs(run_dir, decisions, inputs, retry_failed)
    await run_online_sessions(run_dir, sixth, from_run(run, run_dir))
    await _write_online_answers(run_dir, pending, decisions)
    mark_phase(run_dir, 4)
