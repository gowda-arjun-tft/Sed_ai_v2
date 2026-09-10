"""Create consented schema-9 runs after input preflight and one source-tokenization pass."""

import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from .fs import now_iso, run_group_name, sha256, write_json, atomic_write_text, storage_path
from .settings import (
    CHUNK_ENCODING, CHUNK_INPUT_PARTITIONING, CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS, CHUNK_STRATEGY, CONTEXT_MAXIMUM, CONTEXT_RESERVE,
    CONTEXT_TARGET, LAYER2_SCHEMA_VERSION, MODEL_INPUT_TOKEN_LIMIT,
    MAX_CHUNK_CONCURRENCY, MODEL_NAME, PROMPTS_DIR, PROMPT_FILES, PROVIDER_MAX_RETRIES,
    REASONING_EFFORT, REASONING_EFFORTS, STAGES, WEB_SEARCH_CONTEXT_SIZE,
    WEB_SEARCH_INPUT_LIMIT, WEB_SEARCH_LEVELS, WEB_SEARCH_VERBOSITY,
)
from .windows import source_windows


def require_current(run_dir: Path) -> dict:
    """Input a run path; return schema-9 metadata or reject historical execution unchanged."""
    from .fs import load_json

    record = load_json(run_dir / "run.json")
    if not isinstance(record, dict) or record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        raise ValueError("Layer 2 schema 9 is required; older runs are read-only history")
    return record


def create_run(
    fact_sheet: Path, domain_plugin: Path, requirements: Path, runs_dir: Path,
    *, reasoning_effort: str = REASONING_EFFORT,
    web_search_context_size: str = WEB_SEARCH_CONTEXT_SIZE,
    web_search_verbosity: str = WEB_SEARCH_VERBOSITY,
    public_input_confirmed: bool = False,
) -> Path:
    """Input public-confirmed paths and settings; return a frozen run without model calls."""
    if public_input_confirmed is not True:
        raise ValueError("Layer 2 web-assisted design requires public-input confirmation")
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
    if web_search_context_size not in WEB_SEARCH_LEVELS:
        raise ValueError(f"unsupported web-search context size: {web_search_context_size}")
    if web_search_verbosity not in WEB_SEARCH_LEVELS:
        raise ValueError(f"unsupported web-search verbosity: {web_search_verbosity}")
    if os.name != "nt":
        fact_sheet, domain_plugin, requirements = (
            Path(str(path).replace("\\", "/"))
            for path in (fact_sheet, domain_plugin, requirements)
        )
    paths = {"fact_sheet.md": fact_sheet, "domain_plugin.md": domain_plugin,
             "requirements.md": requirements}
    paths.update({f"prompts/{stage}.md": PROMPTS_DIR / PROMPT_FILES[stage] for stage in STAGES})
    snapshots, metadata = {}, {}
    for name, path in paths.items():
        path = Path(path).resolve()
        raw = storage_path(path).read_bytes()
        if not raw.decode("utf-8-sig").strip():
            raise ValueError(f"input is empty: {path}")
        snapshots[name] = raw
        metadata[name] = {"source_path": str(path), "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest()}
    source = snapshots["fact_sheet.md"].decode("utf-8-sig")
    windows = source_windows(source, include_text=False)
    del source
    group = storage_path(runs_dir) / run_group_name(Path(fact_sheet))
    group.mkdir(parents=True, exist_ok=True)
    while True:
        run = group / f"L2_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        try:
            run.mkdir()
            break
        except FileExistsError:
            continue
    for name, raw in snapshots.items():
        target = run / "_internal" / "inputs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        if sha256(target) != metadata[name]["sha256"]:
            raise OSError("snapshot hash mismatch")
    bom_bytes = 3 if snapshots["fact_sheet.md"].startswith(b"\xef\xbb\xbf") else 0
    for window in windows:
        window["input_bom_bytes"] = bom_bytes
    write_json(run / "_internal" / "trace" / "source" / "manifest.json", windows)
    write_json(run / "run.json", {
        "schema_version": LAYER2_SCHEMA_VERSION, "run_id": run.name,
        "run_group": group.name, "status": "started", "started_at": now_iso(),
        "inputs": metadata, "model": MODEL_NAME, "reasoning_effort": reasoning_effort,
        "source_manifest_sha256": sha256(run / "_internal" / "trace" / "source" / "manifest.json"),
        "execution": "direct_id_routing", "provider_max_retries": PROVIDER_MAX_RETRIES,
        "public_input_confirmed": True,
        "web_search": {"context_size": web_search_context_size,
                       "verbosity": web_search_verbosity, "tool_choice": "auto",
                       "input_token_limit": WEB_SEARCH_INPUT_LIMIT},
        "model_input_token_limit": MODEL_INPUT_TOKEN_LIMIT,
        "source_tokens": windows[-1]["end_token"], "source_windows": len(windows),
        "chunking": {"strategy": CHUNK_STRATEGY, "input_partitioning": CHUNK_INPUT_PARTITIONING,
                     "encoding": CHUNK_ENCODING, "size_tokens": CHUNK_SIZE_TOKENS,
                     "overlap_tokens": CHUNK_OVERLAP_TOKENS,
                     "stride_tokens": CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS,
                     "max_concurrency": MAX_CHUNK_CONCURRENCY},
        "context_policy": {"target_tokens": CONTEXT_TARGET, "maximum_tokens": CONTEXT_MAXIMUM,
                           "framing_reserve": CONTEXT_RESERVE, "count_kind": "local_estimate",
                           "summarization": False},
        "jobs": {}, "downstream_integrated": False,
    })
    atomic_write_text(run / "README.md",
                      "# Layer 2 schema 9\n\nStatus: started.\n\nNot yet integrated with Layers 3/4.\n")
    return run
