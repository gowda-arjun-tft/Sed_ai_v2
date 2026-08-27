from __future__ import annotations

import re
import secrets
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ML.deep_research.layer2.fs import (
    load_json,
    now_iso,
    run_group_name,
    sha256,
    write_json,
)
from ML.deep_research.layer2.settings import REASONING_EFFORTS
from ML.deep_research.layer2.mission_markdown import write_mission_markdown

from ..mission import stage_thread_id
from ..settings import (
    CHECKPOINT_PACKAGE_VERSION,
    CONTEXT_POLICY_VERSION,
    CONTEXT_SOFT_TARGET_TOKENS,
    DEFAULT_OCR_LANGUAGES,
    DEEPAGENTS_VERSION,
    DOCUMENT_EXTRACTION_POLICY_VERSION,
    DOMAIN_NAMES,
    EMERGENCY_EVICTION_KEEP_TOOL_RESULTS,
    EMERGENCY_EVICTION_TRIGGER_TOKENS,
    EVICTION_EXCLUDE_TOOLS,
    EVICTION_KEEP_TOOL_RESULTS,
    EVICTION_TRIGGER_TOKENS,
    FETCH_TIMEOUT_SECONDS,
    FIND_MAX_HITS,
    FULL_DOCUMENT_RESPONSE_TOKENS,
    HARNESS_NAME,
    MAX_DOCUMENT_BYTES,
    MAX_PDF_PAGES,
    MAX_REQUESTED_PAGES,
    MAX_SOURCE_BYTES,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_MAX_RETRIES,
    MODEL_NAME,
    MODEL_TIMEOUT_SECONDS,
    PDF_BATCH_PAGES,
    PROMPTS_DIR,
    REASONING_EFFORT,
    RUN_PREFIX,
    SCHEMA_VERSION,
    SKILL_PATH,
    SUMMARY_KEEP_TOKENS,
    SUMMARY_TRIGGER_TOKENS,
    SUMMARY_TRIM_TOKENS,
    WEB_SEARCH_CONTEXT_SIZE,
    WEB_SEARCH_LEVELS,
    WEB_SEARCH_VERBOSITY,
    WORKER_HEARTBEAT_SECONDS,
    WORKER_STALE_SECONDS,
)


