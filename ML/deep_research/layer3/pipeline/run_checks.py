"""Optional operational report; never grades or blocks model output."""

from __future__ import annotations

from pathlib import Path

from ML.deep_research.layer2.fs import atomic_write_text, load_json, slug

from ..settings import DOMAIN_NAMES, SCHEMA_VERSION


Check = tuple[int, str, bool, str]


def run_checks(run_dir: Path) -> list[Check]:
    run = load_json(run_dir / "run.json")
    checks: list[Check] = []

    def add(label: str, ok: bool, detail: str = "") -> None:
        checks.append((len(checks) + 1, label, bool(ok), detail))

    add("Run metadata uses the current schema", run.get("schema_version") == SCHEMA_VERSION)
    domains = run.get("execution", {}).get("domains", {})
    add(
        "All eight domain invocations have a terminal record",
        all(domains.get(name, {}).get("status") in {"complete", "failed"} for name in DOMAIN_NAMES),
    )
    available = [
        name
        for name in DOMAIN_NAMES
        if (run_dir / "domains" / slug(name) / "final.md").is_file()
    ]
    add(
        "Domain responses were saved",
        bool(available),
        f"{len(available)}/{len(DOMAIN_NAMES)} available",
    )
    add("The synthesis response was saved", (run_dir / "research" / "final.md").is_file())

    passed = sum(ok for _, _, ok, _ in checks)
    lines = [
        f"# Run {run.get('run_id', run_dir.name)} — optional operational report",
        "",
        "This report does not grade, reject, repair, or retry model content.",
        "",
        f"{len(checks)} observations · {passed} true · {len(checks) - passed} false",
        "",
        *(
            f"- [{'x' if ok else ' '}] {number}. {label}"
            + (f" — {detail}" if detail else "")
            for number, label, ok, detail in checks
        ),
        "",
    ]
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines))
    return checks
