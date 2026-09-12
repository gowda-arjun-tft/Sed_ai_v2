"""Persistent independent domain graphs, bounded native scheduling and immediate publication."""

import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from openai import AsyncOpenAI

from ML.deep_research.layer2.ML.harness import build_model, configure_harness
from ML.deep_research.layer2.backend.fs import atomic_write_text, load_json, text_hash, write_json
from ML.deep_research.layer2.backend.run_log import log_failure, operational_logger, stop_progress, waiting_progress
from .domain_tools import make_tools
from .pipeline.create_run import local_path, require_current, verify_inputs
from .research_documents import ResearchDocuments
from .research_memory import ResearchGuard, ResearchSummarization, ResearchTrace, file_middleware, memory_backend
from .research_run import checkpoint_path, eligible_sources
from .research_budget import BudgetExhausted, CallBudget
from .research_handoff import seed_prior_work
from .source_publication import _view, parse_json, publish


def prepare_domain(run, record, domain, checkpoint_dir):
    """Freeze each initial research context once, independently of later upload availability changes."""
    research = record["research"]
    key = domain["key"]
    identifier = text_hash(key)[:24]
    root = run / "_internal/trace/research" / identifier
    frozen = {key: record[key] for key in ("model", "web_search", "reasoning_effort", "timeout_seconds", "provider_max_retries", "inputs")}
    policy = {k: v for k, v in research.items() if k not in {"jobs", "status", "counts", "elapsed_seconds"}}
    entry = research["jobs"].get(key)
    if entry:
        context = (root / "inputs/context.md").read_text(encoding="utf-8")
        if text_hash(context) != entry["input_sha256"]:
            raise ValueError("Frozen researcher context changed")
        sources = (root / "inputs/sources.json").read_text(encoding="utf-8")
        if text_hash(sources) != entry["sources_sha256"]:
            raise ValueError("Frozen researcher sources changed")
        if text_hash(json.dumps([text_hash(context), frozen, policy], sort_keys=True)) != entry["fingerprint"]:
            raise ValueError("Frozen research dependencies changed; create a new linked run")
        return root, entry, context, parse_json(sources)
    sources = eligible_sources(run, record, domain)
    content = "\n\n".join((
        "<domain>\n" + local_path(run, domain["input_path"]).read_text(encoding="utf-8-sig") + "\n</domain>",
        "<asset_metadata>\n" + (run / "_internal/inputs/asset_metadata.md").read_text(encoding="utf-8-sig") + "\n</asset_metadata>",
        "<eligible_sources>\n" + sources + "\n</eligible_sources>"))
    if research["version"] >= 2:
        instruction = (run / "_internal/inputs/user_research_instruction.md").read_text(encoding="utf-8-sig")
        atomic_write_text(root / "inputs/user_research_instruction.md", instruction)
        content += seed_prior_work(run, record, domain, root)
    atomic_write_text(root / "inputs/context.md", content)
    atomic_write_text(root / "inputs/sources.json", sources)
    fingerprint = text_hash(json.dumps([text_hash(content), frozen, policy], sort_keys=True))
    entry = {"status": "pending", "thread_id": uuid4().hex, "fingerprint": fingerprint,
             "input_sha256": text_hash(content), "sources_sha256": text_hash(sources),
             "root": root.relative_to(run).as_posix(), "checkpoint_path": str(checkpoint_path(record, domain, checkpoint_dir)),
             "output_path": "research/" + Path(domain["output_path"]).with_suffix(".md").name,
             "attempt": 0, "checkpoint_started": False}
    research["jobs"][key] = entry
    write_json(run / "run.json", record)
    return root, entry, content, parse_json(sources)


def reuse_final(run, root, entry):
    """Recover durable final output even if interruption preceded the run-record or view write."""
    receipt = root / "final.json"
    if not receipt.exists():
        if entry["status"] == "complete":
            raise ValueError("Completed research receipt is missing; restore preserved records")
        return False
    saved = load_json(receipt)
    raw = (root / "response.md").read_text(encoding="utf-8")
    if saved["fingerprint"] != entry["fingerprint"] or saved["sha256"] != text_hash(raw):
        raise ValueError("Research response or dependency fingerprint changed")
    _view(run, entry["output_path"], raw)
    entry.update(status="complete", reused=True, response_sha256=saved["sha256"], empty_response=not bool(raw.strip()))
    return True


