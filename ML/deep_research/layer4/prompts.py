from __future__ import annotations

from pathlib import Path

from ML.deep_research.layer2.fs import read_text

from .settings import DOMAIN_NAMES, MISSING_EXTERNAL_REPORT


def _root(run_dir: Path) -> Path:
    return run_dir / "inputs" / "prompts"


def _prompt(run_dir: Path, name: str) -> str:
    return read_text(_root(run_dir) / name).strip() + "\n"


def _skill_body(path: Path) -> str:
    text = read_text(path).strip()
    if text.startswith("---\n"):
        _, _, text = text.partition("\n---\n")
    return text.strip() + "\n"


def internal_system_prompt(run_dir: Path) -> str:
    return _prompt(run_dir, "internal.md")


def candidate_system_prompt(run_dir: Path) -> str:
    return _prompt(run_dir, "external_candidates.md")


def researcher_system_prompt(run_dir: Path) -> str:
    return _skill_body(_root(run_dir) / "SKILL.md")


def synthesis_system_prompt(run_dir: Path) -> str:
    return _prompt(run_dir, "synthesis.md")


def internal_message(domain: str, layer3_report: str) -> str:
    return (
        "<internal_segregation_input>\n"
        f"<domain_name>\n{domain}\n</domain_name>\n"
        f"<layer3_domain_report>\n{layer3_report}\n</layer3_domain_report>\n"
        "</internal_segregation_input>"
    )


def candidate_message(domain: str, layer3_report: str) -> str:
    return (
        "<external_candidate_input>\n"
        f"<domain_name>\n{domain}\n</domain_name>\n"
        f"<asset_context>\n{layer3_report}\n</asset_context>\n"
        "</external_candidate_input>"
    )


def researcher_message(
    domain: str,
    layer3_report: str,
    candidate_report: str,
) -> str:
    return (
        "<external_research_input>\n"
        f"<domain_name>\n{domain}\n</domain_name>\n"
        f"<asset_context>\n{layer3_report}\n</asset_context>\n"
        f"<external_research_brief>\n{candidate_report}\n</external_research_brief>\n"
        "</external_research_input>"
    )


def synthesis_message(reports: dict[str, str]) -> str:
    sections = "\n".join(
        "<domain_external_report>\n"
        f"<domain_name>\n{name}\n</domain_name>\n"
        f"<external_research_report>\n{reports.get(name, MISSING_EXTERNAL_REPORT)}\n"
        "</external_research_report>\n"
        "</domain_external_report>"
        for name in DOMAIN_NAMES
    )
    return f"<external_synthesis_input>\n{sections}\n</external_synthesis_input>"
