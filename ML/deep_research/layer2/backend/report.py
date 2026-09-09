"""Observational schema-6 serialization, persistence and assignment diagnostics."""

from pathlib import Path

from .create_run import require_current
from .fs import sha256, storage_path
from .jobs import saved_object


def run_checks(run_dir: Path) -> list[tuple[int, str, bool, str]]:
    """Input a schema-6 run; return technical observations without writes or model calls."""
    run_dir = storage_path(run_dir)
    record = require_current(run_dir)
    inputs_ok = all((run_dir / "_internal/inputs" / name).is_file()
                    and sha256(run_dir / "_internal/inputs" / name) == info["sha256"]
                    for name, info in record["inputs"].items())
    manifest = run_dir / "_internal/trace/source/manifest.json"
    inputs_ok = inputs_ok and manifest.is_file() and sha256(manifest) == record["source_manifest_sha256"]
    jobs = record["jobs"]
    readable = sum(saved_object(run_dir / row["response_path"]) is not None
                   for row in jobs.values())
    coverage = record.get("coverage", {})
    return [
        (1, "Frozen inputs intact", inputs_ok, f"inputs={len(record['inputs'])}"),
        (2, "Saved job responses readable", readable == len(jobs),
         f"readable={readable} jobs={len(jobs)}"),
        (3, "Execution failures", all(j["status"] != "failed" for j in jobs.values()),
         f"status={record['status']}"),
        (4, "Recorded-fact assignment coverage (not source completeness)",
         bool(coverage) and not coverage.get("unresolved_facts"), str(coverage)),
    ]
