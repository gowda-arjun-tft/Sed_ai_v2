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

from ..settings import (
    DOMAIN_NAMES,
    HARNESS_NAME,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_NAME,
    SCHEMA_VERSION,
    SUMMARIZATION_KEEP_TOKENS,
    SUMMARIZATION_TRIGGER_TOKENS,
)
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


def _markers(paths: list[Path]) -> dict[Path, list[str]]:
    return {
        path: [value.strip() for value in _MARKER.findall(read_text(path))]
        if path.is_file()
        else []
        for path in paths
    }


def run_checks(run_dir: Path) -> list[Check]:
    run = load_json(run_dir / "run.json")
    if run.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Layer 3 schema {run.get('schema_version')!r} cannot be checked as schema "
            f"{SCHEMA_VERSION}; start a fresh Layer 3 run"
        )
    checks: list[Check] = []

    def add(label: str, ok: bool, detail: str = "") -> None:
        checks.append((len(checks) + 1, label, bool(ok), detail))

    source_checks = run.get("source_l2", {}).get("checks", {})
    add(
        "The recorded Layer 2 result passed every check",
        isinstance(source_checks.get("run"), int)
        and source_checks.get("run") > 0
        and source_checks.get("failed") == 0
        and source_checks.get("passed") == source_checks.get("run"),
    )

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
    limits = run.get("limits", {})
    add(
        "Run schema, harness, model policy, provider, and public-input record are valid",
        run.get("schema_version") == SCHEMA_VERSION
        and run.get("harness") == HARNESS_NAME
        and run.get("provider") == "online"
        and run.get("model") == MODEL_NAME
        and run.get("public_input_confirmed") is True
        and run.get("model_context_window_tokens") == MODEL_INPUT_TOKEN_LIMIT
        and "input_tokens_per_model_call" not in limits
        and "output_tokens_per_model_call" not in limits
        and limits.get("summarization_trigger_tokens")
        == SUMMARIZATION_TRIGGER_TOKENS
        and limits.get("summarization_keep_tokens") == SUMMARIZATION_KEEP_TOKENS
        and "agent_model_calls" not in limits
        and "agent_timeout_seconds" not in limits
        and "clarification_batches" not in limits,
    )

    execution = run.get("execution", {})
    execution = execution if isinstance(execution, dict) else {}
    domain_execution = execution.get("domains", {})
    domain_execution = domain_execution if isinstance(domain_execution, dict) else {}
    review_execution = execution.get("review", {})
    review_execution = review_execution if isinstance(review_execution, dict) else {}
    clarification = execution.get("clarification")
    final_execution = execution.get("final", {})
    final_execution = final_execution if isinstance(final_execution, dict) else {}
    clarification_domains: Any = (
        clarification.get("domains", {}) if isinstance(clarification, dict) else {}
    )
    clarification_questions: Any = (
        clarification.get("questions", {}) if isinstance(clarification, dict) else {}
    )
    clarification_domains = (
        clarification_domains if isinstance(clarification_domains, dict) else {}
    )
    clarification_questions = (
        clarification_questions if isinstance(clarification_questions, dict) else {}
    )
    records: list[dict[str, Any]] = [
        *domain_execution.values(),
        review_execution,
        *clarification_domains.values(),
        final_execution,
    ]
    clarification_ok = clarification is None or (
        isinstance(clarification_questions, dict)
        and bool(clarification_questions)
        and set(clarification_questions).issubset(DOMAIN_NAMES)
        and set(clarification_domains) == set(clarification_questions)
        and all(
            isinstance(questions, list)
            and bool(questions)
            and all(isinstance(question, str) and question.strip() for question in questions)
            for questions in clarification_questions.values()
        )
        and all(
            isinstance(record, dict)
            and record.get("stage") == "clarification"
            and record.get("actor") == name
            and record.get("batch") == 1
            for name, record in clarification_domains.items()
        )
    )
    execution_ok = (
        isinstance(domain_execution, dict)
        and set(domain_execution) == set(DOMAIN_NAMES)
        and all(isinstance(record, dict) for record in records)
        and review_execution.get("stage") == "review"
        and review_execution.get("actor") == "property-reviewer"
        and final_execution.get("stage") == "synthesis"
        and final_execution.get("actor") == "property-synthesis"
        and clarification_ok
        and all(record.get("status") == "complete" for record in records)
        and all(
            record.get("thread_id")
            and isinstance(record.get("attempt"), int)
            and record.get("attempt", 0) >= 1
            and isinstance(record.get("model_turns"), int)
            and record.get("model_turns", -1) >= 0
            and isinstance(record.get("elapsed_seconds"), (int, float))
            and record.get("elapsed_seconds", -1) >= 0
            for record in records
        )
    )
    add(
        "Eight domains, one review, optional single clarification, and synthesis are complete",
        execution_ok
        and final_execution.get("outcome") in {"answered", "cannot_be_answered"},
    )

    domain_reports = [
        run_dir / "domains" / f"{slug(domain)}.md" for domain in DOMAIN_NAMES
    ]
    partial_reports = [
        run_dir / "domains" / f"{slug(domain)}.partial.md" for domain in DOMAIN_NAMES
    ]
    review = run_dir / "review" / "final_review.md"
    answer = run_dir / "research" / "final.md"
    add(
        f"All {len(DOMAIN_NAMES)} published and progressive domain reports are non-empty",
        all(_nonempty(path) for path in [*domain_reports, *partial_reports]),
        f"expected={len(domain_reports)} published and {len(partial_reports)} partial",
    )
    add("The adversarial review is non-empty", _nonempty(review))
    add("The final property answer is non-empty", _nonempty(answer))

    index, index_ok = _records(run_dir / "sources" / "index.jsonl")
    raw_files = list((run_dir / "sources" / "raw").glob("*/*.bin"))
    add(
        "Every retained raw source hashes to its filename",
        index_ok and all(sha256(path) == path.stem for path in raw_files),
    )
    source_ok = index_ok
    for item in index:
        raw = run_dir / str(item.get("raw_path", ""))
        text_path = run_dir / str(item.get("text_path", ""))
        source_ok = source_ok and raw.is_file() and sha256(raw) == item.get(
            "source_sha256"
        )
        if item.get("text_path"):
            source_ok = source_ok and text_path.is_file() and text_hash(
                read_text(text_path)
            ) == item.get("text_sha256")
    index_ids = [item.get("index_id") for item in index]
    source_ok = source_ok and len(index_ids) == len(set(index_ids))
    add("Source index paths and hashes resolve", source_ok)

    allowed_actors = set(DOMAIN_NAMES)
    queries, queries_ok = _records(run_dir / "sources" / "queries.jsonl")
    query_ids = [item.get("query_id") for item in queries]
    query_ok = queries_ok and len(query_ids) == len(set(query_ids))
    query_ok = query_ok and all(
        item.get("session_id")
        and item.get("agent") in allowed_actors
        and item.get("lens") == item.get("agent")
        and str(item.get("query", "")).strip()
        and item.get("query_id")
        == text_hash(
            f"{item.get('session_id')}\n{item.get('agent')}\n{item.get('lens')}\n"
            f"{' '.join(str(item.get('query', '')).split())}"
        )
        for item in queries
    )
    add("Query records are unique and structurally valid", query_ok)

    citations, citations_ok = _records(run_dir / "sources" / "citations.jsonl")
    citation_ids = [item.get("citation_id") for item in citations]
    store = SourceStore(run_dir)
    validation: dict[str, bool] = {}
    citation_identity_ok = True
    for citation in citations:
        citation_id = str(citation.get("citation_id", ""))
        try:
            validation[citation_id] = store.validate_citation(citation)[0]
        except (OSError, ValueError):
            validation[citation_id] = False
        citation_identity_ok = citation_identity_ok and (
            citation.get("agent") in allowed_actors
            and citation.get("lens") == citation.get("agent")
        )
    add(
        "Citation records are unique and exact quotations revalidate",
        citations_ok
        and len(citation_ids) == len(set(citation_ids))
        and citation_identity_ok
        and all(validation.values()),
    )

    report_paths = [*domain_reports, review, answer]
    markers = _markers(report_paths)
    marker_ok = all(
        validation.get(marker, False)
        for values in markers.values()
        for marker in values
    )
    add("Every emitted citation marker resolves to verified evidence", marker_ok)
    add(
        "An answered property has a verified final-answer citation",
        final_execution.get("outcome") != "answered"
        or any(validation.get(marker, False) for marker in markers[answer]),
    )

    usage, usage_ok = _records(run_dir / "usage.jsonl")
    usage_ids = [item.get("usage_id") for item in usage]
    token_fields = (
        "input_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    usage_ok = usage_ok and len(usage_ids) == len(set(usage_ids))
    for item in usage:
        phase = item.get("phase")
        tokens_ok = all(
            isinstance(item.get(field, 0), int) and item.get(field, 0) >= 0
            for field in token_fields
        )
        event_tokens_ok = phase in {"model", "web_search"} or all(
            item.get(field, 0) == 0 for field in token_fields
        )
        usage_ok = usage_ok and bool(
            item.get("usage_id")
            and item.get("session_id")
            and item.get("actor")
            and isinstance(phase, str)
            and phase.strip()
            and item.get("timestamp")
            and tokens_ok
            and event_tokens_ok
        )
    add("Usage and progress events are attributable, timestamped, and unique", usage_ok)

    _write_report(run_dir, run, checks)
    passed = sum(ok for _, _, ok, _ in checks)
    run["checks"] = {
        "run": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
    }
    run["usage"] = summarize_usage(run_dir)
    run["status"] = "verified" if passed == len(checks) else "failed_validation"
    run["finished_at"] = now_iso()
    write_json(run_dir / "run.json", run)
    return checks
