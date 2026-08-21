from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import read_text, slug
from ML.deep_research.layer2.planner import load_planner

from .settings import DOMAIN_NAMES


def _root(run_dir: Path) -> Path:
    return run_dir / "inputs" / "prompts"


def _joined(*paths: Path) -> str:
    return "\n\n".join(read_text(path).strip() for path in paths) + "\n"


def domain_system_prompt(run_dir: Path, domain: str) -> str:
    if domain not in DOMAIN_NAMES:
        raise ValueError(f"unknown Layer 3 domain: {domain}")
    root = _root(run_dir)
    _, definitions = load_planner(run_dir / "inputs" / "planner_prompt.md")
    definition = next(item for item in definitions if item["name"] == domain)
    handoffs = "\n".join(f"- {item}" for item in definition["handoffs"])
    return (
        _joined(root / "shared_rules.md", root / "five_questions.md")
        + f"\n# {domain}\n\n## Positive mandate\n\n{definition['mandate'].strip()}"
        + f"\n\n## Handoffs\n\n{handoffs}\n"
    )


def reviewer_system_prompt(run_dir: Path) -> str:
    return _joined(_root(run_dir) / "reviewer.md")


def synthesis_system_prompt(run_dir: Path) -> str:
    return _joined(_root(run_dir) / "synthesis.md")


def domain_message(
    assignment: dict[str, Any],
    *,
    batch: int,
    questions: list[str] | None = None,
    previous_report: str = "",
) -> str:
    payload = {
        "round": "initial" if batch == 0 else f"clarification-{batch}",
        "mission": assignment.get("mission", {}),
        "questions": questions or [],
        "previous_report": previous_report,
    }
    return (
        "Research only this domain. Append every decision-relevant unit immediately with "
        "append_report(fragment_id, markdown). Return ResearchOutcome after all five ledger "
        "facets have a terminal status.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def review_message() -> str:
    paths = [f"/domains/{slug(name)}.md" for name in DOMAIN_NAMES]
    return (
        f"Review all eight initial reports once: {paths}. Return ReviewOutcome with the complete "
        "review_markdown and one optional batch of bare clarification questions by domain. Return "
        "no questions when the remaining gaps should be reported honestly as unknowns."
    )


def synthesis_message() -> str:
    paths = [f"/domains/{slug(name)}.md" for name in DOMAIN_NAMES]
    return (
        f"Read the eight reports, including appended clarification: {paths}. Read /review.md. "
        "Return the final property decision as Markdown directly. Do not return JSON, a schema, "
        "field names, or commentary outside the document."
    )
