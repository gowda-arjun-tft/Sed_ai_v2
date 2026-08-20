from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ML.deep_research.layer2.fs import load_json, now_iso, read_text, slug

from ..aggregator_runner import invoke_structured
from ..contracts import QuestionSet
from ..llm import create_structured_agent
from ..mission import load_inputs
from ..question_files import write_question_file
from ..register import aggregator_id, increment_attempts, read_rows, update_row
from ..sessions import checkpoint_saver
from ..settings import LENSES, WORKERS
from .state import mark_phase


def _reports(run_dir: Path, agent: str) -> dict[str, str]:
    directory = run_dir / "lenses" / slug(agent)
    return {lens: read_text(directory / f"{lens}.md") for lens in LENSES}


def _write_set(run_dir: Path, agent: str, values: QuestionSet) -> None:
    for lens in LENSES:
        write_question_file(
            run_dir / "questions" / slug(agent) / f"{lens}.md",
            agent,
            lens,
            getattr(values, lens),
        )


async def write_questions(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    inputs = load_inputs(run_dir)
    if run["provider"] == "fixture":
        for mission, _ in inputs:
            _write_set(run_dir, mission["agent"], QuestionSet())
            update_row(
                run_dir,
                aggregator_id(mission["agent"]),
                first_status="answered",
                first_at=now_iso(),
                first_detail="",
                detail="",
            )
        mark_phase(run_dir, 2)
        return
    semaphore = asyncio.Semaphore(WORKERS)
    rows = {item["row_id"]: item for item in read_rows(run_dir)}
    async with checkpoint_saver(run_dir) as saver:
        agent_graph = create_structured_agent("aggregator_pass1", saver)

        async def one(mission: dict) -> None:
            name = mission["agent"]
            row_id = aggregator_id(name)
            status = rows[row_id]["first_status"]
            if not retry_failed and status in {"answered", "failed"}:
                return
            async with semaphore:
                increment_attempts(run_dir, row_id)
                update_row(run_dir, row_id, first_status="running")
                payload = (
                    f"Mission:\n{json.dumps(mission, ensure_ascii=False, indent=2)}\n\n"
                    "Five independent reports:\n"
                    + json.dumps(_reports(run_dir, name), ensure_ascii=False, indent=2)
                )
                try:
                    values = await invoke_structured(
                        agent_graph,
                        payload,
                        rows[row_id]["thread_id"],
                        QuestionSet,
                        run_dir,
                        "aggregator_pass1",
                    )
                    _write_set(run_dir, name, values)
                    update_row(
                        run_dir,
                        row_id,
                        first_status="answered",
                        first_at=now_iso(),
                        first_detail="",
                        detail="",
                    )
                except Exception as error:
                    # The failure is recorded; no empty question set is written
                    # in the aggregator's place.
                    update_row(
                        run_dir,
                        row_id,
                        first_status="failed",
                        first_at=now_iso(),
                        first_detail=f"{type(error).__name__}: {error}",
                        detail=f"{type(error).__name__}: {error}",
                    )

        await asyncio.gather(*(one(mission) for mission, _ in inputs))
    mark_phase(run_dir, 2)
