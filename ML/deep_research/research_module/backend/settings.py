"""Frozen Layer 3 identities and operational safety settings."""

from pathlib import Path

from ML.deep_research.domain_decider.backend.settings import (
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    MODEL_INPUT_TOKEN_LIMIT,
    REPO_ROOT,
    RUNS_DIR,
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR.parent / "ML" / "prompts"
SCHEMA_VERSION = 9
HARNESS_NAME = "parallel_source_finder"
SOURCE_SUGGESTION_PATH = REPO_ROOT / "inputs" / "source_suggestion.md"
RESEARCH_INSTRUCTION_PATH = REPO_ROOT / "inputs" / "user_research_instruction.md"
RESEARCH_CONFIG_PATH = REPO_ROOT / "inputs" / "research_config.json"
SOURCE_REASONING_EFFORT = "high"
SOURCE_SEARCH_DEPTH = "medium"
SOURCE_SEARCH_VERBOSITY = "low"
SOURCE_CONCURRENCY = 5

MODEL_TIMEOUT_SECONDS = 600
MODEL_MAX_RETRIES = 3
WEB_SEARCH_LEVELS = frozenset({"low", "medium", "high"})
FETCH_TIMEOUT_SECONDS = 30
MAX_SOURCE_BYTES = 10 * 1024 * 1024
