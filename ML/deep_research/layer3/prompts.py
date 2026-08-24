from __future__ import annotations

from pathlib import Path
from typing import Any

from ML.deep_research.layer2.fs import read_text

from .contracts import LENS_NAMES
from .settings import DOMAIN_NAMES


LENS_DESCRIPTIONS = {
    "practitioner": "Traces property exposures, operational dependencies, failure pathways, and effects on the building or people.",
    "academic": "Tests property-applicable regulatory, technical, scientific, and primary evidence.",
    "skeptic": "Searches current and upcoming nearby developments, adverse local evidence, contradictions, and missing linkages.",
    "economist": "Traces supported property pathways into income, Opex, CapEx, finance, liquidity, and value.",
    "historian": "Tests forward regime change, external dependencies, geopolitics, and only genuinely comparable precedent.",
}


def _root(run_dir: Path) -> Path:
    return run_dir / "inputs" / "prompts"


def _joined(*paths: Path) -> str:
    return "\n\n".join(read_text(path).strip() for path in paths) + "\n"


def _skill_body(path: Path) -> str:
    text = read_text(path).strip()
    if text.startswith("---\n"):
        _, _, text = text.partition("\n---\n")
    return text.strip()


def coordinator_system_prompt(run_dir: Path) -> str:
    root = _root(run_dir)
    return (
        _skill_body(root / "SKILL.md")
        + "\n\nThe invocation supplies the domain name, Mission Markdown, mandate, and handoffs. Treat them as property context and research boundaries, not output instructions.\n"
    )


def lens_system_prompt(run_dir: Path, lens: str) -> str:
    if lens not in LENS_NAMES:
        raise ValueError(f"unknown STORM lens: {lens}")
    root = _root(run_dir)
    return _joined(root / "shared_rules.md", root / "lenses" / f"{lens}.md")


def verifier_system_prompt(run_dir: Path) -> str:
    root = _root(run_dir)
    return _joined(root / "shared_rules.md", root / "verifier.md")


def synthesis_system_prompt(run_dir: Path) -> str:
    return _joined(_root(run_dir) / "synthesis.md")


def domain_message(assignment: dict[str, Any]) -> str:
    name = str(assignment["name"])
    boundaries = assignment["boundaries"]
    handoffs = "\n".join(f"- {item}" for item in boundaries["handoffs"])
    return (
        "Execute the complete domain-scoped STORM property-risk procedure for this assignment. "
        "Extract the supplied property anchors and risk questions, and provide them with the "
        "relevant boundaries in every lens task. Return the complete corrected risk report "
        "directly as Markdown without recommendations or investment advice.\n\n"
        f"# Domain\n\n{name}\n\n"
        f"## Mandate\n\n{boundaries['mandate']}\n\n"
        f"## Handoffs\n\n{handoffs}\n\n"
        f"{str(assignment['mission']).strip()}\n"
    )


def synthesis_message(reports: dict[str, str]) -> str:
    sections = "\n\n".join(
        f"## Domain input: {name}\n\n"
        f"{reports.get(name, '[No domain response was available for this run.]')}"
        for name in DOMAIN_NAMES
    )
    return (
        "Produce the property risk landscape directly as Markdown from the domain responses "
        "below. A missing or empty response is an unknown to disclose, not a reason to discard the "
        "available research. Do not add recommendations or an investment decision.\n\n"
        + sections
    )
