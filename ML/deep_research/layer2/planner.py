"""Loading and verifying the roster.

`prompts/planner_prompt.md` is two things at once: prose the agent reads as part
of its system prompt, and a machine-readable list of the eight agent
definitions embedded in it between two HTML comments.

```markdown
<!-- AGENTS_JSON_START -->
[{"name": "...", "mandate": "...", "handoffs": ["..."]}, ...]
<!-- AGENTS_JSON_END -->
```

One file, so the definitions the agent reads and the definitions the code checks
can never drift apart.

Layer 3 imports `load_planner` too, and runs it against the copy inside a Layer 2
run folder before it will accept that run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .settings import AGENT_NAMES
from .fs import read_text

# The three keys every agent definition must carry, no more and no fewer.
# `mandate` assigns accountability; `handoffs` preserve facts needed at the
# interfaces between the eight subjects.
REQUIRED_KEYS = {"name", "mandate", "handoffs"}


def load_planner(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Read the planner prompt and return `(full text, agent definitions)`.

    The full text goes into the agent's system prompt verbatim. The parsed
    definitions are what the code checks against.

    Three things are enforced, all of them structural facts about a
    human-authored file rather than judgements about model output:

    1. the `AGENTS_JSON` block exists and parses as JSON,
    2. it holds exactly the eight `AGENT_NAMES`, in that order,
    3. every definition carries exactly `REQUIRED_KEYS`.

    Raises `ValueError` on any of the three. Called at three points in a run's
    life: when the run folder is created (so a broken roster fails before any
    model call), when the report is written, and again by Layer 3 against the
    copy in the run folder.
    """
    text = read_text(path)
    match = re.search(
        r"<!-- AGENTS_JSON_START -->\s*(.*?)\s*<!-- AGENTS_JSON_END -->",
        text,
        re.S,
    )
    if not match:
        raise ValueError("planner_prompt.md has no AGENTS_JSON block")
    agents = json.loads(match.group(1))
    names = [agent.get("name") for agent in agents]
    if len(agents) != len(AGENT_NAMES) or names != AGENT_NAMES:
        raise ValueError(
            "planner_prompt.md must contain the eight frozen agent names in order"
        )
    if any(set(agent) != REQUIRED_KEYS for agent in agents):
        raise ValueError(
            f"every planner agent must contain exactly {sorted(REQUIRED_KEYS)}"
        )
    if any(
        not isinstance(agent["mandate"], str)
        or not agent["mandate"].strip()
        or not isinstance(agent["handoffs"], list)
        or not agent["handoffs"]
        or any(not isinstance(item, str) or not item.strip() for item in agent["handoffs"])
        for agent in agents
    ):
        raise ValueError("every planner mandate and handoff must be non-empty text")
    return text, agents
