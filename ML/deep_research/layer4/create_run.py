from __future__ import annotations

import copy
import secrets
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    sha256,
    slug,
    write_json,
)
from ML.deep_research.layer2.settings import REASONING_EFFORTS
from ML.deep_research.layer3.pipeline.progress import stage_record
from ML.deep_research.layer3.settings import WEB_SEARCH_LEVELS
from ML.deep_research.layer3.usage import summarize_usage

from .settings import (
    DOMAIN_NAMES,
    HARNESS_NAME,
    LAYER3_HARNESS_NAME,
    LAYER3_SCHEMA_VERSION,
    MISSING_LAYER3_REPORT,
    PROMPTS_DIR,
    RUN_PREFIX,
    SCHEMA_VERSION,
    SKILL_PATH,
    SYNTHESIS_NAME,
)


def _new_run_dir(group_dir: Path) -> tuple[str, Path]:
    while True:
        run_id = f"{RUN_PREFIX}_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        run_dir = group_dir / run_id
        try:
            run_dir.mkdir()
            return run_id, run_dir
        except FileExistsError:
            pass


def _copy_prompts(run_dir: Path) -> dict[str, str]:
    target = run_dir / "inputs" / "prompts"
    target.mkdir(parents=True)
    shutil.copy2(SKILL_PATH, target / "SKILL.md")
    for source in sorted(PROMPTS_DIR.rglob("*.md")):
        destination = target / source.relative_to(PROMPTS_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return {
        path.relative_to(target).as_posix(): sha256(path)
        for path in sorted(target.rglob("*.md"))
    }


def _copy_domain_inputs(run_dir: Path, layer3_run: Path) -> dict[str, dict[str, Any]]:
    target_dir = run_dir / "inputs" / "domains"
    target_dir.mkdir(parents=True)
    records = {}
    for name in DOMAIN_NAMES:
        source = layer3_run / "domains" / slug(name) / "final.md"
        target = target_dir / f"{slug(name)}.md"
        available = source.is_file()
        if available:
            shutil.copy2(source, target)
        else:
            atomic_write_text(target, MISSING_LAYER3_REPORT)
        records[name] = {
            "available": available,
            "source_path": str(source),
            "snapshot_path": target.relative_to(run_dir).as_posix(),
            "sha256": sha256(target),
        }
    return records


def _execution(run_id: str) -> dict[str, Any]:
    seed = {"run_id": run_id}
    return {
        "domains": {
            name: {
                "internal": stage_record(seed, "internal-segregation", name, 0),
                "external_candidates": stage_record(
                    seed, "external-candidate-segregation", name, 0
                ),
                "external_research": stage_record(
                    seed, "external-research", name, 0
                ),
            }
            for name in DOMAIN_NAMES
        },
        "final": stage_record(seed, "synthesis", SYNTHESIS_NAME, 0),
    }


def create_run(
    layer3_run: Path,
    *,
    public_input_confirmed: bool = False,
    reasoning_effort: str | None = None,
    web_search_context_size: str | None = None,
    web_search_verbosity: str | None = None,
) -> Path:
    """Create one isolated Layer 4 run beside an immutable schema-8 Layer 3 run."""
    layer3_run = layer3_run.resolve()
    metadata_path = layer3_run / "run.json"
    if not metadata_path.is_file():
        raise ValueError("Layer 4 requires a Layer 3 run folder containing run.json")
    source = load_json(metadata_path)
    if source.get("schema_version") != LAYER3_SCHEMA_VERSION:
        raise ValueError(
            f"Layer 4 requires Layer 3 schema {LAYER3_SCHEMA_VERSION}; "
            f"received {source.get('schema_version')!r}"
        )
    if source.get("harness") != LAYER3_HARNESS_NAME:
        raise ValueError("Layer 4 requires the schema-8 direct-research Layer 3 harness")
    if not public_input_confirmed:
        raise ValueError("online external research requires public-input confirmation")

    source_search = source.get("web_search") or {}
    if reasoning_effort is None:
        reasoning_effort = source.get("reasoning_effort")
    web_search_context_size = (
        source_search.get("context_size")
        if web_search_context_size is None
        else web_search_context_size
    )
    if web_search_verbosity is None:
        web_search_verbosity = source_search.get("verbosity")
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
    if web_search_context_size not in WEB_SEARCH_LEVELS:
        raise ValueError(
            f"unsupported web-search context size: {web_search_context_size}"
        )
    if web_search_verbosity not in WEB_SEARCH_LEVELS:
        raise ValueError(f"unsupported web-search verbosity: {web_search_verbosity}")

    run_id, run_dir = _new_run_dir(layer3_run.parent)
    for path in (
        run_dir / "domains",
        run_dir / "research",
        run_dir / "sources" / "raw",
        run_dir / "sources" / "text",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for name in DOMAIN_NAMES:
        (run_dir / "domains" / slug(name)).mkdir(parents=True)

    prompt_hashes = _copy_prompts(run_dir)
    domain_inputs = _copy_domain_inputs(run_dir, layer3_run)
    for name in ("index.jsonl", "queries.jsonl"):
        (run_dir / "sources" / name).touch()
    (run_dir / "usage.jsonl").touch()
    sqlite3.connect(run_dir / "checkpoints.sqlite3").close()

    context_management = copy.deepcopy(source.get("context_management"))
    if isinstance(context_management, dict):
        context_management["applies_to"] = "external_researcher"
    started = now_iso()
    run = {
        "schema_version": SCHEMA_VERSION,
        "harness": HARNESS_NAME,
        "run_id": run_id,
        "run_group": run_dir.parent.name,
        "status": "created",
        "started_at": started,
        "updated_at": started,
        "source_l3": {
            "run_id": source.get("run_id"),
            "path": str(layer3_run),
            "status": source.get("status"),
            "schema_version": source.get("schema_version"),
            "harness": source.get("harness"),
            "domain_inputs": domain_inputs,
        },
        "prompt_hashes": prompt_hashes,
        "provider": source.get("provider", "online"),
        "public_input_confirmed": True,
        "model": source.get("model"),
        "reasoning_effort": reasoning_effort,
        "web_search": {
            "context_size": web_search_context_size,
            "verbosity": web_search_verbosity,
        },
        "model_context_window_tokens": source.get("model_context_window_tokens"),
        "deepagents_version": source.get("deepagents_version"),
        "checkpoint_package_version": source.get("checkpoint_package_version"),
        "limits": copy.deepcopy(source.get("limits") or {}),
        "context_management": context_management,
        "usage": summarize_usage(run_dir),
        "domains": list(DOMAIN_NAMES),
        "execution": _execution(run_id),
    }
    write_json(run_dir / "run.json", run)
    return run_dir


__all__ = ["create_run"]
