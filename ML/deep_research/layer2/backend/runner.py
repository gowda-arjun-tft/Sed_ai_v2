"""Schema-5 source understanding, dynamic domains, one review and partial publication."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..ML.agent import Layer2Response, read_only_filesystem
from ..ML.context import dump, estimate
from .create_run import require_current
from .fs import atomic_write_text, load_json, now_iso, read_text, sha256, write_json
from .jobs import run_jobs
from .records import catalogue, extract_records, record_pages, unprocessed, virtual_pages
from .publication import publish, readable
from .run_log import operational_logger
from .usage import summarize_usage
from .windows import source_windows, token_count


def source_payloads(run: Path, context: dict, stage: str) -> list[dict]:
    """Input source manifest and stage context; repack original windows before large dispatches."""
    policy = load_json(run / "run.json")["context_policy"]
    prompt = read_text(run / "_internal/inputs" / "prompts" / f"{stage}.md")
    overhead = estimate([{"role": "user", "content": dump(context)}], prompt,
                        response_schema=Layer2Response.model_json_schema(),
                        reserve=policy["framing_reserve"] + 2_000)
    allowance = policy["target_tokens"] - overhead
    raw_source = (run / "_internal/inputs/fact_sheet.md").read_bytes().decode("utf-8-sig").encode("utf-8")
    jobs = []
    for item in load_json(run / "_internal/trace/source/manifest.json"):
        # The frozen original is authoritative; generated window files are navigation.
        window = {**item,
                  "overlap_context": raw_source[item["start_byte"]:item["new_start_byte"]].decode("utf-8"),
                  "new_content": raw_source[item["new_start_byte"]:item["end_byte"]].decode("utf-8")}
        text = window["overlap_context"] + window["new_content"]
        parts = [window]
        serialized = token_count(dump(dump(text)))
        if allowance < serialized:
            if allowance <= 12_000:
                allowance = policy["maximum_tokens"] - overhead - 2_000
            size = int(token_count(text) * allowance / max(1, serialized)) - 1_000
        else:
            size = token_count(text)
        if 10_000 < size < token_count(text):
            parts = source_windows(text, size=size, overlap=10_000)
            raw = text.encode("utf-8")
            for part in parts:
                cut = max(part["new_start_byte"],
                          item["new_start_byte"] - item["start_byte"])
                cut = min(cut, part["end_byte"])
                part["overlap_context"] = raw[part["start_byte"]:cut].decode("utf-8")
                part["new_content"] = raw[cut:part["end_byte"]].decode("utf-8")
                for field in ("start_byte", "end_byte"):
                    part[field] += item["start_byte"]
                part["new_start_byte"] = cut + item["start_byte"]
        for index, part in enumerate(parts, 1):
            location = {k: item[k] for k in ("source_id", "input_bom_bytes")}
            location.update({k: part[k] for k in ("start_byte", "end_byte", "new_start_byte")})
            location["part"] = index
            jobs.append({**context, "source": location, "overlap_context": part["overlap_context"],
                         "new_content": part["new_content"]})
    return jobs


def review_payloads(run: Path, stage: str, context: dict, records: list,
                    domain_context: dict | None = None) -> list[dict]:
    """Input facts and definitions; inline complete catalogues only when fully counted pages fit."""
    policy = load_json(run / "run.json")["context_policy"]
    prompt = read_text(run / "_internal/inputs" / "prompts" / f"{stage}.md")
    # The pinned native read-only middleware adds no system prose; its unfiltered
    # schemas conservatively include at least the descriptions sent by the graph.
    tools = read_only_filesystem().tools
    schema = Layer2Response.model_json_schema()
    options = [{**context, **domain_context}, context] if domain_context else [context]
    for candidate in options:
        overhead = estimate([{"role": "user", "content": dump(candidate)}], prompt, tools,
                            schema, policy["framing_reserve"] + 5_000)
        budget = max(1, min(40_000, policy["target_tokens"] - overhead))
        pages = [{**candidate, "facts": page} for page in record_pages(records, budget)]
        if all(estimate([{"role": "user", "content": dump(page)}], prompt, tools,
                        schema, policy["framing_reserve"]) <= policy["target_tokens"] for page in pages):
            return pages
    return pages  # Paging exhausted: the existing dispatch guard handles exceptional/oversized inputs.


def understanding_records(responses: list) -> tuple[str, list]:
    """Input saved understanding responses; project readable fragments and source-linked inventory."""
    profiles, inventory = [], []
    for response in responses:
        value, source = response["value"], response["payload"]["source"]
        profiles.append(f"## {source['source_id']} part {source['part']}\n\n"
                        + readable(value.get("profile", value)))
        rows = value.get("evidence", [])
        if isinstance(rows, list):
            for index, body in enumerate(rows, 1):
                inventory.append({"evidence_id": f"e-{response['fingerprint'][:20]}-{index:06d}",
                                  "body": body, "source": source})
    return "\n\n".join(profiles), inventory


async def execute(run: Path, logger) -> dict:
    """Input a current run and logger; execute each phase once, reusing saved phase/page results."""
    record = require_current(run)
    for name, info in record["inputs"].items():
        if sha256(run / "_internal/inputs" / name) != info["sha256"]:
            raise OSError("frozen input hash changed; create a new run")
    if sha256(run / "_internal/trace/source/manifest.json") != record["source_manifest_sha256"]:
        raise OSError("frozen source manifest changed; create a new run")
    instructions = {name: read_text(run / "_internal/inputs" / f"{name}.md")
                    for name in ("domain_plugin", "requirements")}
    original = (run / "_internal/inputs/fact_sheet.md").read_bytes().decode("utf-8-sig")
    async with aiosqlite.connect(str(run / "_internal/trace/checkpoints.sqlite3")) as connection:
        saver = AsyncSqliteSaver(connection, serde=JsonPlusSerializer(
            allowed_msgpack_modules=[Layer2Response],
        ))
        understood = await run_jobs(run, "understanding",
                                    source_payloads(run, instructions, "understanding"),
                                    {}, saver, logger)
        profile, inventory = understanding_records(understood)
        audit = unprocessed(understood, {"profile": str, "evidence": list})
        atomic_write_text(run / "_internal/trace/understanding/subject_profile.md", profile)
        write_json(run / "_internal/trace/understanding/evidence_inventory.json", inventory)
        groups = {**instructions, "original_source": original, "subject_profile": profile,
                  "evidence_inventory": dump(inventory)}
        files = virtual_pages(groups)
        design_input = {**instructions, "evidence_files": list(files),
                        "task": "Read complete subject-profile and evidence-inventory pages "
                                "and relevant original evidence; settle initial domains."}
        designed = await run_jobs(run, "design", [design_input], files, saver, logger)
        initial, design_audit = catalogue(designed[0]["value"] if designed else {})
        audit.extend([{**item, "job": "design/000001"} for item in design_audit]
                     + unprocessed(designed, {"domains": list}))
        write_json(run / "_internal/domains.json", {"initial": initial, "final": []})
        groups["initial_catalogue"] = dump(initial)
        distributed = await run_jobs(
            run, "distribution",
            source_payloads(run, {**instructions, "initial_catalogue": initial}, "distribution"),
            {}, saver, logger,
        )
        facts, initial_owners, distribution_audit = extract_records(run, distributed)
        audit.extend(distribution_audit + unprocessed(distributed, {"facts": list}))
        write_json(run / "_internal/assignments.json", {"initial": initial_owners})
        groups["recorded_facts"] = dump(facts)
        files = virtual_pages(groups)
        reviewed = [{"fact": fact, "initial_assignment": owner}
                    for fact, owner in zip(facts, initial_owners)]
        page_context = {**instructions, "evidence_files": list(files)}
        observations = await run_jobs(
            run, "observations",
            review_payloads(run, "observations", page_context, reviewed, {"initial_catalogue": initial}),
            files, saver, logger,
        )
        observation_values = [row["value"] for row in observations]
        audit.extend(unprocessed(observations, {"observations": list}))
        write_json(run / "_internal/trace/review/observations.json", observation_values)
        groups["observations"] = dump(observation_values)
        files = virtual_pages(groups)
        settled = await run_jobs(
            run, "catalogue",
            [{**instructions, "evidence_files": list(files),
              "task": "Read every saved observation and existing definition; settle final catalogue."}],
            files, saver, logger,
        )
        final, catalogue_audit = catalogue(settled[0]["value"] if settled else {}, initial)
        audit.extend([{**item, "job": "catalogue/000001"} for item in catalogue_audit]
                     + unprocessed(settled, {"domains": list}))
        write_json(run / "_internal/domains.json", {"initial": initial, "final": final})
        groups["final_catalogue"] = dump(final)
        files = virtual_pages(groups)
        assignments = await run_jobs(
            run, "assignments",
            review_payloads(run, "assignments", {
                **instructions, "evidence_files": list(files),
                "final_domain_ids": [row["domain_id"] for row in final],
            }, [{**fact, "initial_assignment": owner} for fact, owner in zip(facts, initial_owners)],
                {"final_catalogue": final}),
            files, saver, logger,
        )
    audit.extend(unprocessed(assignments, {"assignments": list}))
    latest = load_json(run / "run.json")
    audit.extend({"kind": "operational_failure", "job": key, "error_type": entry["error_type"]}
                 for key, entry in latest["jobs"].items() if entry["status"] == "failed")
    coverage = publish(run, final, facts, assignments, audit,
                       profile=profile, observations=observation_values)
    logger.info("published domains=%d recorded_facts=%d unresolved_facts=%d",
                coverage["domain_count"], coverage["recorded_facts"], coverage["unresolved_facts"])
    return coverage


def run_all(run_dir: Path) -> dict:
    """Input a schema-5 run; synchronously execute it and return provider-reported usage totals."""
    run_dir = Path(run_dir).resolve()
    record = require_current(run_dir)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is empty")
    with operational_logger(run_dir) as logger:
        logger.info("run_%s run_id=%s", "started" if record["status"] == "started" else "resumed",
                    record["run_id"])
        logger.info("frozen_policy chunking=%s context=%s", dump(record["chunking"]),
                    dump(record["context_policy"]))
        try:
            coverage = asyncio.run(execute(run_dir, logger))
        except Exception as exc:
            record = load_json(run_dir / "run.json")
            record.update(status="failed", error_type=type(exc).__name__, updated_at=now_iso())
            write_json(run_dir / "run.json", record)
            logger.error("run_failed error_type=%s", type(exc).__name__)
            raise
        record = load_json(run_dir / "run.json")
        failed = sum(job["status"] == "failed" for job in record["jobs"].values())
        usage = summarize_usage(run_dir / "_internal/trace")
        record.update(status="partial" if failed else "complete", current_stage=None,
                      coverage=coverage, usage=usage, finished_at=now_iso(), error_type="")
        write_json(run_dir / "run.json", record)
        logger.info("run_%s failed_jobs=%d", record["status"], failed)
        return usage
