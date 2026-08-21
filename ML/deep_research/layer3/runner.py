from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any, AsyncIterator

from ML.deep_research.layer2.fs import atomic_write_text, load_json, now_iso, read_text, slug

from .contracts import ResearchContext, ResearchOutcome, ReviewOutcome
from .llm import create_domain_harness, create_reviewer_harness, create_synthesis_harness, final_text, structured_value
from .mission import load_research_input
from .pipeline.progress import (
    fail_record,
    model_turns,
    persist_run,
    retry_record,
    save_run,
    stage_event,
    stage_record,
)
from .prompts import domain_message, review_message, synthesis_message
from .providers import from_run
from .research_tools import read_partial_report
from .settings import DOMAIN_NAMES, SCHEMA_VERSION
from .usage import UsageCallback


_CLARIFICATION_HEADING = "\n\n## Clarification\n\n"


@asynccontextmanager
async def checkpoint_saver(run_dir: Path) -> AsyncIterator[Any]:
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite3")) as saver:
        await saver.setup()
        yield saver


def _virtual_files(reports: dict[str, str], review: str = "") -> dict[str, dict[str, str]]:
    files = {f"/domains/{slug(name)}.md": {"content": text} for name, text in reports.items()}
    if review:
        files["/review.md"] = {"content": review}
    return files


async def _run_stage(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    initial: dict[str, Any],
    schema: type | None,
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
) -> dict[str, Any] | None:
    if record["status"] == "complete":
        snapshot = await graph.aget_state({"configurable": {"thread_id": record["thread_id"]}})
        if snapshot.values and not snapshot.next:
            return snapshot.values
        await fail_record(run_dir, run, record, "completed stage checkpoint is unavailable", lock)
        return None
    if record["status"] == "failed":
        if not retry_failed:
            return None
        retry_record(run, record)

    thread_id = record["thread_id"]
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [UsageCallback(run_dir, thread_id)],
        "metadata": {"run_id": run["run_id"], "agent": record["actor"]},
    }
    context = ResearchContext(run_dir, record["actor"], thread_id, retriever)
    started = monotonic()
    record.update(status="running", error="", updated_at=now_iso())
    stage_event(run_dir, record, "stage_start")
    await persist_run(run_dir, run, lock)
    try:
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            result = (
                await graph.ainvoke(None, config=config, context=context)
                if snapshot.next
                else snapshot.values
            )
        else:
            result = await graph.ainvoke(initial, config=config, context=context)
        outcome = structured_value(result, schema) if schema else None
        record.update(
            status="staged",
            outcome=getattr(outcome, "status", "complete"),
            reason=getattr(outcome, "reason", ""),
            unknowns=list(getattr(outcome, "unknowns", [])),
            error="",
        )
        stage_event(run_dir, record, "stage_result")
        return result
    except Exception as error:
        await fail_record(run_dir, run, record, error, lock)
        return None
    finally:
        record.update(
            model_turns=model_turns(run_dir, thread_id),
            elapsed_seconds=round(monotonic() - started, 3),
            updated_at=now_iso(),
        )
        await persist_run(run_dir, run, lock)


def _questions(outcome: ReviewOutcome) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in outcome.questions:
        if item.domain not in DOMAIN_NAMES:
            raise ValueError(f"review returned an unknown domain: {item.domain}")
        if item.domain in result:
            raise ValueError(f"review returned duplicate domain questions: {item.domain}")
        values = [question.strip() for question in item.questions if question.strip()]
        if values:
            result[item.domain] = values
    return result


def _clarification(run: dict[str, Any], questions: dict[str, list[str]]) -> dict[str, Any]:
    existing = run["execution"].get("clarification")
    if existing is not None:
        return existing
    item = {
        "questions": questions,
        "domains": {
            name: stage_record(run, "clarification", name, 1) for name in questions
        },
    }
    run["execution"]["clarification"] = item
    return item


async def _publish_domain(
    graph: Any,
    run_dir: Path,
    run: dict[str, Any],
    record: dict[str, Any],
    retriever: Any,
    initial: dict[str, Any],
    lock: asyncio.Lock,
    *,
    retry_failed: bool,
    base_report: str = "",
) -> str | None:
    target = run_dir / "domains" / f"{slug(record['actor'])}.md"
    if record["status"] == "complete" and target.is_file() and read_text(target).strip():
        return read_text(target)
    state = await _run_stage(
        graph, run_dir, run, record, retriever, initial, ResearchOutcome, lock,
        retry_failed=retry_failed,
    )
    if state is None:
        return None
    attempt_report = read_partial_report(
        run_dir, record["actor"], record["thread_id"]
    )
    if not attempt_report.strip():
        await fail_record(run_dir, run, record, "completed domain has no progressive report", lock)
        return None
    report = (
        base_report.rstrip() + _CLARIFICATION_HEADING + attempt_report
        if base_report
        else attempt_report
    )
    atomic_write_text(target, report)
    record.update(status="complete", artifact=str(target.relative_to(run_dir)).replace("\\", "/"))
    stage_event(run_dir, record, "report_publish", record["artifact"])
    await persist_run(run_dir, run, lock)
    return report


