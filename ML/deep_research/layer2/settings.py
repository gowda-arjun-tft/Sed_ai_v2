"""Fixed CDI model, roster, and Layer 2 chunking configuration."""

from pathlib import Path


MODEL_SPEC = "openai:gpt-5.6-luna"
MODEL_NAME = "gpt-5.6-luna"
REASONING_EFFORT = "max"
MODEL_INPUT_TOKEN_LIMIT = 200_000
PROVIDER_MAX_RETRIES = 2

# Layer 3 still uses these to compact its long research conversations. Layer 2
# has one fresh invocation per chunk and therefore has no summarizer.
SUMMARIZATION_TRIGGER_TOKENS = 180_000
SUMMARIZATION_KEEP_TOKENS = 100_000

LAYER2_SCHEMA_VERSION = 2
CHUNK_SIZE_TOKENS = 50_000
CHUNK_OVERLAP_TOKENS = 5_000
CHUNK_ENCODING = "o200k_base"
MAX_CHUNK_CONCURRENCY = 5
CHUNK_SEPARATORS = ("\n## ", "\n### ", "\n\n", "\n", " ", "")

DEEPAGENTS_VERSION = "0.7.7"
MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[2]
PROMPTS_DIR = MODULE_DIR / "prompts"
PLANNER_PATH = PROMPTS_DIR / "planner_prompt.md"
RUNS_DIR = REPO_ROOT / "runs"

AGENT_NAMES = [
    "Asset Integrity, Systems & Operational Resilience",
    "Occupier, Lease, Income & Counterparty Economics",
    "Rights, Public Law & Ownership Governance",
    "Ground, Physical Climate & Insurability",
    "Energy, Carbon & Transition",
    "Location, Demand, Market, Valuation & Exit",
    "Finance, Debt & Macro Transmission",
    "External Dependencies, Geopolitics, Trade & Supply Chains",
]
