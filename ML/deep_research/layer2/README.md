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
| `windows.py`, `records.py` | Original-source windows, immutable fact ledger and ownership references |
| `publication.py` | Readable domain views, complete audit material and recoverable publication history |
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
| `ML/prompts/01_read_facts.md` | Read factsheet windows; produce subject understanding and detailed evidence |
| `ML/prompts/02_choose_domains.md` | Use that understanding, plugin and requirements to choose initial domains and duties |
| `ML/prompts/03_sort_facts.md` | Read the original factsheet again; place extracted facts into relevant domains or temporary Extra |
| `ML/prompts/04_review_domains.md` | Inspect all extracted facts and initial placements; suggest only needed domain/duty/ownership changes |
| `ML/prompts/05_finalize_domains.md` | Combine the review suggestions into the final domain list and responsibilities |
| `ML/prompts/06_assign_facts.md` | Give every recorded fact its final domain owners, including newly added domains |
| `README.md` | Human-readable navigation and workflow; never a model prompt |

Replace the requirements template's placeholders before running. No customer objective
is supplied, and there is no placeholder-content validator. The run freezes this file as
`_internal/inputs/requirements.md` (plural), regardless of the original filename.

`02_choose_domains.md` tells the model **how to plan**, not which industry domains to use.
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
              01_read_facts.md
              Read source windows
                        │
                        ▼
          Subject profile + evidence inventory
                        │
                        ▼
              02_choose_domains.md
           Generate initial domains
                        │
Original factsheet ─────┤
                        ▼
               03_sort_facts.md
         Extract facts and initial owners
         Unowned facts = temporary Extra
                        │
                        ▼
              04_review_domains.md
        Review ALL facts and initial owners
                        │
                        ▼
             05_finalize_domains.md
          Settle final domains and reasons
                        │
                        ▼
               06_assign_facts.md
             Assign final fact owners
                        │
                        ▼
          Backend publisher — no LLM call
                        │
                        ▼
      domains/<domain-name>.md + unresolved.md when needed
```

The plugin and requirements inform **every model stage**, not just initial planning.
Steps 04–06 are the three parts of the existing reviewer, not an extra review loop:
suggest changes → settle the domain list → assign facts to that final list. Step 03 uses
the initial list; step 06 can move facts to domains that the review added. The backend
then writes the Markdown files without another model call. A catalogue simply means
the domain list plus each domain's responsibilities.

Edit the numbered prompt files above. Internal stage IDs and frozen snapshot filenames
keep their previous names (`understanding`, `design`, `distribution`, `observations`,
`catalogue`, `assignments`) so existing runs resume unchanged. This filename cleanup
does not change prompt text, model calls, settings, output paths or historical artifacts.

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

Schema 5 freezes the three inputs and six prompts, hashes, source windows and settings.
The 60K/10K nominal window policy, native batch concurrency, 200K/250K estimated input
policy, SQLite retrieval threads, usage records and versioned publication remain unchanged.
Completed responses are saved without content grading, repair or content-driven retry.
Operational failures preserve available sibling results; recovery reuses saved responses
and the recorded thread when inputs are unchanged.

## Read the results

```text
L2_<id>/
├── README.md              Execution status, recorded-fact counts and output links
├── domain_plan.md         Subject overview, initial/final domains and review reasons
├── domains/<name>.md      Research responsibilities and section-grouped asset facts
├── unresolved.md          Full unassigned/unprocessed material, only when present
├── run.json               Machine-readable status and frozen configuration
├── run.log                Operational events, not source text or model responses
└── _internal/
    ├── inputs/            Original input bytes and all six prompt snapshots
    ├── facts.jsonl        One canonical ledger, including retained earlier fact versions
    ├── domains.json       Initial and final domain definitions
    ├── assignments.json   Initial/final decisions and active fact IDs
    └── trace/             Raw responses, source manifest, detailed evidence,
                          review pages, publication history, usage.jsonl and checkpoints.sqlite3
```

Start with README.md, then the domain Markdown files. Research Markdown contains the name,
responsibilities and facts grouped by supplied section labels in first-appearance order;
missing labels use `Other supplied facts`. It omits catalogue IDs, source bookkeeping,
window offsets, record links and ownership explanations. Full provenance and source locators
remain in the unchanged internal records, not another duplicate JSON copy. Fact wording,
supported meaning, applicability, dates, conflicting quantities and additional values remain
visible; Python does not paraphrase, deduplicate or strip keywords from prose.
Domain filenames are sanitized and disambiguated without changing the domain definitions.

Raw model objects are saved before interpretation. Recognized facts/owners are published;
unexpected fields and unusable references are shown in unresolved.md with their complete values
and raw-response links. Python does not guess alternate meanings or request a rewritten answer.
Serialization failures, conflicting immutable records and oversized inputs remain operational
errors. Coverage never gates completed content or changes execution status.

The fact ledger is atomically replaced while retaining immutable earlier records. Ownership
and domain definitions are separate; no per-fact or per-domain JSON copies are generated.
Fingerprint-based responses and committed publication revisions remain under trace/. Replaced
visible Markdown bytes are also archived before refreshing views. Missing or interrupted views
are rebuilt on resume from completed jobs, without content-repair calls. Checkpoints are retained.
The usage helper still accepts the directory containing usage.jsonl; for schema 5 that directory
is `_internal/trace/`. Public create_run/run_all interfaces remain unchanged.

## Less repeated model text

Understanding keeps the profile navigational and the evidence inventory detailed. Observations
review every fact but report only changes, disagreements or unresolved issues. Final assignment
output contains an explicit entry for each supplied fact, with a reason only for changed,
disputed or unresolved ownership. Initial owners are supplied for comparison, not as authority.
Complete domain definitions are inlined on review pages only when the fully accounted input
fits the normal context target; otherwise all definition pages remain retrievable. No fact or
definition is truncated, and the original-source distribution pass is unchanged.

Distribution requests concise facts and useful topic labels, with `means` empty when there is
no additional supported interpretation. Material document names/dates belong in the fact,
not exclusively in its source bookkeeping. Domain design and final catalogue request concise
duties and boundaries, keeping rationale/evidence references separate from responsibilities.
No word limit, fixed topic roster or additional model call is introduced. New runs snapshot
these prompts; existing snapshots are unchanged. The cleaner renderer applies to new
publications, including a later explicitly requested resume/republication that archives the
previous visible bytes. Existing run files are not automatically refreshed by a code update.

Fewer files do not themselves save model tokens. Prompt/input savings and quality need a later
authorized live comparison at unchanged model/settings; offline tests prove orchestration only.
Unresolved coverage concerns **recorded facts**, not proof that every source fact was extracted.

**Dynamic schema-5 Layer 2 is not yet integrated with Layers 3/4.** Historical runs and
completed reports remain unchanged. Schema-2/3/4 execution and checks are rejected without migration.
