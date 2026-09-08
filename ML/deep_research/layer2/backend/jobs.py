"""Versioned stage responses, native batching and same-thread checkpoint recovery."""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

from deepagents.backends.utils import create_file_data

from ..ML.agent import Layer2Response, create_stage_agent, response_value
from ..ML.context import dump, estimate
from .fs import load_json, now_iso, read_text, text_hash, write_json
from .usage import UsageCallback


def saved_object(path: Path):
    """Input a response path; return any readable object or None for operational recovery."""
    try:
        value = load_json(path)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


async def completed_jobs(graph, inputs: list, configs: list, retrieval: bool):
    """Input phase work; yield native batch completions or sequential checkpointed page results."""
    if not retrieval:
        async for result in graph.abatch_as_completed(inputs, configs, return_exceptions=True):
            yield result
        return
    # Page sequencing is outside the graph. max_concurrency=1 inside a checkpointed
    # graph can deadlock its pending SQLite writes during exception cleanup.
    for index, (value, config) in enumerate(zip(inputs, configs)):
        try:
            result = await graph.ainvoke(value, config)
        except Exception as exc:
            result = exc
        yield index, result


async def run_jobs(run: Path, stage: str, payloads: list[dict], files: dict,
                   saver, logger) -> list[dict]:
    """Input bounded phase jobs; save arriving results and return usable responses in order."""
    record = load_json(run / "run.json")
    prompt = read_text(run / "inputs" / "prompts" / f"{stage}.md")
    policy = record["context_policy"]
    retrieval = stage not in {"understanding", "distribution"}
    concurrency = 1 if retrieval else int(record["chunking"]["max_concurrency"])
    if concurrency < 1:
        raise ValueError("max_concurrency must be positive")
    inputs, configs, pending, results = [], [], [], {}
    frozen = {k: record[k] for k in ("model", "reasoning_effort", "context_policy", "chunking")}
    for index, payload in enumerate(payloads):
        key = f"{stage}/{index + 1:06d}"
        fingerprint = text_hash(dump([prompt, frozen, payload, files if retrieval else {}]))
        relative = f"responses/{key}/{fingerprint}/response.json"
        old = record["jobs"].get(key, {})
        changed = old.get("fingerprint") != fingerprint
        if changed and old:
            write_json(run / "responses" / key / old["fingerprint"] / "job.json", old)
        entry = dict(old) if not changed else {
            "thread_id": str(uuid4()), "attempt": 0, "status": "pending",
        }
        entry.update(fingerprint=fingerprint, response_path=relative, stage=stage)
        value = saved_object(run / relative)
        record["jobs"][key] = entry
        if value is not None:
            entry.update(status="complete", error_type="")
            results[index] = {"value": value, "job": key, "fingerprint": fingerprint,
                              "payload": payload}
            continue
        entry.update(status="running", attempt=entry["attempt"] + 1, error_type="",
                     updated_at=now_iso())
        config = {"configurable": {"thread_id": entry["thread_id"]},
                  "callbacks": [UsageCallback(run, entry["thread_id"])]}
        if not retrieval:
            config["max_concurrency"] = concurrency
        message = {"role": "user", "content": dump(payload)}
        # Full final schema/tool accounting is repeated by InputBudget on every turn.
        count = estimate([message], prompt, response_schema=Layer2Response.model_json_schema(),
                         reserve=policy["framing_reserve"])
        entry["input_estimate"] = count
        if count > policy["maximum_tokens"]:
            entry.update(status="failed", error_type="InputSizeError")
            logger.error("job_failed job=%s attempt=%d error_type=InputSizeError",
                         key, entry["attempt"])
            continue
        inputs.append({"messages": [message], **({"files": {
            name: create_file_data(body) for name, body in files.items()
        }} if retrieval else {})})
        configs.append(config)
        pending.append((index, key, payload, fingerprint, time.perf_counter()))
        logger.info("job_scheduled job=%s attempt=%d input_estimate=%d",
                    key, entry["attempt"], count)
    record.update(status="running", current_stage=stage)
    write_json(run / "run.json", record)
    if pending:
        returned = set()
        try:
            graph = create_stage_agent(run, stage, saver)
            if retrieval:
                for i, config in enumerate(configs):
                    state = await graph.aget_state(config)
                    if state.values:
                        inputs[i] = None  # Resume exact checkpoint, not a duplicate user message.
            async for batch_index, result in completed_jobs(graph, inputs, configs, retrieval):
                index, key, payload, fingerprint, start = pending[batch_index]
                returned.add(index)
                entry = record["jobs"][key]
                try:
                    if isinstance(result, Exception):
                        raise result
                    value = response_value(result)
                    write_json(run / entry["response_path"], value)
                    entry.update(status="complete", error_type="")
                    results[index] = {"value": value, "job": key,
                                      "fingerprint": fingerprint, "payload": payload}
                except Exception as exc:
                    entry.update(status="failed", error_type=type(exc).__name__)
                entry.update(elapsed_seconds=round(time.perf_counter() - start, 3),
                             updated_at=now_iso())
                write_json(run / "run.json", record)
                logger.info("job_%s job=%s attempt=%d elapsed=%s error_type=%s",
                            entry["status"], key, entry["attempt"],
                            entry["elapsed_seconds"], entry["error_type"])
        except Exception as exc:
            for index, key, *_ in pending:
                if index not in returned:
                    record["jobs"][key].update(status="failed", error_type=type(exc).__name__,
                                               updated_at=now_iso())
                    logger.error("job_failed job=%s error_type=%s", key, type(exc).__name__)
            write_json(run / "run.json", record)
    # Retired page slots must not appear as active failures after a changed-input repack.
    current_keys = {f"{stage}/{i + 1:06d}" for i in range(len(payloads))}
    for key in list(record["jobs"]):
        if key.startswith(stage + "/") and key not in current_keys:
            old = record["jobs"].pop(key)
            write_json(run / "responses" / key / old["fingerprint"] / "job.json", old)
    write_json(run / "run.json", record)
    return [results[i] for i in sorted(results)]
