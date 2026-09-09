# Layer 2 — scalable evidence processing (schema 6)

Layer 2 reads supplied UTF-8 text, designs industry-appropriate domains and places
recorded facts into them. It does not search the web, score risks or draw research
conclusions. Six stages remain; a stage may need multiple bounded jobs and retrieval turns.

## Start here

- Edit industry scope and baseline duties in the selected plugin, such as `plugins/real_estate.md`.
- Edit objectives/priorities/exclusions in [inputs/requirement.md](../../../inputs/requirement.md).
  Replace its placeholders yourself; the application does not invent requirements.
- Supply the factsheet as original evidence, never agent instructions.
- Use the notebook's Layer 2 cell. It shows running/final status, run path and log path.
  `L2_DYNAMIC_RUN` intentionally does not feed the unchanged Layer 3 cell.

## Six steps

```text
Original factsheet only
        │
        ▼
01 Read facts ──► subject fragments + detailed evidence
        │
        ├── selected plugin + user requirements
        ▼
02 Choose domains ──► initial definitions and reasons
        │
Original factsheet + current responsibilities
        ▼
03 Sort facts ──► immutable facts + initial owners / temporary Extra
        │
        ├── plugin + requirements + every recorded fact
        ▼
04 Review domains ──► changes, disagreements and proposals
        ▼
05 Finalize domains ──► final definitions + proposal dispositions
        ▼
06 Assign facts ──► final owners for every recorded fact
        ▼
Backend publisher (no model call)
        ▼
Compact domains/*.md + unresolved.md when needed
```

Read facts keeps its separate compact subject profile and requests coherent evidence groups
about the same subject and topic. Each entry contains `fact`, `relationships`, `contradictions`
and `source`. Historical/proposed/unconfirmed qualifications belong within the fact, not a
separate applicability field. Relationships add supported connections; contradictions describe
unresolved differences. Either list may be empty. Source lists contain only supplied provenance
IDs (or `[]`), without filenames or window metadata. Internal source-window tracking is unchanged.
Grouping reduces repeated structure, not distinct details; no entry count or word limit is imposed.
The four-field contract is prompt guidance, not a Python validator. New runs snapshot it; existing
runs retain their frozen prompt. Detail retention
and token savings require a separately authorized model comparison, not just offline tests.

| Prompt | Inputs and task |
| --- | --- |
| `ML/prompts/01_read_facts.md` | Original overlap/new-content window only. Preserve a compact subject profile and detailed evidence. No plugin, requirements or tools. |
| `ML/prompts/02_choose_domains.md` | Complete scheduled understanding records, plugin, requirements and current definitions. Retain baselines; justify additions or responsibility updates. Tool-free in new runs. |
| `ML/prompts/03_sort_facts.md` | Original source plus initial responsibilities. Extract original facts, not a previous model summary; assign relevant owners. Tool-free. |
| `ML/prompts/04_review_domains.md` | Every recorded fact and its initial ownership, definitions, plugin and requirements. Report changes or disagreements only. |
| `ML/prompts/05_finalize_domains.md` | Scheduled proposal groups, existing definitions, plugin and requirements. Apply explicit changes and state dispositions. |
| `ML/prompts/06_assign_facts.md` | Fact pages, initial owners and final responsibilities. Return owner IDs without repeating fact bodies. |

Steps 04–06 are one finite reviewer stage, not a designer/reviewer approval loop.
The numbered prompts keep stable internal stage IDs: understanding, design, distribution,
observations, catalogue, assignments. Frozen copies use those IDs as filenames.
All industry responsibilities come from the selected plugin, never a Python roster.

## Large inputs and large domain lists

Preparation tokenizes once using installed `o200k_base`. Nominal windows are 60K tokens,
10K original-source overlap and 50K stride. Actual byte boundaries are Unicode-safe;
new-content slices reconstruct the original text. Processing stops at source end.
Only manifest boundaries remain in memory after preparation. The tokenizer still allocates
for the whole input during preparation: RAM is **not** input-size-independent.

Execution seeks recorded ranges instead of reloading the whole factsheet. Native
`abatch_as_completed` uses frozen concurrency five and batches of at most twice concurrency.
Completions save immediately; records assemble in source order. Planning and review are sequential,
with fresh page contexts unless resuming that exact checkpoint.

