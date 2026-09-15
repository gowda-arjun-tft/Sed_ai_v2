"""Freeze dynamic Layer 2 Markdown and settings for Layer 3 preparation and research."""

import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path

from ML.deep_research.domain_decider.backend.fs import (
    atomic_write_text, load_json, now_iso, sha256, storage_path, write_json,
)
from ML.deep_research.domain_decider.backend.publication import domain_names
from ML.deep_research.domain_decider.backend.settings import REASONING_EFFORTS
from .settings import (
    HARNESS_NAME, MODEL_INPUT_TOKEN_LIMIT, MODEL_MAX_RETRIES, MODEL_NAME,
    MODEL_TIMEOUT_SECONDS, PROMPTS_DIR, SCHEMA_VERSION, SOURCE_CONCURRENCY,
    SOURCE_REASONING_EFFORT, SOURCE_SEARCH_DEPTH, SOURCE_SEARCH_VERBOSITY,
    SOURCE_SUGGESTION_PATH, RESEARCH_CONFIG_PATH, RESEARCH_INSTRUCTION_PATH, WEB_SEARCH_LEVELS,
)
from .document_records import UPLOAD_POLICY
from ML.deep_research.domain_decider.backend.stage_settings import resolve_stage_settings


def local_path(run: Path, relative: str) -> Path:
    """Resolve a recorded relative path inside this run, rejecting escape paths."""
    path = (run / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(run.resolve()):
        raise ValueError("recorded path escapes the Layer 3 run")
    return path


def require_current(run: Path) -> dict:
    """Read source-discovery metadata; reject historical execution before any mutation."""
    record = load_json(run / "run.json")
    if record.get("schema_version") != SCHEMA_VERSION or record.get("harness") != HARNESS_NAME:
        raise ValueError("Historical Layer 3 runs are read-only; start a fresh Layer 3 source run")
    return record


def verify_inputs(run: Path, record: dict) -> None:
    """Verify frozen bytes and consent before dispatch or response reuse."""
    if not record.get("public_input_confirmed"):
        raise ValueError("Layer 3 requires public-input confirmation")
    for relative, item in record["inputs"].items():
        if sha256(local_path(run, relative)) != item["sha256"]:
            raise ValueError("Frozen Layer 3 input changed; create a fresh source run")
    for domain in record["domains"]:
        if domain["input_path"] not in record["inputs"]:
            raise ValueError("Domain input is absent from the frozen input manifest")
        local_path(run, domain["output_path"])


def factsheet_snapshot(run: Path, record: dict) -> tuple[bytes, dict] | None:
    """Read only a manifest-backed source snapshot, optionally following its recorded Layer 2."""
    relative = "_internal/inputs/fact_sheet.md"
    manifest = record.get("inputs", {})
    item = manifest.get(relative) or manifest.get("fact_sheet.md")
    path = local_path(run, relative)
    if item is not None:
        # Missing recorded bytes are corruption, not optional-source unavailability.
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.get("sha256"):
            raise ValueError("Frozen factsheet hash mismatch")
        if not raw.decode("utf-8-sig").strip():
            raise ValueError("Frozen factsheet is empty")
        return raw, {"source_path": str(path), "sha256": item["sha256"], "bytes": len(raw)}
    if path.exists():
        raise ValueError("Frozen factsheet has no input manifest entry")
    source = record.get("source_l2", {}).get("path")
    if source:
        parent = storage_path(source)
        if not parent.exists():
            return None
        original = load_json(parent / "run.json")
        if original.get("schema_version") != 9 or original.get("source_l2"):
            raise ValueError("Invalid recorded Domain Decider source")
        expected_id = record["source_l2"].get("run_id")
        if expected_id is not None and original.get("run_id") != expected_id:
            raise ValueError("Recorded Domain Decider identity changed")
        return factsheet_snapshot(parent, original)
    return None


def freeze_factsheet(snapshots: dict, inputs: dict, policy: dict, source, enabled=True) -> None:
    """Add verified optional bytes to existing snapshots and freeze their availability."""
    policy["research_factsheet_access"] = enabled
    policy["factsheet"] = {"status": "unavailable" if enabled else "disabled"}
    if not enabled:
        snapshots.pop("_internal/inputs/fact_sheet.md", None)
        inputs.pop("_internal/inputs/fact_sheet.md", None)
        return
    if source is not None:
        raw, item = source
        relative = "_internal/inputs/fact_sheet.md"
        snapshots[relative], inputs[relative] = raw, item
        policy["factsheet"] = {"status": "available", "input_path": relative}


def create_run(
    l2_run: Path,
    runs_dir: Path,
    *,
    source_suggestion: Path = SOURCE_SUGGESTION_PATH,
    public_input_confirmed: bool = False,
    reasoning_effort: str = SOURCE_REASONING_EFFORT,
    web_search_context_size: str = SOURCE_SEARCH_DEPTH,
    web_search_verbosity: str = SOURCE_SEARCH_VERBOSITY,
    research_reasoning_effort: str = "max",
    research_instruction: Path = RESEARCH_INSTRUCTION_PATH,
    research_config: Path = RESEARCH_CONFIG_PATH,
    stage_settings: dict | None = None, destination: Path | None = None,
    prompt_directory: Path | None = None,
    research_factsheet_access: bool = True,
) -> Path:
    """Create beside completed schema-9 Layer 2; read all inputs before creating a directory."""
    if not public_input_confirmed:
        raise ValueError("Layer 3 requires public-input confirmation")
    if type(research_factsheet_access) is not bool:
        raise ValueError("research_factsheet_access must be a Boolean")
    from .research_run import RESEARCH_PROMPTS, read_research_config, research_policy

    config_path = storage_path(research_config)
    config_bytes, limits = read_research_config(config_path)
    research = research_policy(research_reasoning_effort, call_limits=limits)
    resolved = resolve_stage_settings(stage_settings, legacy={
        "source_discovery": {"reasoning": reasoning_effort, "search_context": web_search_context_size,
                             "verbosity": web_search_verbosity},
        "research": {"reasoning": research_reasoning_effort},
    })
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError("unsupported reasoning effort")
    if web_search_context_size not in WEB_SEARCH_LEVELS or web_search_verbosity not in WEB_SEARCH_LEVELS:
        raise ValueError("unsupported web-search depth or verbosity")
    l2_run = storage_path(l2_run)
    source = load_json(l2_run / "run.json")
    if source.get("schema_version") != 9 or source.get("status") != "complete":
        raise ValueError("Source discovery requires a completed Layer 2 schema-9 run")
    files = sorted((l2_run / "domains").glob("*.md"))
    if not files:
        raise ValueError("Layer 2 has no domain Markdown files")
    domains = [{"key": f"source_finder/{index:06d}", "source_file": f"domains/{path.name}",
                "input_path": f"_internal/inputs/domains/{index:06d}.md"}
               for index, path in enumerate(files, 1)]
    names = domain_names({item["key"]: {"name": path.stem}
                          for item, path in zip(domains, files, strict=True)})
    paths = {"_internal/inputs/asset_metadata.md": local_path(l2_run, "asset_metadata.md"),
             "_internal/inputs/source_suggestion.md": storage_path(source_suggestion),
             "_internal/inputs/user_research_instruction.md": storage_path(research_instruction),
             "_internal/inputs/prompts/source_finder.md": Path(prompt_directory or PROMPTS_DIR) / "source_finder.md"}
    paths.update({f"_internal/inputs/prompts/{name}.md": Path(prompt_directory or PROMPTS_DIR) / f"{name}.md"
                  for name in RESEARCH_PROMPTS})
    for item in domains:
        paths[item["input_path"]] = local_path(l2_run, item["source_file"])
        item["output_path"] = names[item["key"]].replace("domains/", "sources/", 1)[:-3] + ".json"
    snapshots, inputs = {}, {}
    for relative, path in paths.items():
        raw = path.read_bytes()
        if not raw.decode("utf-8-sig").strip():
            raise ValueError(f"Required Markdown input is empty: {path.name}")
        snapshots[relative] = raw
        inputs[relative] = {"source_path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw)}
    config_relative = "_internal/inputs/research_config.json"
    snapshots[config_relative] = config_bytes
    inputs[config_relative] = {"source_path": str(config_path), "sha256": hashlib.sha256(config_bytes).hexdigest(),
                              "bytes": len(config_bytes)}
    freeze_factsheet(snapshots, inputs, research,
                    factsheet_snapshot(l2_run, source) if research_factsheet_access else None,
                    research_factsheet_access)
    # The public runs_dir argument remains accepted; the selected Layer 2 owns colocation.
    while True:
        run_id = f"L3_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        run = storage_path(destination) if destination is not None else l2_run.parent / run_id
        try:
            run.mkdir()
            break
        except FileExistsError:
            if destination is not None:
                raise
            continue
    for relative, raw in snapshots.items():
        target = run / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (run / "_internal/trace").mkdir(parents=True)
    (run / "sources").mkdir()
    record = {
        "schema_version": SCHEMA_VERSION, "harness": HARNESS_NAME, "run_id": run_id,
        "stage_settings": resolved,
        "status": "created", "started_at": now_iso(), "updated_at": now_iso(),
        "source_l2": {"run_id": source.get("run_id"), "path": str(l2_run),
                      "status": source["status"], "checks": source.get("checks") or {},
                      "facts": source.get("facts") or {}},
        "inputs": inputs, "domains": domains, "public_input_confirmed": True,
        "model": MODEL_NAME, "reasoning_effort": reasoning_effort,
        "provider_max_retries": MODEL_MAX_RETRIES, "timeout_seconds": MODEL_TIMEOUT_SECONDS,
        "max_concurrency": SOURCE_CONCURRENCY, "model_input_token_limit": MODEL_INPUT_TOKEN_LIMIT,
        "web_search": {"context_size": web_search_context_size, "verbosity": web_search_verbosity,
                       "tool_choice": {"type": "web_search"}, "input_token_limit": 128_000},
        "context_policy": {"target_tokens": 300_000, "maximum_tokens": 350_000,
                           "framing_reserve": 8_000, "count_kind": "local_estimate"},
        "jobs": {}, "document_uploads": {"policy": dict(UPLOAD_POLICY), "status": "pending"},
        "research": research,
    }
    verify_inputs(run, record)
    write_json(run / "run.json", record)
    atomic_write_text(run / "README.md", "# Layer 3 research\n\nStatus: created. Source preparation precedes domain research.\n")
    return run
