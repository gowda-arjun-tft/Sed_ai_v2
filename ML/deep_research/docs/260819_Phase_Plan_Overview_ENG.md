# Layer 2 — build plan, overview

One agent, built on **deepagents**, that turns one fact sheet into fourteen mission files.

This folder holds one plan per phase. Read this file first; it says how the phases fit together
and how the agent is wired.

```
260819_Phase_Plan_Overview_ENG.md        this file
260819_Phase_0_Run_Folder_ENG.md         the run folder and the two inputs
260819_Phase_1_Split_Fact_Sheet_ENG.md   cutting the fact sheet into readable pieces
260819_Phase_2_Route_Into_Buckets_ENG.md filling fourteen buckets
260819_Phase_3_Write_Missions_ENG.md     turning each bucket into a mission
260819_Phase_4_Checks_ENG.md             what is checked before the run is called done
```

---

## The problem this design solves

The fact sheet can be very large. A bigger data room, or several buildings, produces more facts
than should be routed in one model call.

Sending the whole thing in one request has two failure modes. A very long input degrades the
reasoning, and at some size it simply will not fit. Cutting it at a fixed token count is worse:
the cut lands inside a fact and both halves become useless.

**So the fact sheet is cut only at boundaries that already exist in it, and the agent works
through the pieces one at a time, writing what it finds to disk as it goes.**

## The bucket method

Fourteen buckets, one per agent. Each is a markdown file on disk.

```
the fact sheet is cut into pieces
        │
        ▼
for each piece, in order:
    read it
    decide which buckets each fact belongs to
    append the fact to those buckets          ← a fact may go to several
    record the piece as done
        │
   … every piece processed …
        │
        ▼
for each bucket, in order:
    read that bucket alone
    write missions/<agent-name-slug>.json
```

The agent never holds the whole fact sheet. It holds **one piece plus the fourteen bucket
definitions**, which are short. The buckets grow on disk, not in the context window.

When the last piece is routed, the fourteen buckets together contain every fact that reached an
agent, and the mission-writing step reads one bucket at a time.

### Why this replaces the earlier "one request, never split" rule

The design document says the mission call must not be chunked, because splitting the input
means the model can no longer see that a fact belongs to two agents at once.

The bucket method meets that requirement a different way: **every routing step sees all fourteen
bucket definitions, and may append one fact to several buckets.** A fact belonging to condition
and to valuation is written to both, in the same step, by the same decision.

So the reason for the original rule is satisfied, and the rule itself is replaced. This is a
deliberate change and the design document should be updated to match once this is built.

### Why sections control the pieces

There is no token-based boundary. Each retained `##` section becomes one piece, so titles provide
the routing context and fact blocks remain intact. Token estimates are recorded for visibility but
do not combine small sections or split large ones.

---

## How the agent is wired

One agent. No subagents. `deepagents 0.7.7`.

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware

agent = create_deep_agent(
    model="openai:gpt-5.6-luna",               # pinned explicitly, never left to default
    system_prompt=LAYER2_SYSTEM_PROMPT,        # see phase 2
    tools=[append_to_bucket, mark_piece_done],
    backend=CompositeBackend(
        default=StateBackend(),
        routes={"/run/": FilesystemBackend(root_dir=RUN_DIR, virtual_mode=True)},
    ),
    middleware=[TodoListMiddleware()],
)
```

### Why each choice

| Choice | Reason |
|---|---|
| **one agent, no subagents** | The work is a single sequential pass. Subagent overhead is only worth paying for multi-step, output-heavy delegation. |
| **`CompositeBackend`** | The buckets and missions must survive on real disk. Everything the harness writes internally — offloaded tool results, conversation history — stays in state instead of landing next to the output. Using `FilesystemBackend` alone would dump those into the run folder. |
| **`virtual_mode=True`** | Anchors every path inside the run folder and blocks `..` and `~`. This is a path guardrail, not a sandbox — acceptable because this is a local tool, not a service. |
| **`TodoListMiddleware`** | Planning is opt-in since v0.7 and costs tokens every turn, so it is only worth adding for long multi-step work. This run is one step per piece plus one per bucket — 20 to 30 steps. It qualifies, and it makes progress readable while the run is going. |
| **two custom tools** | `append_to_bucket` and `mark_piece_done`. Reasons in phase 2. |
| **`model` pinned** | `model=None` is deprecated since 0.5.3 and removed in 1.0.0. |

### Two custom tools, and why the built-ins are not enough

The harness already gives `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`
and `task`. Reading pieces uses `read_file`; writing missions uses `write_file`. Two things need
their own tool:

**`append_to_bucket(agent_name, fact_block)`** — appending with `edit_file` means a
read-modify-write of a file that grows all run, and `edit_file` with an empty `old_string`
corrupts the whole file on every backend. A dedicated append avoids both. It also gives the model
a schema that names the fourteen agents, which teaches the routing better than prose in the prompt
would.

**`mark_piece_done(piece_id, facts_routed)`** — writes one line to the progress ledger. Keeping it
out of the model's file-writing path means the ledger cannot be corrupted by a bad edit, and the
run can resume from it after a crash.

### What is deliberately not used

- **Long-term memory** (`/memories/`, `StoreBackend`) — nothing needs to survive past one run.
- **Subagents** — see above.
- **`interrupt_on`** — nothing here is destructive enough to need an approval gate. Add one on
  `delete` if the run folder ever holds anything irreplaceable.
- **`LocalShellBackend`** — the agent has no reason to run shell commands.

---

## The phases

| Phase | What it does | Model involved? |
|---|---|---|
| **0** | Create the run folder, copy in the two inputs, record the run | no |
| **1** | Write one piece per retained `##` section and set aside non-fact sections | no |
| **2** | Route every fact into one or more of the fourteen buckets | **yes** |
| **3** | Turn each bucket into `missions/<agent-name-slug>.json` | **yes** |
| **4** | Check the run and write the record | no |

Phases 0, 1 and 4 are ordinary code. Only phases 2 and 3 call a model, which keeps the parts that
must be exact — splitting, counting, checking — away from anything that can vary between runs.

---

## What the whole thing produces

```
runs/<run_id>/
  inputs/
    fact_sheet.md                  copied in, never modified
    planner_prompt.md              the fourteen agent definitions and the rules
  pieces/
    p001_identity-title-and-land.md
    p002_…                         one file per piece, in reading order
  buckets/
    building-condition-capital-expenditure-warranty.md
    occupier-lease-income.md
    …                              fourteen files
  missions/
    building-condition-capital-expenditure-warranty.json
    …                              fourteen files — the deliverable
  progress.csv                     one row per piece, and one per bucket
  run.json                         model, versions, timings, counts
```

`missions/` is what Layer 3 consumes. Everything else exists so the run can be checked and
resumed.
