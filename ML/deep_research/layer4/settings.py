"""Frozen Layer 4 identities and shared domain names."""

from pathlib import Path

from ML.deep_research.layer3.settings import (
    DOMAIN_NAMES,
    REPO_ROOT,
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
SKILL_PATH = MODULE_DIR / "SKILL.md"
RUN_PREFIX = "L4"
SCHEMA_VERSION = 1
HARNESS_NAME = "external_dependency_direct_output"
LAYER3_SCHEMA_VERSION = 8
LAYER3_HARNESS_NAME = "domain_plain_research_direct_output"

INTERNAL_SEGREGATOR_NAME = "internal-segregator"
EXTERNAL_CANDIDATE_SEGREGATOR_NAME = "external-candidate-segregator"
EXTERNAL_RESEARCHER_NAME = "external-researcher"
SYNTHESIS_NAME = "external-synthesis"

MISSING_LAYER3_REPORT = "[No Layer 3 domain response was available for this domain.]"
MISSING_INTERNAL_REPORT = "[No internal segregation response was available for this domain.]"
MISSING_CANDIDATE_REPORT = (
    "[No external-candidate segregation response was available for this domain.]"
)
MISSING_EXTERNAL_REPORT = (
    "[No external research response was available for this domain.]"
)