def build_agent(run, record, root, entry, tools, saver, logger, budget=None, clients=None):
    """Assemble the installed native loop without shell, delegation, repair or loop-budget middleware."""
    configure_harness()
    model = build_model(record["research"]["reasoning_effort"],
                        max_retries=record["provider_max_retries"], timeout=record["timeout_seconds"], **(clients or {}))
    backend = memory_backend(root)
    files = file_middleware(backend)
    prompt_root = run / "_internal/inputs/prompts"
    prompt = (prompt_root / "domain_research.md").read_text(encoding="utf-8")
    if record["research"]["version"] >= 2:
        # Task instructions stay active through compaction, unlike evidence or old dialogue.
        prompt += "\n\n# Selected user research instruction\n\n" + (
            run / "_internal/inputs/user_research_instruction.md").read_text(encoding="utf-8-sig")
    middleware = [files, TodoListMiddleware(),
                  ResearchSummarization(model, backend, record,
                                        (prompt_root / "research_summary.md").read_text(encoding="utf-8"), logger, budget),
                  ResearchGuard(record, root, entry["fingerprint"], logger, budget)]
    graph = create_deep_agent(model=model, tools=tools, backend=backend, middleware=middleware,
                              subagents=[], checkpointer=saver, response_format=None,
                              system_prompt=prompt,
                              name="domain-research")
    return graph, files, model


async def _domain(run, record, domain, checkpoint_dir, documents, logger, retry_failed, starts, clients):
    """Own one checkpoint connection and publish one domain without gating successful siblings."""
    key, began = domain["key"], time.perf_counter()
    budget = None
    entry = record["research"]["jobs"].setdefault(key, {"status": "pending"})
    # Remove a new placeholder; prepare_domain atomically fills its actual identities.
    if "root" not in entry:
        record["research"]["jobs"].pop(key)
    try:
        root, entry, context, sources = prepare_domain(run, record, domain, checkpoint_dir)
        if reuse_final(run, root, entry):
            logger.info("research_reused domain=%s", key)
            return
        if entry["status"] == "failed" and not retry_failed:
            return
        budget = (CallBudget(root, record["research"], entry, logger, lambda: write_json(run / "run.json", record))
                  if record["research"]["version"] >= 2 else None)
        if budget and budget.phase == "exhausted":
            raise BudgetExhausted("No remaining logical calls; retained work is available")
        checkpoint = checkpoint_path(record, domain, checkpoint_dir)
        if str(checkpoint) != entry["checkpoint_path"]:
            raise ValueError("Frozen checkpoint path changed")
        if entry["checkpoint_started"] and not checkpoint.is_file():
            raise RuntimeError("Research checkpoint missing; restore its Docker volume before resuming")
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        documents.authorize(key, sources)
        trace = ResearchTrace(root / "trace", entry["thread_id"], logger, key)
        entry.update(status="running", attempt=entry["attempt"] + 1, reused=False)
        starts[key] = time.perf_counter()
        write_json(run / "run.json", record)
        logger.info("research_started domain=%s thread=%s attempt=%d", key, entry["thread_id"], entry["attempt"])
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint)) as saver:
            await saver.setup()
            graph, files, model = build_agent(run, record, root, entry,
                                              make_tools(root, record, key, documents, budget), saver, logger, budget, clients)
            config = {"configurable": {"thread_id": entry["thread_id"]}, "recursion_limit": sys.maxsize,
                      "callbacks": [trace], "metadata": {"lc_agent_name": key}, "max_concurrency": 5}
            try:
                snapshot = await graph.aget_state(config)
                logger.info("checkpoint_loaded domain=%s thread=%s present=%s pending_nodes=%d",
                            key, entry["thread_id"], bool(snapshot.values), len(snapshot.next))
                if entry["checkpoint_started"] and not snapshot.values:
                    raise RuntimeError("Research checkpoint has no resumable thread state")
                entry["checkpoint_started"] = True
                write_json(run / "run.json", record)
                result = (snapshot.values if snapshot.values and not snapshot.next else
                          await graph.ainvoke(None if snapshot.values else {"messages": [HumanMessage(content=context)]},
                                              config=config))
                logger.info("checkpoint_saved domain=%s thread=%s", key, entry["thread_id"])
                # Keep private notes/plans visible to recovery diagnostics without making them a completion gate.
                write_json(root / "working_state.json", {"todos": result.get("todos", []), "files": result.get("files", {})})
                if not reuse_final(run, root, entry):
                    raise RuntimeError("Research graph ended without a durable assistant completion")
                logger.info("research_response_saved domain=%s", key)
            finally:
                files._glob_executor.shutdown(wait=True, cancel_futures=True)
    except asyncio.CancelledError:
        entry.update(status="interrupted")
        raise
    except BudgetExhausted as error:
        entry.update(status="budget_exhausted", error_type=type(error).__name__)
        logger.warning("research_budget_exhausted domain=%s thread=%s", key, entry.get("thread_id"))
    except Exception as error:
        entry.update(status="budget_exhausted" if budget and budget.phase == "exhausted" else "failed",
                     error_type=type(error).__name__)
        log_failure(logger, "research_failed", error, domain=key, thread=entry.get("thread_id"))
    finally:
        entry["elapsed_seconds"] = round(time.perf_counter() - began, 3)
        if entry.get("root"):
            work = local_path(run, entry["root"])
            entry["observed_calls"] = {
                "model_requests": len(list((work / "trace").glob("model-*-input.json"))),
                "tool_calls": len(list((work / "trace").glob("tool-*-input.json"))),
                "search_completions": len(list((work / "evidence/search").glob("*/usage.json"))),
                "document_read_completions": len(list((work / "evidence/documents").glob("*/usage.json")))}
        record["research"]["jobs"][key] = entry
        write_json(run / "run.json", record)
        publish(run)
        logger.info("research_finished domain=%s status=%s elapsed_seconds=%.3f observed_calls=%s",
                    key, entry["status"], entry["elapsed_seconds"], entry.get("observed_calls", {}))


