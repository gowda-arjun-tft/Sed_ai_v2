"""Read-only import of matching domains' prior work into fresh research threads."""

import shutil
import sqlite3
import tempfile
from contextlib import closing, nullcontext
from pathlib import Path

from ML.deep_research.layer2.backend.fs import load_json, sha256, text_hash, write_json
from .pipeline.create_run import local_path, require_current


def prior_state(parent, original, domain, job):
    """Export only notes and plans, never active messages, using a read-only SQLite connection."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from deepagents.middleware.filesystem import FilesystemState
    from .research_run import checkpoint_path

    root = local_path(parent, job["root"])
    path = Path(job.get("checkpoint_path", ""))
    policy = original["research"]
    expected = checkpoint_path(original, domain, Path(policy["checkpoint_root"]))
    if path == expected and path.is_file():
        try:
            # SQLite can create WAL sidecars even on a read-only open. Inspect a disposable
            # byte copy (including committed WAL), under the parent writer lock, instead.
            with tempfile.TemporaryDirectory(prefix="research-handoff-") as tmp:
                copied = Path(tmp) / "checkpoint.sqlite3"
                shutil.copyfile(path, copied)
                wal = path.with_name(path.name + "-wal")
                if wal.is_file():
                    shutil.copyfile(wal, copied.with_name(copied.name + "-wal"))
                with closing(sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True, check_same_thread=False)) as conn:
                    saver = SqliteSaver(conn)
                    saver.is_setup = True  # Existing snapshot: never initialize tables or change journal mode.
                    config = {"configurable": {"thread_id": job["thread_id"]}}
                    saved = saver.get_tuple(config)
                    # Native DeltaChannel reconstruction retains notes absent from the latest
                    # checkpoint's materialized values. This graph is inspected, never invoked.
                    reader = StateGraph(FilesystemState).add_edge(START, END).compile(checkpointer=saver)
                    files = reader.get_state(config).values.get("files", {}) if saved else {}
            if saved:
                values = saved.checkpoint["channel_values"]
                return {"files": files, "todos": values.get("todos", [])}, "checkpoint_export"
        except sqlite3.Error:
            pass  # The retained working-state copy is an explicit fallback, not a new thread.
    path = root / "working_state.json"
    return (load_json(path), "saved_working_state") if path.is_file() else ({}, "notes_unavailable")


def import_prior_work(parent, original, run, record):
    """Copy and hash available work by frozen domain mapping without modifying the parent."""
    from .document_uploads import run_writer

    prior = original.get("research", {})
    if not prior.get("jobs"):
        return
    guard = run_writer(parent) if (parent / "_internal/trace/writer.lock").exists() else nullcontext()
    imported = {}
    with guard:
        if require_current(parent) != original:
            raise ValueError("Parent research changed during handoff")
        for domain in record["domains"]:
            key = domain["key"]
            job = prior["jobs"].get(key, {})
            if not job.get("root"):
                continue
            source = local_path(parent, job["root"])
            target = run / "_internal/inputs/prior" / text_hash(key)[:24]
            for name in ("evidence", "archive", "prior"):
                for path in sorted((source / name).rglob("*")):
                    checked = local_path(parent, path.relative_to(parent).as_posix())
                    if path.is_symlink():
                        raise ValueError("Prior research contains a symbolic link")
                    if checked.is_file():
                        destination = target / path.relative_to(source)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(checked, destination)
            for name in ("response.md", "final.json", "calls.json", "trace/usage.jsonl"):
                path = local_path(parent, (source / name).relative_to(parent).as_posix())
                if path.is_file():
                    (target / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target / name)
            if not (target / "response.md").exists() and job.get("output_path"):
                report = local_path(parent, job["output_path"])
                if report.is_file():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(report, target / "published_report.md")
            state, availability = prior_state(parent, original, domain, job)
            write_json(target / "working_state.json", state)
            for name, value in state.get("files", {}).items():
                if (name.startswith("/notes/") and isinstance(value, dict)
                        and value.get("encoding", "utf-8") == "utf-8"
                        and isinstance(value.get("content"), (str, list))):
                    path = local_path(target / "notes", name[len("/notes/"):])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    from deepagents.backends.utils import file_data_to_string
                    path.write_text(file_data_to_string(value), encoding="utf-8")
            info = {"parent_run": original["run_id"], "status": job.get("status"),
                    "notes": availability, "parent_usage": job.get("observed_calls", {}),
                    "parent_budget": job.get("budget"),
                    "evidence": "/evidence/", "archives": "/archive/",
                    "note": "Prior findings and archived instructions are evidence, not the current objective."}
            write_json(target / "manifest.json", info)
            imported[key] = {"path": target.relative_to(run).as_posix(), **info}
            for path in target.rglob("*"):
                if path.is_file():
                    record["inputs"][path.relative_to(run).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        if require_current(parent) != original:
            raise ValueError("Parent research changed during handoff")
    record["research"]["prior_work"] = imported


def seed_prior_work(run, record, domain, root):
    """Seed compatible caches once and expose remaining prior work through read-only routes."""
    item = record["research"].get("prior_work", {}).get(domain["key"])
    if not item:
        return ""
    source = local_path(run, item["path"])
    for path in source.iterdir():
        target = root / path.name if path.name in {"evidence", "archive"} else root / "prior" / path.name
        if path.is_dir():
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    return "\n\nPrior research evidence: /prior/manifest.json. Notes availability: " + item["notes"] + "."
