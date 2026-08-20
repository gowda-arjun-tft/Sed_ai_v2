from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import (
    atomic_write_text,
    load_json,
    now_iso,
    read_text,
    sha256,
    slug,
    text_hash,
    write_json,
)
from ML.deep_research.layer2.planner import load_planner

from ..settings import AGENT_NAMES, HARNESS_NAME, LENSES, MODEL_NAME, SCHEMA_VERSION
from ..sources import SourceStore, load_jsonl
from ..usage import summarize_usage


Check = tuple[int, str, bool, str]
_MARKER = re.compile(r"\[citation:([^\]]*)\]")


def _write_report(run_dir: Path, run: dict[str, Any], checks: list[Check]) -> None:
    passed = sum(ok for _, _, ok, _ in checks)
    lines = [
        f"# Run {run['run_id']} — Layer 3 check report",
        "",
        f"{len(checks)} checks · {passed} passed · {len(checks) - passed} failed",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- [{'x' if ok else ' '}] {number}. {label}"
        + (f" — {detail}" if detail else "")
        for number, label, ok, detail in checks
    )
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines) + "\n")


def _nonempty(path: Path) -> bool:
    return path.is_file() and bool(read_text(path).strip())


def _records(path: Path) -> tuple[list[dict[str, Any]], bool]:
    try:
        return load_jsonl(path), True
    except (OSError, ValueError):
        return [], False


