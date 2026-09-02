from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    read_text,
    slug,
)
from ML.deep_research.layer3.llm import final_text
from ML.deep_research.layer3.pipeline.progress import (
    persist_run,
    restart_record,
    save_run,
    stage_event,
)
from ML.deep_research.layer3.providers import from_run
from ML.deep_research.layer3.runner import checkpoint_saver, run_stage

from .llm import (
    create_candidate_harness,
    create_external_researcher_harness,
    create_internal_harness,
    create_synthesis_harness,
)
from .prompts import (
    candidate_message,
    internal_message,
    researcher_message,
    synthesis_message,
)
from .settings import (
    DOMAIN_NAMES,
    MISSING_CANDIDATE_REPORT,
    SCHEMA_VERSION,
)


def _initial(message: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": message}]}


async def _publish(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    message: str,
    target: Path,
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> str | None:
    if record["status"] == "complete":
        if target.is_file():
            return read_text(target)
        record["status"] = "pending"

    state = await run_stage(
        graph,
        run_dir,
        run,
        record,
        retriever,
        _initial(message),
        lock,
        retry_failed=retry_failed,
    )
    if state is None:
        return None
    report = final_text(state)
    atomic_write_text(target, report)
    output_path = target.relative_to(run_dir).as_posix()
    record.update(status="complete", output_path=output_path)
    stage_event(run_dir, record, "output_publish", output_path)
    await persist_run(run_dir, run, lock)
    return report


def _restart_started(run: dict[str, Any], *records: dict[str, Any]) -> bool:
    changed = False
    for record in records:
        if record["status"] != "pending":
            restart_record(run, record)
            changed = True
    return changed


async def _run_domain(
    name: str,
    graphs: tuple[Any, Any, Any],
    run_dir: Path,
    run: dict[str, Any],
    retriever: Any,
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> tuple[str | None, bool]:
    internal_graph, candidate_graph, researcher_graph = graphs
    records = run["execution"]["domains"][name]
    domain_dir = run_dir / "domains" / slug(name)
    layer3_report = read_text(run_dir / "inputs" / "domains" / f"{slug(name)}.md")
    research_initially_complete = records["external_research"]["status"] == "complete"

    internal_target = domain_dir / "internal.md"
    await _publish(
        internal_graph,
        run_dir,
        run,
        records["internal"],
        retriever,
        internal_message(name, layer3_report),
        internal_target,
        lock,
        retry_failed=retry_failed,
    )

    candidates_target = domain_dir / "external_candidates.md"
    candidates_reused = (
        records["external_candidates"]["status"] == "complete"
        and candidates_target.is_file()
    )
    candidates = await _publish(
        candidate_graph,
        run_dir,
        run,
        records["external_candidates"],
        retriever,
        candidate_message(name, layer3_report),
        candidates_target,
        lock,
        retry_failed=retry_failed,
    )
    candidates_changed = candidates is not None and not candidates_reused
    if candidates_changed and _restart_started(run, records["external_research"]):
        await persist_run(run_dir, run, lock)
    candidate_input = candidates if candidates is not None else MISSING_CANDIDATE_REPORT

    research_target = domain_dir / "external_research.md"
    research_reused = (
        records["external_research"]["status"] == "complete"
        and research_target.is_file()
    )
    research = await _publish(
        researcher_graph,
        run_dir,
        run,
        records["external_research"],
        retriever,
        researcher_message(name, layer3_report, candidate_input),
        research_target,
        lock,
        retry_failed=retry_failed,
    )
    research_changed = (
        research_initially_complete and candidates_changed
    ) or (research is not None and not research_reused)
    return research, research_changed


async def run_external_research(
    run_dir: Path,
    *,
    retry_failed: bool = False,
) -> None:
    run = load_json(run_dir / "run.json")
    if run.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 4 schema {run.get('schema_version')!r} cannot resume in schema "
            f"{SCHEMA_VERSION}; start a fresh Layer 4 run from the Layer 3 source"
        )
    retriever = from_run(run, run_dir)
    lock = asyncio.Lock()
    run["status"] = "running"
    save_run(run_dir, run)

    reports: dict[str, str] = {}
    research_changed = False
    async with checkpoint_saver(run_dir) as saver:
        graphs = (
            create_internal_harness(run_dir, saver),
            create_candidate_harness(run_dir, saver),
            create_external_researcher_harness(run_dir, saver),
        )
        for name in DOMAIN_NAMES:
            report, changed = await _run_domain(
                name,
                graphs,
                run_dir,
                run,
                retriever,
                lock,
                retry_failed=retry_failed,
            )
            if report is not None:
                reports[name] = report
            research_changed = research_changed or changed

        final_record = run["execution"]["final"]
        if research_changed and final_record["status"] != "pending":
            restart_record(run, final_record)
            await persist_run(run_dir, run, lock)
        synthesis = await _publish(
            create_synthesis_harness(run_dir, saver),
            run_dir,
            run,
            final_record,
            retriever,
            synthesis_message(reports),
            run_dir / "research" / "final.md",
            lock,
            retry_failed=retry_failed,
        )
        if synthesis is None:
            run["status"] = "incomplete"
            save_run(run_dir, run)
            return

    run["status"] = "complete"
    save_run(run_dir, run)


__all__ = ["run_external_research"]
