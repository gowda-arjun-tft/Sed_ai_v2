"""Frozen Layer 2 policies and shared model configuration."""

from pathlib import Path


MODEL_SPEC = "openai:gpt-5.6-luna"
MODEL_NAME = "gpt-5.6-luna"
REASONING_EFFORT = "high"
REASONING_EFFORTS = frozenset({"low", "medium", "high", "max"})
# Read from the model profile, not assumed: `init_chat_model(MODEL_SPEC).profile`
# reports max_input_tokens = 1_050_000. Layer 3 uses this shared profile value;
# Layer 2's separate 300K/350K assembled-input policy is defined below.
MODEL_INPUT_TOKEN_LIMIT = 1_050_000
PROVIDER_MAX_RETRIES = 3

LAYER2_SCHEMA_VERSION = 6
CHUNK_STRATEGY = "fixed_token_windows"
CHUNK_INPUT_PARTITIONING = "overlap_context_v1"
CHUNK_SIZE_TOKENS = 60_000
CHUNK_OVERLAP_TOKENS = 10_000
CHUNK_ENCODING = "o200k_base"
MAX_CHUNK_CONCURRENCY = 5

DEEPAGENTS_VERSION = "0.7.7"
MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_DIR.parents[2]
PROMPTS_DIR = MODULE_DIR / "ML" / "prompts"
RUNS_DIR = REPO_ROOT / "runs"
DOMAIN_PLUGIN_PATH = MODULE_DIR / "plugins" / "real_estate.md"
CONTEXT_TARGET = 300_000
CONTEXT_MAXIMUM = 350_000
CONTEXT_RESERVE = 8_000
STAGES = ("understanding", "design", "distribution", "observations", "catalogue", "assignments")
# Editable names follow execution order; frozen snapshot/job names remain stable for resume.
PROMPT_FILES = dict(zip(STAGES, (
    "01_read_facts.md", "02_choose_domains.md", "03_sort_facts.md",
    "04_review_domains.md", "05_finalize_domains.md", "06_assign_facts.md",
)))


def stage_uses_tools(record: dict, stage: str) -> bool:
    """Input frozen run/stage; return read-tool availability for graphs and input packing."""
    return stage not in {"understanding", "distribution"} and not (
        stage == "design" and record.get("design_tool_free", False)
    )
