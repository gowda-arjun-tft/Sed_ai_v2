"""Versioned research runs, frozen handoffs and dedicated checkpoint storage."""

import copy
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import tempfile
from contextlib import closing, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ML.deep_research.layer2.backend.fs import load_json, now_iso, sha256, storage_path, write_json
from ML.deep_research.layer2.backend.settings import REASONING_EFFORTS
from .document_records import REGISTRY_PATH, UPLOAD_POLICY, enrich, research_usable, source_entries
from .pipeline.create_run import local_path, require_current, verify_inputs
from .settings import PROMPTS_DIR, RESEARCH_INSTRUCTION_PATH, WEB_SEARCH_LEVELS
from .source_publication import parse_json, pretty_json

RESEARCH_PROMPTS = ("domain_research", "research_summary", "read_document")
CHECKPOINT_DEFAULT = "/var/lib/sedai/research-checkpoints"


def research_policy(reasoning="max") -> dict:
    """Freeze research independently of preparation and historical Layer 4 settings."""
    if reasoning not in REASONING_EFFORTS:
        raise ValueError("unsupported research reasoning effort")
    return {"version": 2, "status": "pending", "mode": "full", "reasoning_effort": reasoning,
            "max_concurrency": 1, "maximum_calls": 80, "wrap_up_after": 60, "finalize_after": 70,
            "target_tokens": 300_000, "maximum_tokens": 350_000,
            "summary_trigger_tokens": 250_000, "summary_keep_tokens": 100_000,
            "framing_reserve": 8_000, "file_input_max_bytes": 50_000_000,
            "checkpoint_root": os.environ.get("SEDAI_RESEARCH_CHECKPOINT_DIR", CHECKPOINT_DEFAULT),
            "identity": uuid4().hex, "jobs": {}}


def checkpoint_root(record) -> Path:
    """Require a writable, separately mounted Linux checkpoint volume before paid work."""
    policy = record["research"]
    if policy.get("version") not in {1, 2}:
        raise ValueError("unsupported research capability")
    configured = os.environ.get("SEDAI_RESEARCH_CHECKPOINT_DIR")
    if sys.platform != "linux" or not configured or configured != policy["checkpoint_root"]:
        raise RuntimeError("Research requires Docker and its frozen SEDAI_RESEARCH_CHECKPOINT_DIR")
    root = Path(configured).resolve()
    if not root.is_absolute() or root == Path("/") or root.is_relative_to(Path("/app")) or not os.path.ismount(root):
        raise RuntimeError("Research checkpoints require a dedicated mount outside /app")
    mounts = Path("/proc/self/mountinfo").read_text().splitlines()
    own = [line.split(" - ", 1)[1].split()[0] for line in mounts
           if line.split()[4] == str(root)]
    if not own or own[0] not in {"ext4", "xfs", "btrfs", "zfs"}:
        raise RuntimeError("Research checkpoints must use a Docker-managed Linux filesystem")
    with tempfile.TemporaryDirectory(prefix="check-", dir=root) as tmp:
        with closing(sqlite3.connect(Path(tmp) / "probe.sqlite3")) as conn:
            conn.execute("CREATE TABLE probe (value INTEGER)")
            conn.execute("INSERT INTO probe VALUES (1)")
            conn.commit()
            assert conn.execute("SELECT value FROM probe").fetchone() == (1,)
    return root


def checkpoint_path(record, domain, root) -> Path:
    """Derive checkpoint locations from trusted hex identities, never model paths."""
    identity = record["research"]["identity"]
    if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("invalid research identity")
    key = hashlib.sha256(domain["key"].encode()).hexdigest()[:24]
    return root / identity / f"{key}.sqlite3"


def eligible_sources(run, record, domain) -> str:
    """Project only eligible, unambiguous sources; never trust model-supplied upload receipts."""
    job = record["jobs"].get(domain["key"], {})
    registry = load_json(run / REGISTRY_PATH) if (run / REGISTRY_PATH).exists() else {}
    entries = []
    if job.get("status") == "complete" and job.get("response_path"):
        path = local_path(run, job["response_path"])
        if sha256(path) != job.get("response_sha256"):
            raise ValueError("Source response changed before research")
        try:
            value = enrich(parse_json(path.read_text(encoding="utf-8")), registry)
        except (ValueError, RecursionError):
            value = None
        for _, item, ambiguous in source_entries(value):
            if not ambiguous and research_usable(item):
                entries.append(item)
    # Use the existing duplicate-preserving renderer, not dict(item).
    from ML.deep_research.layer2.backend.publication import ObjectMembers

    def wire(value):
        """Serialize selected values without flattening duplicate arbitrary members."""
        if isinstance(value, ObjectMembers):
            return "{" + ",".join(json.dumps(k) + ":" + wire(v) for k, v in value) + "}"
        if isinstance(value, list):
            return "[" + ",".join(wire(v) for v in value) + "]"
        from decimal import Decimal
        return str(value) if isinstance(value, Decimal) else json.dumps(value, ensure_ascii=False)

    return pretty_json(wire(entries))