def run_checks(run_dir: Path) -> list[Check]:
    run = load_json(run_dir / "run.json")
    checks: list[Check] = []

    def add(label: str, ok: bool, detail: str = "") -> None:
        checks.append((len(checks) + 1, label, bool(ok), detail))

    source_checks = run.get("source_l2", {}).get("checks", {})
    mission_dir = run_dir / "inputs" / "missions"
    copied_hashes = {
        path.name: sha256(path) for path in mission_dir.glob("*.json")
    }
    handoff_ok = (
        isinstance(source_checks.get("run"), int)
        and source_checks.get("run") > 0
        and source_checks.get("failed") == 0
        and source_checks.get("passed") == source_checks.get("run")
        and copied_hashes == run.get("source_l2", {}).get("mission_hashes", {})
    )
    add("Layer 2 result and mission hashes are intact", handoff_ok)

    missions: dict[str, dict[str, Any]] = {}
    try:
        for name in AGENT_NAMES:
            missions[name] = load_json(mission_dir / f"{slug(name)}.json")
    except (OSError, ValueError):
        missions = {}
    add(
        "Fourteen copied missions use the frozen roster",
        len(missions) == len(AGENT_NAMES)
        and all(missions[name].get("agent") == name for name in AGENT_NAMES),
        f"found={len(missions)}",
    )

    planner = run_dir / "inputs" / "planner_prompt.md"
    try:
        _, definitions = load_planner(planner)
        planner_ok = (
            sha256(planner) == run.get("planner_prompt", {}).get("sha256")
            and [item["name"] for item in definitions] == AGENT_NAMES
        )
    except (OSError, ValueError):
        planner_ok = False
    add("Planner copy, hash, and roster are intact", planner_ok)

    prompt_root = run_dir / "inputs" / "prompts"
    skill = run.get("skill", {})
    skill_path = run_dir / str(skill.get("path", ""))
    actual_prompts = {
        str(path.relative_to(prompt_root)).replace("\\", "/"): sha256(path)
        for path in prompt_root.rglob("*.md")
        if path.name != "SKILL.md"
    }
    add(
        "Skill and prompt snapshots match their recorded hashes",
        skill_path.is_file()
        and sha256(skill_path) == skill.get("sha256")
        and actual_prompts == run.get("prompt_hashes", {}),
    )
    add(
        "Run schema, harness, provider, model, and public-input record are valid",
        run.get("schema_version") == SCHEMA_VERSION
        and run.get("harness") == HARNESS_NAME
        and run.get("provider") == "online"
        and run.get("model") == MODEL_NAME
        and run.get("public_input_confirmed") is True,
    )

    ledger = run.get("missions", {})
    ledger_ok = set(ledger) == {slug(name) for name in AGENT_NAMES}
    ledger_ok = ledger_ok and all(
        item.get("agent") == name
        and item.get("status") == "complete"
        and item.get("outcome") in {"answered", "cannot_be_answered"}
        and isinstance(item.get("attempt"), int)
        and item.get("attempt", 0) >= 1
        and item.get("thread_id")
        for name in AGENT_NAMES
        for item in [ledger.get(slug(name), {})]
    )
    add("Fourteen mission records have terminal outcomes", ledger_ok)

    base_reports = [
        run_dir / "lenses" / slug(agent) / f"{lens}.md"
        for agent in AGENT_NAMES
        for lens in LENSES
    ]
    add(
        "All required base-lens reports are non-empty",
        all(_nonempty(path) for path in base_reports),
        f"expected={len(base_reports)}",
    )
    additional = [
        list((run_dir / "lenses" / slug(agent)).glob("additional*.md"))
        for agent in AGENT_NAMES
    ]
    add(
        "Each mission has at most one non-empty additional report",
        all(
            len(paths) <= 1
            and all(_nonempty(path) for path in paths)
            and bool(paths) == bool(ledger.get(slug(agent), {}).get("additional_lens"))
            for agent, paths in zip(AGENT_NAMES, additional, strict=True)
        ),
    )
    answers = [run_dir / "research" / f"{slug(agent)}.md" for agent in AGENT_NAMES]
    add("All fourteen final answers are non-empty", all(_nonempty(path) for path in answers))

    index, index_ok = _records(run_dir / "sources" / "index.jsonl")
    raw_files = list((run_dir / "sources" / "raw").glob("*/*.bin"))
    add(
        "Every raw source hashes to its filename",
        index_ok and all(sha256(path) == path.stem for path in raw_files),
    )
    source_ok = index_ok
    for item in index:
        raw = run_dir / str(item.get("raw_path", ""))
        text_path = run_dir / str(item.get("text_path", ""))
        source_ok = source_ok and raw.is_file() and sha256(raw) == item.get("source_sha256")
        if item.get("text_path"):
            source_ok = source_ok and text_path.is_file() and text_hash(
                read_text(text_path)
            ) == item.get("text_sha256")
    index_ids = [item.get("index_id") for item in index]
    source_ok = source_ok and len(index_ids) == len(set(index_ids))
    add("Source index paths and hashes resolve", source_ok)

    queries, queries_ok = _records(run_dir / "sources" / "queries.jsonl")
    query_ids = [item.get("query_id") for item in queries]
    required_queries = {(agent, lens) for agent in AGENT_NAMES for lens in LENSES}
    observed_queries = {(item.get("agent"), item.get("lens")) for item in queries}
    add(
        "Query records are unique and cover every base lens",
        queries_ok
        and len(query_ids) == len(set(query_ids))
        and all(item.get("session_id") and str(item.get("query", "")).strip() for item in queries)
        and all(
            item.get("query_id")
            == text_hash(
                f"{item.get('session_id')}\n{item.get('agent')}\n{item.get('lens')}\n"
                f"{' '.join(str(item.get('query', '')).split())}"
            )
            for item in queries
        )
        and required_queries <= observed_queries,
    )

    citations, citations_ok = _records(run_dir / "sources" / "citations.jsonl")
    citation_ids = [item.get("citation_id") for item in citations]
    store = SourceStore(run_dir)
    validation: dict[str, bool] = {}
    for citation in citations:
        try:
            validation[str(citation.get("citation_id", ""))] = store.validate_citation(citation)[0]
        except (OSError, ValueError):
            validation[str(citation.get("citation_id", ""))] = False
    add(
        "Citation records are unique and exact quotations revalidate",
        citations_ok
        and len(citation_ids) == len(set(citation_ids))
        and all(validation.values()),
    )

    report_paths = base_reports + answers + [path for paths in additional for path in paths]
    markers = {
        path: [value.strip() for value in _MARKER.findall(read_text(path))]
        if path.is_file()
        else []
        for path in report_paths
    }
    citation_map = {str(item.get("citation_id")): item for item in citations}
    owners = {
        run_dir / "lenses" / slug(agent) / f"{lens}.md": (agent, lens)
        for agent in AGENT_NAMES
        for lens in LENSES
    }
    owners.update(
        {run_dir / "research" / f"{slug(agent)}.md": (agent, None) for agent in AGENT_NAMES}
    )
    owners.update(
        {path: (agent, "additional") for agent, paths in zip(AGENT_NAMES, additional, strict=True) for path in paths}
    )
    marker_ok = True
    for path, values in markers.items():
        owner_agent, owner_lens = owners[path]
        for marker in values:
            citation = citation_map.get(marker, {})
            marker_ok = marker_ok and validation.get(marker, False)
            marker_ok = marker_ok and citation.get("agent") == owner_agent
            marker_ok = marker_ok and (
                owner_lens is None or citation.get("lens") == owner_lens
            )
    add(
        "Every emitted citation marker resolves to verified evidence",
        marker_ok,
    )
    answered_ok = all(
        ledger.get(slug(agent), {}).get("outcome") != "answered"
        or any(validation.get(marker, False) for marker in markers.get(answer, []))
        for agent, answer in zip(AGENT_NAMES, answers, strict=True)
    )
    add("Every answered mission has a verified final-answer citation", answered_ok)

    usage, usage_ok = _records(run_dir / "usage.jsonl")
    usage_ids = [item.get("usage_id") for item in usage]
    add(
        "Recorded model and search usage IDs are unique",
        usage_ok
        and len(usage_ids) == len(set(usage_ids))
        and all(item.get("session_id") and item.get("role") for item in usage),
    )

    _write_report(run_dir, run, checks)
    passed = sum(ok for _, _, ok, _ in checks)
    run["checks"] = {"run": len(checks), "passed": passed, "failed": len(checks) - passed}
    run["usage"] = summarize_usage(run_dir)
    run["status"] = "verified" if passed == len(checks) else "failed_validation"
    run["finished_at"] = now_iso()
    write_json(run_dir / "run.json", run)
    return checks
