"""Layer 3 configuration.

Deliberately short. This module holds identity and scheduling only.

There are no query budgets, result caps, snippet caps, byte caps, timeouts,
attempt counts, call ceilings or character limits here, and none anywhere else in
the layer. The researcher decides how much to search, how long to work, when it
has enough and what to write. Nothing in Python judges that.

`RECURSION_LIMIT` below is the one number that looks like a limit and is not:
LangGraph defaults to 25 steps, so this exists to lift that ceiling out of the
way rather than to impose one.
"""

from __future__ import annotations

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
RUN_PREFIX = "L3"

# How many sessions run at once. Scheduling, not a constraint on any session.
WORKERS = 6

# Lifts LangGraph's 25-step default out of the way. Not a ceiling we want.
RECURSION_LIMIT = 1_000_000

CHECKPOINT_PACKAGE_VERSION = "3.1.1"

LENSES = {
    "practitioner": "How the work is done in practice, and what it costs.",
    "academic": "What research and published standards establish.",
    "economist": "What it is worth, and who ultimately pays.",
    "historian": "How comparable cases turned out, and what precedent exists.",
    "skeptic": "Test every connection and explain why the answer may be wrong.",
}

TERMINAL_STATUSES = {
    "answered",
    "cannot be answered",
    "failed",
    "half done",
    "skipped",
}
