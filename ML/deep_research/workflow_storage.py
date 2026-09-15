"""Number allocation and frozen inputs for the thin, two-phase workflow."""

import hashlib
import re
from pathlib import Path

from .domain_decider.backend.fs import load_json, storage_path, write_json
from .domain_decider.backend.settings import REPO_ROOT, PROMPTS_DIR, PROMPT_FILES
from .research_module.backend.document_uploads import file_writer
from .research_module.backend.settings import PROMPTS_DIR as RESEARCH_PROMPTS


def allocate(runs_dir, fact_sheet):
    """Reserve a durable number under an OS lock; deletion never resets the high-water mark."""
    runs = storage_path(runs_dir)
    source = storage_path(fact_sheet).resolve()
    identity = (source.relative_to(REPO_ROOT).as_posix() if source.is_relative_to(REPO_ROOT)
                else source.as_posix())
    counter = runs / "_internal/workflow_groups.json"
    with file_writer(counter.with_suffix(".lock"), blocking=True):
        groups = load_json(counter) if counter.exists() else {}
        if identity not in groups:
            stem = re.sub(r"[^\w.-]+", "-", source.stem).strip(".-") or "factsheet"
            if stem.upper() in {"CON", "PRN", "AUX", "NUL", *[f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)]}:
                stem = "factsheet-" + stem
            stem = stem[:80]
            name, suffix = stem, 1
            existing = {v["group"].casefold() for v in groups.values()}
            while name.casefold() in existing or (runs / name).exists():
                suffix += 1
                name = f"{stem}_{suffix}"
            groups[identity] = {"group": name, "next_run": 1}
        entry = groups[identity]
        if (not isinstance(entry.get("group"), str) or Path(entry["group"]).name != entry["group"]
                or entry["group"] in {".", ".."} or type(entry.get("next_run")) is not int
                or entry["next_run"] < 1):
            raise ValueError("Invalid workflow number registry")
        group = runs / entry["group"]
        if not group.resolve().is_relative_to(runs.resolve()):
            raise ValueError("Workflow group escapes run storage")
        group.mkdir(parents=True, exist_ok=True)
        while True:
            number = entry["next_run"]
            entry["next_run"] += 1
            write_json(counter, groups)
            root = group / f"run_{number:03d}"
            try:
                root.mkdir()
                return root, identity, number
            except FileExistsError:
                continue


def input_snapshots(paths):
    """Read every user input and both phases' production prompts before the first call."""
    paths = dict(paths)
    paths.update({f"domain_prompts/{name}": PROMPTS_DIR / name for name in PROMPT_FILES.values()})
    paths.update({f"research_prompts/{name}.md": RESEARCH_PROMPTS / f"{name}.md"
                  for name in ("source_finder", "domain_research", "research_summary", "read_document")})
    snapshots = {}
    for name, path in paths.items():
        raw = storage_path(path).read_bytes()
        if not raw.decode("utf-8-sig").strip():
            raise ValueError(f"Required workflow input is empty: {name}")
        snapshots[name] = raw
    return snapshots


def save_inputs(root, snapshots):
    """Freeze exact bytes and their hashes; failures remain visible rather than overwriting runs."""
    manifest = {}
    for name, raw in snapshots.items():
        relative = "_internal/inputs/" + name
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest[relative] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return manifest


def child_path(root, relative):
    """Refuse corrupted manifests that escape this workflow's owned storage."""
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Workflow path escapes its run")
    return path
