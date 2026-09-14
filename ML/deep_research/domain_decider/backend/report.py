"""Observational schema-9 frozen-file, execution and ID-routing diagnostics."""

from pathlib import Path

from .create_run import require_current
from .fs import sha256, storage_path
from .jobs import saved_text


def run_checks(run_dir: Path) -> list[tuple[int, str, bool, str]]:
    """Input a current run; return observations without writes, log appends or model calls."""
    run = storage_path(run_dir)
    record = require_current(run)
    intact = all((run / "_internal/inputs" / name).is_file()
                 and sha256(run / "_internal/inputs" / name) == info["sha256"]
                 for name, info in record["inputs"].items())
    manifest = run / "_internal/trace/source/manifest.json"
    intact = intact and manifest.is_file() and sha256(manifest) == record["source_manifest_sha256"]
    jobs = record["jobs"]
    readable = sum(saved_text(run / row["response_path"]) is not None for row in jobs.values())
    expected = record["source_windows"] * 2 + 1
    completed = sum(row["status"] == "complete" for row in jobs.values())
    publication = record.get("publication", {})
    return [(1, "Frozen inputs intact", intact, f"inputs={len(record['inputs'])}"),
            (2, "Saved job responses readable", readable == len(jobs), f"readable={readable} jobs={len(jobs)}"),
            (3, "Execution complete", completed == expected and record["status"] == "complete",
             f"completed={completed}/{expected} status={record['status']}"),
            (4, "Routing observations (not source completeness)",
             bool(publication) and not publication.get("routing_issues"), str(publication))]