async def run_domains(run, checkpoint_dir, *, retry_failed=False):
    """Run frozen native batches (one domain for version 2), retaining siblings on cancellation."""
    record = require_current(run)
    verify_inputs(run, record)
    started = time.perf_counter()
    policy = record["research"]
    policy["status"], record["status"] = "running", "running"
    write_json(run / "run.json", record)
    with operational_logger(run) as logger:
        workers, starts = set(), {}
        outstanding = {d["key"] for d in record["domains"]}
        progress = asyncio.create_task(waiting_progress(logger, "domain_research", outstanding, starts, started))
        try:
            with httpx.Client(timeout=record["timeout_seconds"]) as sync_client:
                async with httpx.AsyncClient(timeout=record["timeout_seconds"]) as async_client:
                    clients = {"http_client": sync_client, "http_async_client": async_client}
                    await _execute_domains(run, record, checkpoint_dir, retry_failed, logger, workers, starts, outstanding, clients)
            complete = sum(j.get("status") == "complete" for j in policy["jobs"].values())
            policy["status"] = "complete" if complete == len(record["domains"]) else "partial"
            record["status"] = "complete" if policy["status"] == "complete" and record.get("discovery_status") == "complete" else "partial"
        except asyncio.CancelledError:
            policy["status"], record["status"] = "interrupted", "interrupted"
            raise
        except Exception as error:
            policy["status"], record["status"] = "partial", "partial"
            log_failure(logger, "research_stage_failed", error)
            raise
        finally:
            await stop_progress(progress)
            policy["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            policy["counts"] = {status: sum(j.get("status") == status for j in policy["jobs"].values())
                                for status in ("complete", "failed", "interrupted", "budget_exhausted")}
            write_json(run / "run.json", record)
            publish(run)
            logger.info("research_stage_finished status=%s counts=%s elapsed_seconds=%.3f",
                        policy["status"], policy["counts"], policy["elapsed_seconds"])


async def _execute_domains(run, record, checkpoint_dir, retry_failed, logger, workers, starts, outstanding, clients):
    """Keep clients alive across all domains; the frozen policy retains historical concurrency."""
    policy = record["research"]
    async with AsyncOpenAI(timeout=record["timeout_seconds"], max_retries=record["provider_max_retries"]) as client:
        documents = ResearchDocuments(run, record, client, logger)

        async def invoke(domain):
            """Track native workers so closing the completion iterator cannot leave live writers."""
            task = asyncio.current_task()
            workers.add(task)
            try:
                await _domain(run, record, domain, checkpoint_dir, documents, logger, retry_failed, starts, clients)
            finally:
                workers.discard(task)
                outstanding.discard(domain["key"])

        for start in range(0, len(record["domains"]), policy["max_concurrency"]):
            batch = record["domains"][start:start + policy["max_concurrency"]]
            stream = RunnableLambda(invoke).abatch_as_completed(batch, {"max_concurrency": policy["max_concurrency"]},
                                                               return_exceptions=True)
            try:
                async for _, result in stream:
                    if isinstance(result, BaseException):
                        raise result
            finally:
                await stream.aclose()
                active = list(workers)
                for task in active:
                    task.cancel()
                await asyncio.gather(*active, return_exceptions=True)
