"""Frozen Layer 3 identities and operational safety settings."""

from pathlib import Path

from ML.deep_research.layer2.settings import (
    AGENT_NAMES,
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    MODEL_SPEC,
    REASONING_EFFORT,
    REPO_ROOT,
    RUNS_DIR,
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
SKILL_PATH = MODULE_DIR / "SKILL.md"
RUN_PREFIX = "L3"
SCHEMA_VERSION = 2
HARNESS_NAME = "mission_supervisor"
CHECKPOINT_PACKAGE_VERSION = "3.1.1"

MODEL_TIMEOUT_SECONDS = 600
MODEL_MAX_RETRIES = 2
FETCH_TIMEOUT_SECONDS = 30
MAX_SOURCE_BYTES = 10 * 1024 * 1024

LENSES = {
    "practitioner": "How the work is done in practice, and what it costs.",
    "academic": "What research and published standards establish.",
    "economist": "What it is worth, and who ultimately pays.",
    "historian": "How comparable cases turned out, and what precedent exists.",
    "skeptic": "Test every connection and explain why the answer may be wrong.",
}
