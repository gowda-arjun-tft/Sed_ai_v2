"""Non-mutating operational observations for source-discovery runs."""

from pathlib import Path

from .create_run import local_path, require_current
from ..source_publication import is_json
from ML.deep_research.layer2.backend.jobs import saved_text

Check = tuple[int, str, bool, str]


def run_checks(run_dir: Path) -> list[Check]:
    """Inspect saved source outputs without writing reports, changing status or invoking models."""
    run = require_current(run_dir)
    domains = run["domains"]
    terminal = sum(run["jobs"].get(d["key"], {}).get("status") in {"complete", "failed"}
                   for d in domains)
    available = 0
    for domain in domains:
        raw = saved_text(local_path(run_dir, domain["output_path"]))
        available += raw is not None and is_json(raw)
    checks = [
        (1, "Current source-discovery schema", True, ""),
        (2, "All domain jobs have terminal records", terminal == len(domains),
         f"{terminal}/{len(domains)} terminal"),
        (3, "Source JSON outputs available", bool(available),
         f"{available}/{len(domains)} available; content and access claims are not graded"),
    ]
    if run.get("research"):
        jobs = run["research"]["jobs"]
        complete = sum(j.get("status") == "complete" for j in jobs.values())
        available = sum(local_path(run_dir, j["output_path"]).exists() for j in jobs.values()
                        if j.get("status") == "complete")
        checks.append((4, "Research reports available", available == complete,
                       f"{available}/{len(domains)} available; report content is not graded"))
    return checks