def create_research_run(prepared_run, runs_dir, *, public_input_confirmed=False,
                        research_reasoning_effort="max", web_search_context_size=None,
                        web_search_verbosity=None, research_instruction=RESEARCH_INSTRUCTION_PATH) -> Path:
    """Create a new linked run; copy prepared evidence without touching the parent or calling APIs."""
    from .document_uploads import run_writer

    if not public_input_confirmed:
        raise ValueError("Layer 3 requires public-input confirmation")
    policy = research_policy(research_reasoning_effort)
    instruction = storage_path(research_instruction).read_bytes()
    if not instruction.decode("utf-8-sig").strip():
        raise ValueError("User research instruction is empty")
    for value in (web_search_context_size, web_search_verbosity):
        if value is not None and value not in WEB_SEARCH_LEVELS:
            raise ValueError("unsupported web-search depth or verbosity")
    parent = storage_path(prepared_run)
    original = require_current(parent)
    verify_inputs(parent, original)
    if original["status"] not in {"complete", "partial"}:
        raise ValueError("Research requires settled complete or partial preparation")
    # Read-only historical parents may never have had a writer-lock file.
    guard = run_writer(parent) if (parent / "_internal/trace/writer.lock").exists() else nullcontext()
    with guard:
        snapshots = {p: local_path(parent, p).read_bytes() for p in original["inputs"]}
        record = copy.deepcopy(original)
        for job in original["jobs"].values():
            if not job.get("response_path"):
                continue
            path = local_path(parent, job["response_path"])
            if not path.exists():
                if job.get("status") == "complete":
                    raise ValueError("Completed prepared response is missing")
                continue
            if sha256(path) != job.get("response_sha256"):
                raise ValueError("Prepared response changed")
            snapshots[job["response_path"]] = path.read_bytes()
            for name in ("provider_message.json", "completion.json"):
                other = path.with_name(name)
                if other.exists():
                    snapshots[other.relative_to(parent).as_posix()] = other.read_bytes()
        registry = load_json(parent / REGISTRY_PATH) if (parent / REGISTRY_PATH).exists() else None
        if require_current(parent) != original:
            raise ValueError("Preparation changed while creating its research handoff")
    for name in RESEARCH_PROMPTS:
        snapshots[f"_internal/inputs/prompts/{name}.md"] = (PROMPTS_DIR / f"{name}.md").read_bytes()
    snapshots["_internal/inputs/user_research_instruction.md"] = instruction
    if registry is not None:
        snapshots["_internal/inputs/prepared_upload_registry.json"] = json.dumps(registry, ensure_ascii=False).encode()
    while True:
        run = parent.parent / f"L3_{datetime.now(UTC):%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"
        try:
            run.mkdir()
            break
        except FileExistsError:
            continue
    for relative, raw in snapshots.items():
        target = local_path(run, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    record["inputs"] = {p: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                        for p, raw in snapshots.items()}
    record.update(run_id=run.name, status="created", started_at=now_iso(), updated_at=now_iso(),
                  prepared_run={"path": str(parent), "run_id": original["run_id"],
                                "manifest_sha256": hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()},
                  discovery_status=original.get("discovery_status", original["status"]), research=policy)
    record["research"]["mode"] = "linked"
    record["document_uploads"] = {**copy.deepcopy(original.get("document_uploads", {})),
                                  "policy": dict(UPLOAD_POLICY),
                                  "status": original.get("document_uploads", {}).get("status", "not_run")}
    if web_search_context_size:
        record["web_search"]["context_size"] = web_search_context_size
    if web_search_verbosity:
        record["web_search"]["verbosity"] = web_search_verbosity
    if registry is not None:
        write_json(run / REGISTRY_PATH, registry)
    from .research_handoff import import_prior_work
    import_prior_work(parent, original, run, record)
    write_json(run / "run.json", record)
    from .source_publication import publish
    publish(run)
    return run
