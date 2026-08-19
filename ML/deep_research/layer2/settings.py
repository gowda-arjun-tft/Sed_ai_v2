from pathlib import Path


MODEL_SPEC = "openai:gpt-5.6-luna"
MODEL_NAME = "gpt-5.6-luna"
REASONING_EFFORT = "high"
DEEPAGENTS_VERSION = "0.7.7"
MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[2]
PLANNER_PATH = MODULE_DIR / "prompts" / "planner_prompt.md"
RUNS_DIR = REPO_ROOT / "runs"

AGENT_NAMES = [
    "Building condition, capital expenditure & warranty",
    "Occupier, lease & income",
    "Legal, title & encumbrance",
    "Utilities, connection & building technology",
    "Ground, environment & insurability",
    "Counterparty mandate & award legitimacy",
    "Energy, carbon & transition",
    "Market, valuation & exit",
    "Planning, regulation & tax",
    "Location, access & surroundings",
    "Regional economy & demographics",
    "Macro, financing & debt",
    "Fund vehicle eligibility",
    "Geopolitical, trade & supply chain",
]

SKIPPED_SECTIONS = {
    "not covered": "Lists gaps rather than facts about the property.",
    "audit appendix": "Run bookkeeping rather than facts about the property.",
    "how to read this document": "Instructions to the reader.",
    "coverage at a glance": "Coverage counts rather than property facts.",
    "reader note": "Instructions to the reader.",
    "executive readout": "Summary of facts routed from their full sections instead.",
}
