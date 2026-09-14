"""Direct calls with immediate raw persistence and dependency-versioned recovery."""

import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import AIMessage

from ..ML.context import InputSizeError, estimate, messages, request_options
from .fs import atomic_write_text, load_json, now_iso, text_hash, write_json
from .run_log import DispatchLog, diagnostic_identifier, log_failure, stop_progress, waiting_progress
from .usage import UsageCallback


class IncompleteResponseError(RuntimeError):
    """The provider reported an incomplete completion; its received text remains preserved."""


def saved_text(path: Path) -> str | None:
    """Input a saved Markdown path; return exact text, including empty text, or unreadable None."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeError):
        return None


def saved_entry(run: Path, key: str, fingerprint: str, previous: dict) -> dict:
    """Input a dependency version; recover its recorded completion even after an interrupted resume."""
    old = previous.get(key, {})
    if old.get("fingerprint") == fingerprint:
        try:
            completed = load_json((run / old["response_path"]).with_name("completion.json"))
            return {**old, **completed}
        except (OSError, ValueError, KeyError, TypeError):
            return dict(old)
    folder = run / "_internal/trace/responses" / key / fingerprint
    for path in sorted(folder.glob("*/completion.json"), reverse=True):
        try:
            entry = load_json(path)
            if entry["status"] == "complete" and saved_text(run / entry["response_path"]) is not None:
                return entry
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return {"attempt": 0}


async def run_jobs(run: Path, model, stage: str, sections: list[dict], previous: dict,
                   logger, *, offset: int = 0) -> list[Path]:
    """Input one bounded stage batch; persist direct completions and return source-ordered paths."""
    record = load_json(run / "run.json")
    prompt = saved_text(run / "_internal/inputs/prompts" / f"{stage}.md")
    policy = record["context_policy"]
    profile = getattr(model, "profile", None) or {}
    capacity = min(record["model_input_token_limit"],
                   profile.get("max_input_tokens") or record["model_input_token_limit"])
    ceiling = min(policy["maximum_tokens"], capacity)
    options = request_options(stage, record)
    if stage == "design":
        ceiling = min(ceiling, record["web_search"]["input_token_limit"])
    caller = model.bind(**options) if options else model
    frozen = {key: record[key] for key in ("model", "reasoning_effort", "provider_max_retries",
                                          "chunking", "context_policy", "model_input_token_limit",
                                          "public_input_confirmed", "web_search")}
    results, inputs, configs, pending, starts = {}, [], [], [], {}
    for index, context in enumerate(sections):
        key = f"{stage}/{offset + index + 1:06d}"
        request = messages(prompt, context)
        fingerprint = text_hash(json.dumps([frozen, options, [text_hash(m.content) for m in request]],
                                          sort_keys=True))
        entry = saved_entry(run, key, fingerprint, previous)
        entry.update(stage=stage, fingerprint=fingerprint, updated_at=now_iso(), reused=False)
        record["jobs"][key] = entry
        path = run / entry["response_path"] if entry.get("response_path") else None
        text = saved_text(path) if path else None
        if text is not None and entry.get("error_type") != "IncompleteResponseError":
            entry.update(status="complete", error_type="", response_sha256=text_hash(text), reused=True)
            results[index] = path
            logger.info("job_reused stage=%s job=%s attempt=%d", stage, key, entry["attempt"])
            continue
        attempt = entry["attempt"] + 1
        folder = run / "_internal/trace/responses" / key / fingerprint
        while (folder / f"{attempt:03d}").exists():
            attempt += 1
        for field in ("response_sha256", "response_id", "provider", "elapsed_seconds", "web_search_actions"):
            entry.pop(field, None)
        entry.update(attempt=attempt, status="running", error_type="",
                     request_id=str(uuid4()))
        suffix = "md" if stage == "metadata" else "json"
        relative = f"_internal/trace/responses/{key}/{fingerprint}/{entry['attempt']:03d}/response.{suffix}"
        entry["response_path"] = relative
        count = estimate(request, policy["framing_reserve"], options)
        reason = "complete mandatory context" if count > policy["target_tokens"] else "normal"
        entry.update(input_estimate=count, input_estimate_reason=reason, input_ceiling=ceiling)
        logger.info("job_scheduled stage=%s job=%s attempt=%d request_id=%s input_estimate=%d reason=%s",
                    stage, key, entry["attempt"], entry["request_id"], count, reason)
        if count > ceiling:
            entry.update(status="failed", error_type="InputSizeError")
            record["current_stage"] = stage
            # Earlier items in this batch were prepared but have not been dispatched.
            for _, pending_key, _ in pending:
                record["jobs"][pending_key]["status"] = "pending"
            write_json(run / "run.json", record)
            raise InputSizeError(f"assembled input estimate {count} exceeds effective ceiling {ceiling}")
        scheduled = time.perf_counter()
        config = {"run_id": uuid4(), "max_concurrency": record["chunking"]["max_concurrency"],
                  "metadata": {"lc_agent_name": f"layer2-{stage}", "job": key},
                  "callbacks": [UsageCallback(run / "_internal/trace", entry["request_id"]),
                                DispatchLog(logger, stage, key, scheduled, starts)]}
        entry["callback_run_id"] = str(config["run_id"])
        inputs.append(request)
        configs.append(config)
        pending.append((index, key, scheduled))
    record.update(status="running", current_stage=stage)
    write_json(run / "run.json", record)
    if not pending:
        return [results[index] for index in sorted(results)]
    returned = set()
    outstanding = {key for _, key, _ in pending}
    progress = asyncio.create_task(waiting_progress(logger, stage, outstanding, starts, time.perf_counter()))
    try:
        if stage == "distribution":
            completions = caller.abatch_as_completed(inputs, configs, return_exceptions=True)
        else:
            completions = sequential_call(caller, inputs[0], configs[0])
        async for batch_index, result in completions:
            index, key, started = pending[batch_index]
            entry = record["jobs"][key]
            returned.add(key)
            outstanding.discard(key)
            try:
                if isinstance(result, Exception):
                    raise result
                if not isinstance(result, AIMessage):
                    raise TypeError("direct model call did not return an assistant message")
                path = run / entry["response_path"]
                blocks = [block for block in result.content if isinstance(block, dict)] if isinstance(result.content, list) else []
                blocks += result.additional_kwargs.get("tool_outputs") or []
                entry["web_search_actions"] = sum(block.get("type") == "web_search_call"
                                                  for block in blocks if isinstance(block, dict))
                info = result.response_metadata
                entry.update(response_sha256=text_hash(result.text), response_id=result.id,
                             provider={key: info[key] for key in ("id", "model_name", "finish_reason",
                                       "status", "incomplete_details") if key in info})
                incomplete = info.get("status") == "incomplete" or info.get("finish_reason") == "length"
                entry.update(status="failed" if incomplete else "complete",
                             error_type="IncompleteResponseError" if incomplete else "",
                             elapsed_seconds=round(time.perf_counter() - started, 3))
                # Record provider completion before exposing text so a crash cannot promote partial output.
                write_json(path.with_name("completion.json"), entry)
                atomic_write_text(path, result.text)
                logger.info("response_saved stage=%s job=%s path=%s", stage, key, entry["response_path"])
                if stage == "design":
                    # One native web trace per designer response; other stages need no duplicate body.
                    write_json(path.with_name("provider_message.json"), result.model_dump(mode="json"))
                if incomplete:
                    raise IncompleteResponseError("provider reported incomplete output")
                results[index] = path
            except Exception as exc:
                entry.update(status="failed", error_type=type(exc).__name__)
                log_failure(logger, "job_failed", exc, stage=stage, job=key,
                            request_id=entry["request_id"], attempt=entry["attempt"])
            entry.update(elapsed_seconds=round(time.perf_counter() - started, 3), updated_at=now_iso())
            write_json(run / "run.json", record)
            logger.info("job_%s stage=%s job=%s attempt=%d elapsed=%s response_id=%s provider_status=%s finish_reason=%s",
                        entry["status"], stage, key, entry["attempt"], entry["elapsed_seconds"],
                        diagnostic_identifier(entry.get("response_id")),
                        diagnostic_identifier(entry.get("provider", {}).get("status")),
                        diagnostic_identifier(entry.get("provider", {}).get("finish_reason")))
            if key in starts:
                logger.info("job_timing stage=%s job=%s queued_seconds=%.3f dispatch_to_handled_seconds=%.3f",
                            stage, key, starts[key] - started, time.perf_counter() - starts[key])
            if stage == "design":
                logger.info("designer_web_actions job=%s count=%s", key, entry.get("web_search_actions"))
    except Exception as exc:
        for _, key, _ in pending:
            if key not in returned:
                record["jobs"][key].update(status="failed", error_type=type(exc).__name__)
        write_json(run / "run.json", record)
        log_failure(logger, "stage_failed", exc, stage=stage)
    finally:
        await stop_progress(progress)
    return [results[index] for index in sorted(results)]


async def sequential_call(model, request: list, config: dict):
    """Input one metadata/design request; yield its direct result or operational exception."""
    try:
        result = await model.ainvoke(request, config)
    except Exception as exc:
        result = exc
    yield 0, result
