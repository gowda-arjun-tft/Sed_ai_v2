"""Frozen Layer 3 identities and operational safety settings."""

from pathlib import Path

from ML.deep_research.layer2.settings import (
    AGENT_NAMES,
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_SPEC,
    REPO_ROOT,
    RUNS_DIR,
    SUMMARIZATION_KEEP_TOKENS,
    SUMMARIZATION_TRIGGER_TOKENS,
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
SKILL_PATH = MODULE_DIR / "SKILL.md"
RUN_PREFIX = "L3"
SCHEMA_VERSION = 5
HARNESS_NAME = "progressive_direct_domain_research"
CHECKPOINT_PACKAGE_VERSION = "3.1.1"

MODEL_TIMEOUT_SECONDS = 600
MODEL_MAX_RETRIES = 2
REASONING_EFFORT = "high"
FETCH_TIMEOUT_SECONDS = 30
MAX_SOURCE_BYTES = 10 * 1024 * 1024

# Layer 2 owns the ordered domain roster. Layer 3 consumes those mission files
# one-for-one so the two layers cannot silently disagree about responsibility.
DOMAIN_NAMES = tuple(AGENT_NAMES)