def normalize_ocr_languages(value: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    items = value.split(",") if isinstance(value, str) else value
    languages: list[str] = []
    for item in items:
        language = str(item).strip().casefold()
        if not language:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", language):
            raise ValueError(f"invalid OCR language code: {item!r}")
        if language not in languages:
            languages.append(language)
    if not languages:
        raise ValueError("at least one OCR language is required")
    return tuple(languages)


def _load_l2(run_dir: Path) -> tuple[dict, Path, list[Path]]:
    metadata_path = run_dir / "run.json"
    metadata = load_json(metadata_path)
    planner = run_dir / "inputs" / "planner_prompt.md"
    mission_dir = run_dir / "missions"
    missions = sorted(mission_dir.glob("*.json"))
    return metadata, planner, missions


def _new_run_dir(runs_dir: Path, l2_run: Path, source: dict) -> tuple[str, Path]:
    if l2_run.parent.parent.resolve() == runs_dir.resolve():
        group_dir = l2_run.parent
    else:
        source_path = source.get("fact_sheet", {}).get("source_path")
        group_dir = runs_dir / run_group_name(Path(source_path) if source_path else l2_run)
    group_dir.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = (
            f"{RUN_PREFIX}_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        )
        run_dir = group_dir / run_id
        try:
            run_dir.mkdir()
            return run_id, run_dir
        except FileExistsError:
            pass


def _copy_prompts(run_dir: Path) -> tuple[str, dict[str, str]]:
    target = run_dir / "inputs" / "prompts"
    target.mkdir(parents=True)
    skill_copy = target / "SKILL.md"
    shutil.copy2(SKILL_PATH, skill_copy)
    for source in sorted(PROMPTS_DIR.rglob("*.md")):
        relative = source.relative_to(PROMPTS_DIR)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    prompt_hashes = {
        str(path.relative_to(target)).replace("\\", "/"): sha256(path)
        for path in sorted(target.rglob("*.md"))
        if path.name != "SKILL.md"
    }
    return sha256(skill_copy), prompt_hashes


def create_run(
    l2_run: Path,
    runs_dir: Path,
    *,
    public_input_confirmed: bool = False,
    reasoning_effort: str = REASONING_EFFORT,
    web_search_context_size: str = WEB_SEARCH_CONTEXT_SIZE,
    web_search_verbosity: str = WEB_SEARCH_VERBOSITY,
    ocr_languages: str | tuple[str, ...] | list[str] = DEFAULT_OCR_LANGUAGES,
) -> Path:
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
    if web_search_context_size not in WEB_SEARCH_LEVELS:
        raise ValueError(f"unsupported web-search context size: {web_search_context_size}")
    if web_search_verbosity not in WEB_SEARCH_LEVELS:
        raise ValueError(f"unsupported web-search verbosity: {web_search_verbosity}")
    selected_ocr_languages = normalize_ocr_languages(ocr_languages)
    l2_run = l2_run.resolve()
    source, planner, missions = _load_l2(l2_run)
    if not public_input_confirmed:
        raise ValueError("online research requires public-input confirmation")
    run_id, run_dir = _new_run_dir(runs_dir, l2_run, source)
    mission_dir = run_dir / "inputs" / "missions"
    mission_md_dir = run_dir / "inputs" / "mission_md"
    for path in (
        mission_dir,
        mission_md_dir,
        run_dir / "domains",
        run_dir / "research",
        run_dir / "sources" / "raw",
        run_dir / "sources" / "text",
        run_dir / "sources" / "documents",
    ):
        path.mkdir(parents=True, exist_ok=True)
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    shutil.copy2(planner, planner_copy)
    for mission in missions:
        target = mission_dir / mission.name
        shutil.copy2(mission, target)
        markdown = l2_run / "mission_md" / f"{mission.stem}.md"
        markdown_target = mission_md_dir / markdown.name
        if markdown.is_file():
            shutil.copy2(markdown, markdown_target)
        else:
            write_mission_markdown(markdown_target, load_json(mission))
    skill_hash, prompt_hashes = _copy_prompts(run_dir)
    for name in ("index.jsonl", "queries.jsonl"):
        (run_dir / "sources" / name).touch()
    (run_dir / "usage.jsonl").touch()
    sqlite3.connect(run_dir / "checkpoints.sqlite3").close()
    started = now_iso()
    write_json(
        run_dir / "run.json",
        {
            "schema_version": SCHEMA_VERSION,
            "harness": HARNESS_NAME,
            "run_id": run_id,
            "run_group": run_dir.parent.name,
            "status": "created",
            "started_at": started,
            "updated_at": started,
            "source_l2": {
                "run_id": source.get("run_id"),
                "path": str(l2_run),
                "status": source.get("status"),
                "checks": source.get("checks") or {},
                "facts": source.get("facts") or {},
            },
            "skill": {"path": "inputs/prompts/SKILL.md", "sha256": skill_hash},
            "prompt_hashes": prompt_hashes,
            "provider": "online",
            "public_input_confirmed": True,
            "model": MODEL_NAME,
            "reasoning_effort": reasoning_effort,
            "web_search": {
                "context_size": web_search_context_size,
                "verbosity": web_search_verbosity,
            },
            "document_extraction": {
                "policy_version": DOCUMENT_EXTRACTION_POLICY_VERSION,
                "backend": "local_docling",
                "ocr_engine": "easyocr",
                "ocr_languages": list(selected_ocr_languages),
                "max_document_bytes": MAX_DOCUMENT_BYTES,
                "max_pdf_pages": MAX_PDF_PAGES,
                "pdf_batch_pages": PDF_BATCH_PAGES,
                "full_response_token_threshold": FULL_DOCUMENT_RESPONSE_TOKENS,
                "max_requested_pages": MAX_REQUESTED_PAGES,
                "max_find_hits": FIND_MAX_HITS,
                "worker_heartbeat_seconds": WORKER_HEARTBEAT_SECONDS,
                "worker_stale_seconds": WORKER_STALE_SECONDS,
            },
            "model_context_window_tokens": MODEL_INPUT_TOKEN_LIMIT,
            "deepagents_version": DEEPAGENTS_VERSION,
            "checkpoint_package_version": CHECKPOINT_PACKAGE_VERSION,
            "limits": {
                "model_and_search_timeout_seconds": MODEL_TIMEOUT_SECONDS,
                "transient_retries": MODEL_MAX_RETRIES,
                "fetch_timeout_seconds": FETCH_TIMEOUT_SECONDS,
                "maximum_source_bytes": MAX_SOURCE_BYTES,
            },
            # Applied to the five lenses and the citation verifier only. These
            # shape context size, never model content.
            "context_management": {
                "policy_version": CONTEXT_POLICY_VERSION,
                "applies_to": "research_subagents",
                "soft_target_tokens": CONTEXT_SOFT_TARGET_TOKENS,
                "eviction_trigger_tokens": EVICTION_TRIGGER_TOKENS,
                "eviction_keep_tool_results": EVICTION_KEEP_TOOL_RESULTS,
                "eviction_exempt_tools": list(EVICTION_EXCLUDE_TOOLS),
                "emergency_eviction_trigger_tokens": (
                    EMERGENCY_EVICTION_TRIGGER_TOKENS
                ),
                "emergency_eviction_keep_tool_results": (
                    EMERGENCY_EVICTION_KEEP_TOOL_RESULTS
                ),
                "summary_trigger_tokens": SUMMARY_TRIGGER_TOKENS,
                "summary_keep_tokens": SUMMARY_KEEP_TOKENS,
                "summary_trim_tokens": SUMMARY_TRIM_TOKENS,
            },
            "usage": {
                "api_calls": 0,
                "model_calls": 0,
                "summarization_calls": 0,
                "web_search_calls": 0,
                "over_soft_target_calls": 0,
                "compacted_source_results": 0,
                "events": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "total_tokens": 0,
            },
            "domains": list(DOMAIN_NAMES),
            "execution": _execution(run_id, started),
        },
    )
    return run_dir


def _record(run_id: str, stage: str, actor: str, batch: int, started: str) -> dict:
    return {
        "stage": stage,
        "actor": actor,
        "batch": batch,
        "thread_id": stage_thread_id(run_id, stage, actor, batch, 1),
        "attempt": 1,
        "status": "pending",
        "error": "",
        "output_path": "",
        "model_turns": 0,
        "elapsed_seconds": 0.0,
        "updated_at": started,
    }


def _execution(run_id: str, started: str) -> dict:
    return {
        "domains": {
            name: _record(run_id, "coordinator", name, 0, started)
            for name in DOMAIN_NAMES
        },
        "final": _record(run_id, "synthesis", "property-synthesis", 0, started),
    }
