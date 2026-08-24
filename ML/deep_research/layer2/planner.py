"""Load the human-authored domain roster embedded in the planner prompt.

`prompts/planner_prompt.md` is two things at once: prose the agent reads as part
of its system prompt, and a machine-readable list of the eight agent
definitions embedded in it between two HTML comments.

```markdown
<!-- AGENTS_JSON_START -->
[{"name": "...", "mandate": "...", "handoffs": ["..."]}, ...]
<!-- AGENTS_JSON_END -->
```

One file keeps the definitions the agent reads and the definitions used for
mission filenames together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .fs import read_text


def load_planner(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Read the planner prompt and return `(full text, agent definitions)`.

    Only the JSON envelope is parsed. Domain quality and completeness remain a
    prompt concern rather than an execution gate.
    """
    text = read_text(path)
    match = re.search(
        r"<!-- AGENTS_JSON_START -->\s*(.*?)\s*<!-- AGENTS_JSON_END -->",
        text,
        re.S,
    )
    if not match:
        raise ValueError("planner_prompt.md has no AGENTS_JSON block")
    return text, json.loads(match.group(1))
