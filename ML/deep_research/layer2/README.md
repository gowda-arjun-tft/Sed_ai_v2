# Layer 2 — plugin-driven domains and evidence routing

Layer 2 organizes supplied facts; it does not perform web research or score risks.
The selected plugin supplies the industry perspective and baseline responsibilities.
User requirements supply priorities. Evidence supplies subject-specific context.
The model designs the initial domains and reviews them once after fact distribution.
There are six model stages, not six guaranteed calls: source windows and review pages
can require multiple calls, and read-only retrieval can require additional turns.

## Where to look

```text
layer2/
├── backend/   Execution, recovery, input snapshots, publication, logging and CLI
├── ML/        Deep Agent construction, model configuration and input-context policy
│   └── prompts/   Six generic stage instructions
├── plugins/   Industry definitions; currently real_estate.md
├── README.md  This human-readable guide
├── __init__.py    Public create_run and run_all functions
└── __main__.py    python -m ML.deep_research.layer2 entrypoint
```

`backend` and `ML` separate operations from AI logic. Neither is frontend code;
the Layer 2 notebook cell is the user interface.

| Backend file | Responsibility |
| --- | --- |
| `runner.py`, `jobs.py` | Stage order, bounded jobs, saved results and checkpoint recovery |
| `create_run.py`, `settings.py` | Preflight, frozen input copies, paths and configuration |
| `windows.py`, `records.py` | Original-source windows, immutable facts, ownership and publication |
| `fs.py` | Atomic file writes, normalized reads, hashes and safe identifiers |
| `usage.py`, `run_log.py` | Provider usage and one operational log per run |
| `cli.py`, `report.py` | Thin command-line adapter and read-only diagnostics |

| AI file | Responsibility |
| --- | --- |
| `ML/agent.py` | Stage-specific Deep Agent graphs and permissive provider JSON handling |
| `ML/harness.py` | Existing shared model and harness configuration |
| `ML/context.py` | Complete input estimates and lossless, retrievable read-result pointers |

## Markdown file guide

| File | Purpose |
| --- | --- |
| `plugins/real_estate.md` | Real-estate scope, baseline domains and brief responsibilities |
| User's factsheet | Original evidence, including uncertainty; never agent instructions |
| [`inputs/requirement.md`](../../../inputs/requirement.md) | Editable user objectives, priorities, exclusions, geography and time horizon |
| `ML/prompts/understanding.md` | Understand every source window and retain detailed evidence |
| `ML/prompts/design.md` | Generic instructions to generate the initial domain catalogue |
| `ML/prompts/distribution.md` | Extract original facts and assign initial domain owners |
| `ML/prompts/observations.md` | Review all recorded facts and initial ownership for needed changes |
| `ML/prompts/catalogue.md` | Settle final domains, responsibilities and change reasons |
| `ML/prompts/assignments.md` | Assign recorded facts to the final domains |
| `README.md` | Human-readable navigation and workflow; never a model prompt |

Replace the requirements template's placeholders before running. No customer objective
is supplied, and there is no placeholder-content validator. The run freezes this file as
`inputs/requirements.md` (plural), regardless of the original filename.

`design.md` tells the model **how to plan**, not which industry domains to use.
Change the selected plugin for another industry; the Python engine has no fixed roster
or real-estate fallback. Insurance and stock-market inputs are tested offline, not shipped
as production plugins in this change.

The old predefined planner is now only
[`tests/fixtures/legacy_l2_planner_prompt.md`](../../../tests/fixtures/legacy_l2_planner_prompt.md).
It constructs historical Layer 3 test inputs. Layer 3's historical parser and renderer live
in `layer3/legacy_input.py`; its fixed roster lives in `layer3/settings.py`.
New Layer 2 runs use neither. The unused live `chunk_router.md` has been removed;
historical run snapshots remain untouched.

## Workflow

```text
Factsheet + selected plugin + user requirements
                        │
                        ▼
              understanding.md
              Read source windows
                        │
                        ▼
          Subject profile + evidence inventory
                        │
                        ▼
                  design.md
           Generate initial domains
                        │
Original factsheet ─────┤
                        ▼
               distribution.md
         Extract facts and initial owners
         Unowned facts = temporary Extra
                        │
                        ▼
               observations.md
        Review ALL facts and initial owners
                        │
                        ▼
                 catalogue.md
          Settle final domains and reasons
                        │
                        ▼
                assignments.md
             Assign final fact owners
                        │
                        ▼
          Backend publisher — no LLM call
                        │
                        ▼
      Domain facts.json + facts.md + unresolved audit
```

The plugin and requirements inform **every model stage**, not just initial planning.
Source understanding and distribution are tool-free; design and the three review phases
use only `ls`, `glob`, `grep` and `read_file` on explicitly provided run-local evidence.
No host filesystem, web tools, shell, subagents or automatic summarization is enabled.
Profiles guide navigation; distribution reads the original source again.

## Run and recovery

```python
from ML.deep_research.layer2 import create_run, run_all

# Pass pathlib.Path values for all four paths; fill requirements before execution.
run = create_run(factsheet, plugin, requirements, runs_root, reasoning_effort="high")
run_all(run)
```

The notebook exposes those paths and reasoning, then displays status, run path and log
path only. Its `L2_DYNAMIC_RUN` variable intentionally does not feed Layer 3.
CLI and `run.ps1` remain available; `--check-only` is observational and non-mutating.

Schema 4 freezes the three inputs and six prompts, hashes, source windows and settings.
The 60K/10K nominal window policy, native batch concurrency, 200K/250K estimated input
policy, SQLite retrieval threads, usage records and versioned publication remain unchanged.
Completed responses are saved without content grading, repair or content-driven retry.
Operational failures preserve available sibling results; recovery reuses saved responses
and the recorded thread when inputs are unchanged.

Find outputs through `publication.json`, which points to
`publications/<id>/domains/<domain-id>/facts.json` and `facts.md` plus the unresolved audit.
Original inputs, detailed evidence and immutable fact records remain separately stored.
Unresolved coverage concerns **recorded facts**, not proof that every source fact was extracted.

**Dynamic schema-4 Layer 2 is not yet integrated with Layers 3/4.** Their historical
inputs and completed runs are unchanged; schema-2/3 Layer 2 execution remains unsupported.
