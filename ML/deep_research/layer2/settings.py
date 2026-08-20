"""Every fixed value Layer 2 uses.

Nothing here is computed at run time and nothing here is configurable by flag.
Both are deliberate: the roster is a contract Layer 3 verifies, and the model
choice is part of the run record rather than a knob.

Layer 3 imports `MODEL_SPEC`, `MODEL_NAME`, `REASONING_EFFORT`,
`DEEPAGENTS_VERSION` and `REPO_ROOT` from here, so this module is shared and not
private to Layer 2.
"""

from pathlib import Path


# How LangChain's `init_chat_model` is asked for the model: "provider:name".
MODEL_SPEC = "openai:gpt-5.6-luna"

# The bare name, recorded in run.json so a run can be read back years later.
MODEL_NAME = "gpt-5.6-luna"

# Passed to the provider profile in `agent.configure_provider`.
REASONING_EFFORT = "high"

# Recorded in run.json. The harness's behaviour changes between versions, so the
# version that produced a run is part of its provenance.
DEEPAGENTS_VERSION = "0.7.7"

MODULE_DIR = Path(__file__).resolve().parent

# .../Sed_ai_v2 — MODULE_DIR is ML/deep_research/layer2, so up three.
REPO_ROOT = MODULE_DIR.parents[2]

PROMPTS_DIR = MODULE_DIR / "prompts"

# The one authoritative copy of the roster. `test_structure.py` asserts no second
# copy exists at the repository root.
PLANNER_PATH = PROMPTS_DIR / "planner_prompt.md"

# Where run folders are created: <repo>/runs/L2_YYYYMMDD_xxxx
RUNS_DIR = REPO_ROOT / "runs"

# The fourteen research subjects, frozen in this order.
#
# Frozen because the whole pipeline is keyed on them: `slug(name)` is the mission
# filename, `planner.load_planner` refuses a planner prompt whose names or order
# differ, and Layer 3 looks up each mission by the same slug. Adding a fifteenth
# subject means changing this list, planner_prompt.md and Layer 3 together.
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

# There is deliberately no SKIPPED_SECTIONS list. Deciding that a section titled
# "audit appendix" or "reader note" holds no property facts was a hardcoded set
# of English titles applied before the model ever saw the document — it made the
# code monolingual and pre-judged the input. The agent reads the whole sheet.
