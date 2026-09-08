"""Frozen Layer 2 policies and shared model configuration."""

from pathlib import Path


MODEL_SPEC = "openai:gpt-5.6-luna"
MODEL_NAME = "gpt-5.6-luna"
REASONING_EFFORT = "max"
REASONING_EFFORTS = frozenset({"low", "medium", "high", "max"})
# Read from the model profile, not assumed: `init_chat_model(MODEL_SPEC).profile`
# reports max_input_tokens = 1_050_000. Layer 3 uses this shared profile value;
# Layer 2's separate 200K/250K assembled-input policy is defined below.
MODEL_INPUT_TOKEN_LIMIT = 1_050_000
PROVIDER_MAX_RETRIES = 3

LAYER2_SCHEMA_VERSION = 4
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
CONTEXT_TARGET = 200_000
CONTEXT_MAXIMUM = 250_000
CONTEXT_RESERVE = 8_000
STAGES = ("understanding", "design", "distribution", "observations", "catalogue", "assignments")