Small subject inputs use one domain-design job. Larger inputs schedule every subject group
in order. Models return additions/updates, not the entire roster each time. The application
allocates stable IDs and preserves unchanged definitions. Finalization uses the same bounded
update pattern and schedules every proposal page.

New runs freeze `design_tool_free: true`: Choose domains uses only supplied JSON evidence,
plugin, requirements and current definitions. Every understanding page is scheduled; profiles
never replace detailed evidence. The designer stays sequential and checkpointed, but has no
evidence backend or tools. Historical schema-6 runs without this setting retain their original
designer behavior and prompt snapshots. No existing run is restarted or converted automatically.

Large fact collections are paged. Oversized **responsibility definitions** are different:
each fact/proposal group is explicitly compared with every definition page. Planning comparisons
are reconciled in bounded jobs. Tool-free design reconciliation explicitly includes current
corresponding definitions and domains added by earlier reconciliations, paging large values
without truncation. Unknown comparison references remain in the audit, not a repair loop.
When source plus definitions will not fit, sorting extracts
the original source once, then schedules ownership-only comparisons. Facts can have several
owners, including domains added during review. Failed or missing ownership comparisons remain
visible even if another page supplied an owner.

There is no repeat-until-good loop, automatic summarizer, semantic deduplication or repair call.
Completed large values remain saved and become parent-linked text fragments only when another
job consumes them. Fragment locations do not turn a source-window offset into an exact fact citation.

## Evidence, memory and input limits

The normal assembled-input target is **300K estimated tokens**, with logged exceptional
tolerance through **350K**. Every dispatch, including tool follow-ups, counts instructions,
messages, evidence, tool definitions, response metadata and conservative framing.
The effective allowance is also bounded by the model's supported capacity. These estimates
are not provider billing counts. There is **no application output-token limit**; provider limits apply.

Page material first. Archive complete older assistant/tool exchanges before replacing them
with retrievable references. Keep current instructions, pending tool calls and newest evidence.
No generated summary replaces original evidence. Mandatory/indivisible input that cannot fit
fails operationally, preserving completed siblings; completed content is never rejected for quality.

Review (and historical tool-enabled design) exposes only native `ls`, `glob`, `grep`, `read_file` through CompositeBackend.
An indexed read-only backend serves registered `/evidence/` pages from this run and
`/history/` pages from this session. No arbitrary host-path resolution, shell, web, model writes,
delegation, embeddings, vector database or cross-run memory. StateBackend contains only small
thread state; corpus bodies are not seeded into each checkpoint.
Tool-free design still uses SQLite checkpoints; removing its tools is not a general SQLite-locking fix.

During stage execution the runner retains one idle evidence connection, without an open transaction,
to avoid last-connection WAL cleanup overlapping new tool reads. Each retrieval still opens its own
query-only connection with a five-second busy timeout. Native read operations retry only SQLite
BUSY/PROTOCOL primary codes: three attempts total, with 0.25s/0.5s backoff and fresh connections.
SQLite's internal protocol waits are separate from the busy timeout. Partial attempt results are
discarded before returning a tool response. Initialization, history indexing, writes and checkpoints
are outside this retry boundary. Exhaustion remains an operational failure; no LLM response is retried.
This is tested read recovery, not a guarantee against every SQLite failure.

The existing run.log records retry/recovery/failure, database/tool, stage/job/thread, timing and SQLite
codes. Final failures include traceback file/function/line frames, not source lines, local variables,
SQL parameters, exception payloads or model content. Database attempts do not increment model usage
or job attempts. No separate monitoring service is added; check-only still writes nothing.

SQLite stores immutable page versions and a searchable projection of source, records, identifiers,
model-supplied entities/topics/relationships/aliases. `grep` is literal substring search with an
exact scan, not ranked top matches; narrow truncated results through directory shards and read
all relevant pages. Source pages link to adjacent pages/windows. An FTS accelerator is unnecessary
for correctness and has not been added. Original snapshots, raw responses and ledger remain authoritative.

## Files and code

```text
layer2/
├── backend/   Operations, persistence and publication
├── ML/        Deep Agent construction, context policy and prompts
├── plugins/   User-selectable industry definitions
├── README.md  Human workflow guide (not a prompt)
├── __init__.py    Public create_run / run_all
└── __main__.py    Thin command-line entrypoint
```

