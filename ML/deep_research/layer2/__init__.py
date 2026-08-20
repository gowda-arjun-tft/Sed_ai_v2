"""CDI Layer 2: turn one property fact sheet into fourteen research missions.

Three steps, in order:

| Module | Step | Model? |
|---|---|---|
| `create_run` | build the run folder and copy the two inputs | no |
| `agent` | one harness agent reads the sheet and writes the missions | yes |
| `report` | eight bookkeeping checks, then the two record files | no |

`cli` runs them in that order. `settings` holds every fixed value, `planner`
loads and verifies the fourteen-subject roster, `python_tool` is the agent's
calculator, and `fs` holds the file and hash helpers -- which Layer 3 imports
from here too, so `fs`, `planner` and `settings` are shared rather than private.

`ML/deep_research/docs/260820_Layer2_Code_Walkthrough_ENG.md` walks the flow
end to end.
"""

from .cli import main

__all__ = ["main"]
