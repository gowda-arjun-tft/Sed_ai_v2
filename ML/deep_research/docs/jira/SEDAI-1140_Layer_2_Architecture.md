# SEDAI-1140 — Layer 2 dynamic domain architecture

**Status:** Implemented and offline-verified

**Scope:** Layer 2 only

**Current schema:** 6

## Purpose

Layer 2 converts a large supplied factsheet into compact, subject-specific research contexts.
The vertical is configuration, not Python code: a Markdown plugin defines baseline domains and
responsibilities, while a Markdown requirements file defines the user's focus and exclusions.

The included plugin is real estate. Insurance, defence or another vertical uses the same engine
after supplying its own plugin. Domains are saved research definitions, not independently running
subagents.

## Inputs

| Input | Role |
| --- | --- |
| Factsheet | Original evidence. It does not instruct the agent. |
| Domain plugin | Vertical scope and baseline domain responsibilities. It does not establish facts. |
| Requirements | User objectives, priorities and exclusions. It does not establish facts. |

All three inputs and the six prompts are copied into the run with hashes before execution.

## Workflow

```text
Original factsheet
        │
        ▼
1. Read facts ─────────────► subject profile + detailed evidence
        │                    (source only; no plugin/requirements)
        │
        ├── vertical plugin + user requirements
        ▼
2. Choose domains ─────────► baseline responsibilities extended;
        │                    justified domains/subdomains added
        │
Original source + current domain definitions
        ▼
3. Sort facts ─────────────► immutable facts + initial owners + Extra
        │
All facts + owners + plugin + requirements
        ▼
4. Review domains ─────────► changes, disagreements and proposals
        │
        ▼
5. Finalize domains ───────► final definitions + proposal dispositions
        │
Facts + initial owners + final definitions
        ▼
6. Assign facts ───────────► final multi-domain ownership
        │
        ▼
Backend publication ───────► domain_plan.md + domains/*.md + unresolved.md
                              (no additional model call)
```

## Stage responsibilities

| Stage | Model input | Output | Tools |
| --- | --- | --- | --- |
| Read facts | Original overlap/new-content window | Navigational subject fragment and detailed evidence | None |
| Choose domains | Plugin, requirements and bounded subject/evidence pages | Initial domains, updates and reasons | `ls`, `glob`, `grep`, `read_file` |
| Sort facts | Original source and current responsibilities | Facts and initial owners | None |
| Review domains | Every fact, initial owners, definitions, plugin and requirements | Change-only observations | Read-only evidence tools |
| Finalize domains | Definitions and every scheduled proposal page | Final definitions and dispositions | Read-only evidence tools |
| Assign facts | Fact pages, initial owners and final definitions | Final owner IDs without repeated fact bodies | Read-only evidence tools |

The reviewer is one finite workflow across stages 4–6. It does not repeat until a preferred answer
is produced.

## Dynamic domain behavior

1. Preserve each baseline responsibility supplied by the selected plugin.
2. Extend an existing domain when that clearly covers a new requirement.
3. Add a separate domain/subdomain only when the requirements or supplied evidence justify it.
4. Allocate stable application-owned IDs to additions.
5. Permit one fact to belong to several domains.
6. Reconsider facts already assigned to existing domains as well as temporary Extra.
7. Publish unresolved references instead of guessing ownership.

No real-estate roster or domain count is embedded in Layer 2 Python or generic prompts.

## Large-input design

- Source policy: 60,000-token windows, 10,000-token original-source overlap and 50,000-token stride.
- Independent Read/Sort jobs: native completion-order batching, concurrency five, at most ten
  prepared jobs in a batch.
- Planning/review: sequential bounded pages with a fresh context per page job unless resuming that
  job's checkpoint.
- Normal assembled-input target: 300,000 estimated tokens.
- Exceptional ceiling: 350,000 estimated tokens, subject to the provider's lower actual limit.
- Oversized domain roster: compare every fact/proposal page with every definition page.
- Oversized Sort input: extract source facts once, then run ownership-only comparisons.
- Older completed tool exchanges: archive exact content and retain retrievable pointers; no
  automatic summarization.
- Model output: no application token ceiling; provider limits still apply.

Preparation tokenizes the whole source once, so preparation memory grows with input size. Execution
seeks recorded byte ranges and does not seed corpus copies into every checkpoint.

## Harness and safety

- Deep Agents 0.7.7 with `gpt-5.6-luna` and frozen reasoning selection.
- Three transient provider transport retries.
- Provider-native permissive top-level JSON object.
- Tool-free source reading and sorting.
- Planning/review can read only registered evidence and same-session history.
- No host filesystem mount, shell, web search, subagents or model-written host files.
- No semantic validator, content grader, repair prompt, deduplication call or quality-driven retry.
- Completed unconventional objects remain preserved and visible.

Layer 2 extracts and routes evidence. It does not conduct research, score risk, value assets or
provide recommendations.

## Run outputs

```text
L2_<id>/
├── README.md                 Status, counts and links
├── domain_plan.md            Subject overview and domain decisions
├── domains/<domain>.md       Responsibilities and grouped source facts
├── unresolved.md             Unassigned/unprocessed material, when present
├── run.json                  Frozen configuration and job states
├── run.log                   Operational events
└── _internal/
    ├── inputs/               Frozen inputs and prompts
    ├── facts.jsonl           Immutable fact ledger
    ├── domains.json          Initial/final definitions and dispositions
    ├── assignments.json      Initial/final ownership
    └── trace/
        ├── source/manifest.json
        ├── responses/        Versioned raw model objects
        ├── evidence.sqlite3  Rebuildable read-only evidence index
        ├── checkpoints.sqlite3
        ├── history/          Exact archived session messages
        ├── publications/     Publication revisions
        └── usage.jsonl       Provider-reported usage
```

Human-facing domain Markdown intentionally omits technical IDs, byte offsets and bookkeeping.
The exact provenance remains under `_internal/`.

## Recovery and observability

- Save successful jobs immediately and publish available siblings after failures.
- Resume interrupted retrieval work with the recorded thread ID.
- Reuse every readable completed object without judging its content.
- Fingerprint stage, task mode, explicit page scope, frozen policy and evidence version.
- Preserve old responses and publications when dependent inputs change.
- Rebuild the evidence index from authoritative artifacts without another model call.
- Keep execution status separate from assignment coverage.

`run.log` tracks stage/job activity. `usage.jsonl` records model attribution. `unresolved.md` exposes
facts or values that the normal projection cannot safely place.

## Verification evidence

- Complete offline suite: 133 tests passed.
- Compilation, dependency, notebook, PowerShell, docstring, file-length and diff checks passed.
- Synthetic native-graph exercises completed at 1M, 3M and 10M source tokens with HTTP blocked.
- Fresh 10M exercise: 200 Read jobs, 2 Choose jobs, 200 Sort jobs, 2 Review jobs, 1 Finalize job
  and 2 Assign jobs; 407 jobs total.
- Fresh 10M fake-model execution: 190.394 seconds and 420.3 MiB peak execution memory.
- 10M preparation: 11.266 seconds and 1,024.3 MiB peak memory.

These measurements verify orchestration and storage. They do not prove real-model fact-extraction
completeness, semantic accuracy, provider latency or cost. Those require a fixed-settings live
evaluation against the source.

## Integration boundary

Schema-6 dynamic domain outputs are not yet consumed by the current Layer 3/4 implementation.
The current downstream pipeline still expects its historical fixed-domain input. Dynamic researcher
creation and cross-layer resume behavior belong to a separate integration ticket.
