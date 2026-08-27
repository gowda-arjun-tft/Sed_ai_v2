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
)


MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
SKILL_PATH = MODULE_DIR / "SKILL.md"
RUN_PREFIX = "L3"
SCHEMA_VERSION = 7
HARNESS_NAME = "domain_scoped_storm_direct_output"
CHECKPOINT_PACKAGE_VERSION = "3.1.1"

MODEL_TIMEOUT_SECONDS = 600
MODEL_MAX_RETRIES = 3
REASONING_EFFORT = "low"
WEB_SEARCH_CONTEXT_SIZE = "low"
WEB_SEARCH_VERBOSITY = "low"
WEB_SEARCH_LEVELS = frozenset({"low", "medium", "high"})
FETCH_TIMEOUT_SECONDS = 30
MAX_SOURCE_BYTES = 10 * 1024 * 1024

# Frozen into new runs. Runs without this policy retain legacy source reading.
DOCUMENT_EXTRACTION_POLICY_VERSION = 1
DEFAULT_OCR_LANGUAGES = ("de", "en")
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 2_000
PDF_BATCH_PAGES = 25
FULL_DOCUMENT_RESPONSE_TOKENS = 16_000
MAX_REQUESTED_PAGES = 30
FIND_MAX_HITS = 40
WORKER_HEARTBEAT_SECONDS = 10
WORKER_STALE_SECONDS = 60

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

# Layer 2 owns the ordered domain roster. Layer 3 consumes those mission files
# one-for-one so the two layers cannot silently disagree about responsibility.
DOMAIN_NAMES = tuple(AGENT_NAMES)
