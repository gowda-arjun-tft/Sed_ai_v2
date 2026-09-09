"""Create schema-6 runs after input preflight and one source-tokenization pass."""

import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path

from .fs import now_iso, run_group_name, sha256, write_json, atomic_write_text, storage_path
from .settings import (
    CHUNK_ENCODING, CHUNK_INPUT_PARTITIONING, CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS, CHUNK_STRATEGY, CONTEXT_MAXIMUM, CONTEXT_RESERVE,
    CONTEXT_TARGET, DEEPAGENTS_VERSION, LAYER2_SCHEMA_VERSION,
    MAX_CHUNK_CONCURRENCY, MODEL_NAME, PROMPTS_DIR, PROMPT_FILES, PROVIDER_MAX_RETRIES,
    REASONING_EFFORT, REASONING_EFFORTS, STAGES,
)
from .windows import source_windows


def require_current(run_dir: Path) -> dict:
    """Input a run path; return schema-6 metadata or reject historical execution unchanged."""
    from .fs import load_json

    record = load_json(run_dir / "run.json")
    if not isinstance(record, dict) or record.get("schema_version") != LAYER2_SCHEMA_VERSION:
        raise ValueError("Layer 2 schema 6 is required; schema 2/3/4/5 runs are read-only history")
    return record


def create_run(
    fact_sheet: Path, domain_plugin: Path, requirements: Path, runs_dir: Path,
    *, reasoning_effort: str = REASONING_EFFORT,
) -> Path:
    """Input three user paths and root; return a frozen schema-6 run without model calls."""
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort}")
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
    write_json(run / "_internal" / "trace" / "source" / "manifest.json", [
        {k: v for k, v in window.items() if k not in {"overlap_context", "new_content"}}
        for window in windows
    ])
    write_json(run / "run.json", {
        "schema_version": LAYER2_SCHEMA_VERSION, "run_id": run.name,
        "run_group": group.name, "status": "started", "started_at": now_iso(),
        "inputs": metadata, "model": MODEL_NAME, "reasoning_effort": reasoning_effort,
        "source_manifest_sha256": sha256(run / "_internal" / "trace" / "source" / "manifest.json"),
        "deepagents_version": DEEPAGENTS_VERSION, "provider_max_retries": PROVIDER_MAX_RETRIES,
        "chunking": {"strategy": CHUNK_STRATEGY, "input_partitioning": CHUNK_INPUT_PARTITIONING,
                     "encoding": CHUNK_ENCODING, "size_tokens": CHUNK_SIZE_TOKENS,
                     "overlap_tokens": CHUNK_OVERLAP_TOKENS,
                     "stride_tokens": CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS,
                     "max_concurrency": MAX_CHUNK_CONCURRENCY},
        "context_policy": {"target_tokens": CONTEXT_TARGET, "maximum_tokens": CONTEXT_MAXIMUM,
                           "framing_reserve": CONTEXT_RESERVE, "count_kind": "local_estimate",
                           "history": "retrievable_pointers", "summarization": False},
        "jobs": {}, "downstream_integrated": False, "design_tool_free": True,
    })
    atomic_write_text(run / "README.md",
                      "# Layer 2 schema 6\n\nStatus: started.\n\nNot yet integrated with Layers 3/4.\n")
    return run
