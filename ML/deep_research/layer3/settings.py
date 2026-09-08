"""Frozen Layer 3 identities and operational safety settings."""

from pathlib import Path

from ML.deep_research.layer2.backend.settings import (
    DEEPAGENTS_VERSION,
    MODEL_NAME,
    MODEL_INPUT_TOKEN_LIMIT,
    MODEL_SPEC,
    REPO_ROOT,
    RUNS_DIR,
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
SKILL_PATH = MODULE_DIR / "SKILL.md"
RUN_PREFIX = "L3"
SCHEMA_VERSION = 8
HARNESS_NAME = "domain_plain_research_direct_output"
CHECKPOINT_PACKAGE_VERSION = "3.1.1"

MODEL_TIMEOUT_SECONDS = 600
MODEL_MAX_RETRIES = 3
REASONING_EFFORT = "low"
WEB_SEARCH_CONTEXT_SIZE = "low"
WEB_SEARCH_VERBOSITY = "low"
WEB_SEARCH_LEVELS = frozenset({"low", "medium", "high"})
FETCH_TIMEOUT_SECONDS = 30
MAX_SOURCE_BYTES = 10 * 1024 * 1024

# Defaults copied into each new run. Runtime middleware reads the run-local
# policy instead, so changing these values cannot change a resumable run.
CONTEXT_POLICY_VERSION = 1
CONTEXT_SOFT_TARGET_TOKENS = 200_000
EVICTION_TRIGGER_TOKENS = 150_000
EVICTION_KEEP_TOOL_RESULTS = 6
EVICTION_EXCLUDE_TOOLS = ("search_web",)
EMERGENCY_EVICTION_TRIGGER_TOKENS = 170_000
EMERGENCY_EVICTION_KEEP_TOOL_RESULTS = 0
SUMMARY_TRIGGER_TOKENS = 170_000
SUMMARY_KEEP_TOKENS = 70_000
SUMMARY_TRIM_TOKENS = None

# Historical Layer 2/3 roster; schema-4 Layer 2 domains come from its plugin.
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
DOMAIN_NAMES = tuple(AGENT_NAMES)