def commit_outputs(run_dir: Path, reports: dict[str, str], review: str, answer: str) -> None:
    """Gate the final answer on all published domains and the written review."""
    if set(reports) != set(DOMAIN_NAMES) or not all(text.strip() for text in reports.values()):
        raise ValueError("all eight published domain reports are required")
    if not review.strip() or not answer.strip():
        raise ValueError("the completed review and final answer are required")
    if any(
        not (run_dir / "domains" / f"{slug(name)}.md").is_file()
        or read_text(run_dir / "domains" / f"{slug(name)}.md") != text
        for name, text in reports.items()
    ):
        raise ValueError("published domain reports do not match the synthesis inputs")
    atomic_write_text(run_dir / "research" / "final.md", answer)


async def run_research(run_dir: Path, *, retry_failed: bool = False) -> None:
    run = load_json(run_dir / "run.json")
    if run.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 3 schema {run.get('schema_version')!r} cannot resume in schema {SCHEMA_VERSION}; "
            "start a fresh Layer 3 run from the completed Layer 2 run"
        )
    retriever = from_run(run, run_dir)
    assignments = {item["name"]: item for item in load_research_input(run_dir)}
    lock = asyncio.Lock()
    run["status"] = "running"
    save_run(run_dir, run)

    async with checkpoint_saver(run_dir) as saver:
        graphs = {name: create_domain_harness(run_dir, name, saver) for name in DOMAIN_NAMES}
        initial = await asyncio.gather(
            *(
                _publish_domain(
                    graphs[name], run_dir, run, run["execution"]["domains"][name], retriever,
                    {"messages": [{"role": "user", "content": domain_message(assignments[name], batch=0)}]},
                    lock, retry_failed=retry_failed,
                )
                for name in DOMAIN_NAMES
            )
        )
        if any(report is None for report in initial):
            run["status"] = "incomplete"
            save_run(run_dir, run)
            return
        reports = dict(zip(DOMAIN_NAMES, initial, strict=True))

        review_record = run["execution"]["review"]
        review_path = run_dir / "review" / "final_review.md"
        if review_record["status"] == "complete" and review_path.is_file():
            review = read_text(review_path)
            questions = review_record.get("questions", {})
        else:
            review_state = await _run_stage(
                create_reviewer_harness(run_dir, saver), run_dir, run, review_record, retriever,
                {"messages": [{"role": "user", "content": review_message()}], "files": _virtual_files(reports)},
                ReviewOutcome, lock, retry_failed=retry_failed,
            )
            if review_state is None:
                run["status"] = "incomplete"
                save_run(run_dir, run)
                return
            outcome = structured_value(review_state, ReviewOutcome)
            try:
                questions = _questions(outcome)
                review = outcome.review_markdown
                if not review.strip():
                    raise ValueError("review markdown cannot be empty")
            except ValueError as error:
                await fail_record(run_dir, run, review_record, error, lock)
                run["status"] = "incomplete"
                save_run(run_dir, run)
                return
            atomic_write_text(review_path, review)
            review_record.update(status="complete", questions=questions)
            stage_event(run_dir, review_record, "review_publish", "review/final_review.md")
            await persist_run(run_dir, run, lock)

        if questions:
            clarification = _clarification(run, questions)
            save_run(run_dir, run)
            followups = await asyncio.gather(
                *(
                    _publish_domain(
                        graphs[name], run_dir, run, clarification["domains"][name], retriever,
                        {"messages": [{"role": "user", "content": domain_message(
                            assignments[name], batch=1, questions=items, previous_report=reports[name]
                        )}]},
                        lock,
                        retry_failed=retry_failed,
                        base_report=reports[name],
                    )
                    for name, items in questions.items()
                )
            )
            if any(report is None for report in followups):
                run["status"] = "incomplete"
                save_run(run_dir, run)
                return
            reports.update(zip(questions, followups, strict=True))

        final_record = run["execution"]["final"]
        final_path = run_dir / "research" / "final.md"
        if final_record["status"] != "complete" or not final_path.is_file():
            final_state = await _run_stage(
                create_synthesis_harness(run_dir, saver), run_dir, run, final_record, retriever,
                {"messages": [{"role": "user", "content": synthesis_message()}], "files": _virtual_files(reports, review)},
                None, lock, retry_failed=retry_failed,
            )
            if final_state is None:
                run["status"] = "incomplete"
                save_run(run_dir, run)
                return
            try:
                answer = final_text(final_state)
                commit_outputs(run_dir, reports, review, answer)
            except ValueError as error:
                await fail_record(run_dir, run, final_record, error, lock)
                run["status"] = "incomplete"
                save_run(run_dir, run)
                return
            final_record.update(status="complete", outcome="answered", reason="")
            stage_event(run_dir, final_record, "answer_publish", "research/final.md")
            await persist_run(run_dir, run, lock)

    run["status"] = "complete"
    save_run(run_dir, run)