| Code | Purpose |
| --- | --- |
| `backend/runner.py`, `stages.py`, `jobs.py` | Six-stage order, bounded queues, immediate saves and recovery |
| `backend/create_run.py`, `settings.py` | Preflight, frozen input/prompt snapshots and policies |
| `backend/windows.py`, `packing.py` | Unicode-safe source ranges and input pages |
| `backend/evidence.py` | Rebuildable SQLite evidence/projection index and exact session archives |
| `backend/projections.py` | Immutable ledger and explicit domain/ownership operations; observational audits |
| `backend/publication.py`, `publish.py` | Readable rendering and streamed, versioned publication |
| `backend/fs.py`, `usage.py`, `run_log.py` | Atomic I/O, provider usage and operational logging |
| `backend/cli.py`, `report.py` | Thin CLI and read-only checks |
| `ML/agent.py`, `harness.py` | Stage capabilities and unchanged shared model construction |
| `ML/context.py`, `evidence_backend.py` | Final input guard, history pointers and native read-only evidence access |

## Read the results

```text
L2_<id>/
├── README.md              Status, counts, output links
├── domain_plan.md         Subject overview, initial/final domains, reasons and dispositions
├── domains/<name>.md      Responsibilities and section-grouped facts
├── unresolved.md          Complete unassigned/unprocessed material, when present
├── run.json
├── run.log
└── _internal/
    ├── inputs/            Original bytes and six frozen prompt copies
    ├── facts.jsonl        Immutable fact ledger, retaining earlier generations
    ├── domains.json       Initial/final definitions and proposal dispositions
    ├── assignments.json   Initial/final ownership and active fact IDs
    └── trace/
        ├── source/manifest.json
        ├── evidence.sqlite3    Rebuildable index, shared across this run's retrieval jobs
        ├── responses/          Raw response.json files and job-version history
        ├── history/            Exact archived session messages
        ├── publications/       Complete publication revisions
        ├── presentation_history/
        ├── checkpoints.sqlite3
        └── usage.jsonl
```

Research Markdown contains the name, responsibilities and grouped facts, not technical IDs,
byte offsets, source bookkeeping or decision inventories. Facts retain substantive dates,
quantities, contradictions and qualifications within the fact. Sort facts no longer requests separate
means or applicability fields. The publisher omits those exact top-level fields (and source bookkeeping)
from research Markdown, but preserves full bodies in raw responses and the ledger. Other nested or
unconventional values remain visible; words in prose are not stripped. Python does not paraphrase or
infer missing ownership. Old qualifications stored only in a hidden field remain available internally,
not automatically moved into fact text. New prompts apply only through new-run snapshots; existing
run views are not refreshed until publication is explicitly invoked.

Publications stream one domain at a time through atomic temporary files. Old visible bytes
are archived before replacement; raw responses and checkpoints are retained. The SQLite index
can be rebuilt from authoritative records without another model call. Damaged index bytes are
retained for diagnosis.

## Execution and compatibility

```python
from ML.deep_research.layer2 import create_run, run_all
run = create_run(factsheet, plugin, requirements, runs_root, reasoning_effort="high")
run_all(run)
```

Pass pathlib.Path values; CLI/PowerShell flags and public signatures are unchanged.
Run snapshots include all three inputs even though step 01 receives source only.
Operational failures resume by explicit saved thread ID. Job identity includes stage/mode/page
scope; fingerprints include frozen policy, prompt, explicit inputs and the accessible evidence
manifest version, not an entire corpus copy. Changed upstream evidence preserves old results and
creates dependent versions. Completed objects, even empty/unconventional ones, are reused.

`--check-only` is observational: no model calls, file changes or log appends.
Schema-2/3/4/5 files remain readable as history but execution/checks are rejected without migration.
Schema 6 is **not yet integrated with Layers 3/4**. Their code, cells and historical inputs are unchanged.

## Verification boundary

Offline fixtures exercise native tool surfaces/checkpoint recovery, exact source preservation,
bounded jobs, exhaustive scheduled comparisons, input accounting and streamed publication.
`python -m tests.layer2_scale prepare <fixture-dir> --tokens 10000000` followed by the corresponding
`execute` command runs synthetic native-graph outputs with HTTP blocked. Use separate processes
for preparation/execution RAM, I/O and timing measurements. These are operational checks:
they do not prove extraction completeness, semantic retrieval quality or future provider latency.
A fixed-settings model comparison requires separate authorization.

See [schema-6 verification and scale measurements](docs/schema6_verification.md) for the
offline results and their limits.
