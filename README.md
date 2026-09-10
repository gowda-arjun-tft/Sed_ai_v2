# CDI Deep Research

Layer 2 designs plugin-driven domains and organizes supplied evidence. Existing Layers 3/4 research
real-estate risks and external influences using historical Layer 2 inputs. Python uses `compute` at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` designs plugin-driven domains, reads original source windows,
  distributes evidence and performs one paged review before versioned domain publication.
- `ML/deep_research/layer3/` runs eight direct domain researchers sequentially. Each uses the two
  evidence tools and writes one domain report before property synthesis.
- `ML/deep_research/layer4/` stores internal conditions, maps external-factor briefs directly from
  Layer 3, researches those pathways with full property context, and writes one cross-domain
  synthesis.
- `ML/deep_research/docs/` contains archived run-verification and redesign notes; the root
  architecture HTML records the previous schema-7 design.
- `tests/` contains model-free unit and fabricated end-to-end run tests.

Generated `runs/`, `.env`, caches, sources, and checkpoint databases remain local and are ignored.
New runs are grouped by the input path so repeated work stays easy to identify:

```text
runs/<parent>-<markdown-name>-<short-path-id>/
  L2_YYYYMMDD_HHMMSS_xxxx/
  L3_YYYYMMDD_HHMMSS_xxxx/
  L4_YYYYMMDD_HHMMSS_xxxx/
```

## Setup

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
```

Set only the API key in `.env`:

```text
OPENAI_API_KEY=your-key
```

The model is fixed in code to `gpt-5.6-luna`. Layer 2 freezes the selected reasoning. Layer 3 currently uses
low reasoning for domain research, synthesis, and web-search proxy calls while live behavior is
measured; this is configuration, not a separate test command. Neither layer sets an application
output-token ceiling; provider limits still apply. Layer 3 uses Deep Agents 0.7.7 with stable SQLite
researcher threads and thread-scoped `StateBackend` scratch. Each researcher receives only
`search_web` and `read_source`; the general-purpose subagent, `task`, `StoreBackend`, host shell,
`run_python`, model-writable host folders, and cross-property memory remain disabled. Web-search
context remains low.

## Layer 2 — schema 7

Supply three independent UTF-8 Markdown inputs: factsheet, domain plugin and your own requirements.
The application never invents requirements. The supplied real-estate plugin preserves the current
eight baseline responsibilities; other plugins may define different rosters without Python changes.

    .\run.ps1 -FactSheet 'C:\path\facts.md' -DomainPlugin '.\ML\deep_research\layer2\plugins\real_estate.md' -Requirements 'C:\path\requirements.md'
    .\run.ps1 -Resume '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx'

Public Python: `from ML.deep_research.layer2 import create_run, run_all`; create the run with
`create_run(factsheet, plugin, requirements, runs_root, reasoning_effort=...)`, then call `run_all(run_dir)`.
The notebook exposes these paths and reasoning. Replace the placeholders in `inputs/requirement.md`
before execution. Its `L2_DYNAMIC_RUN` variable does not feed Layer 3.

See the [Layer 2 workflow and file guide](ML/deep_research/layer2/README.md).
Operational code is in `layer2/backend/`; AI code and six generic prompts are in `layer2/ML/`.
Industry definitions live only in the selected plugin. The old predefined planner is a historical
test fixture; it is not a new Layer 2 prompt.

Read facts receives no plugin or requirements. Planning and domain review receive both; initial
and final assignment use the resulting responsibilities. No web research happens in Layer 2.

Flow: read every original source window → profile fragments and evidence inventory → initial
domain catalogue → assign preserved fact IDs → ONE correction review → accepted domain changes
and scoped ownership updates → publish recorded facts by domain. Original extraction runs once;
profiles are navigation, not
replacement evidence. Domains retain concise change reasons; review includes existing owners AND
temporary Extra. A fact can belong to multiple domains.

Inputs, prompts, hashes and policies are frozen. Nominal windows are 60K tokens with 10K
original-source overlap and 50K stride. Unicode-safe actual byte/token boundaries and any original
BOM offset are recorded; headings do not move nominal boundaries. Native abatch_as_completed
handles reading and distribution at frozen concurrency five by default, in batches of at most ten;
planning/review pages are sequential. Original windows are sought by recorded byte ranges.
Large source inputs are repacked before dispatch. The normal assembled-input target is 300K
estimated tokens; exceptional 300K–350K inputs carry a logged reason. Mandatory or indivisible
content that cannot fit fails operationally, never silently truncates. Accounting includes
instructions, messages, tools, schema and a conservative reserve; provider usage is separate.

Reader/initial-assignment graphs and designers are tool-free. Choose domains receives complete
paged understanding text, plugin, requirements and current definitions; it stays sequential
and checkpointed. Evidence is labelled text, not another escaped JSON dump. Reviewer graphs expose only native ls, glob,
grep and read_file through CompositeBackend against a rebuildable, run-owned SQLite evidence index.
StateBackend contains only small thread-local state, never a corpus copy. There is no host
filesystem mount, shell, web, delegation, cross-run memory or automatic summarizer. SQLite saves
retrieval sessions and lossless read-result pointers; original source and detailed evidence remain
stored outside model context.

All completed objects are saved using the permissive provider-native top-level JSON contract.
No semantic validator, deduplication, grading, repair prompt or content retry is added. Unknown
references and unusual response shapes remain visible; Python never invents missing assignments.
Operationally failed or unreadable jobs resume their recorded checkpoint thread. Input fingerprints
start fresh dependent jobs when recovered inputs change, preserving prior responses/publications.

Run layout:

- README.md and domain_plan.md: status, navigation, subject overview, definitions and change reasons.
- domains/<readable-name>.md: domain responsibilities and preserved facts, not routine JSON dumps.
- unresolved.md: complete unassigned/unprocessed material and response links, when present.
- run.json and run.log: frozen metadata, execution status and safe operational events.
- _internal/: input snapshots, one facts.jsonl ledger, domains.json (with membership IDs) and assignments.json.
- _internal/trace/: raw responses, source manifest, detailed evidence, review observations,
  retained publication revisions, usage.jsonl and checkpoints.sqlite3.

The normal files are rebuildable views of preserved records; prior versions and replaced Markdown
bytes are retained internally. No per-fact JSON files or per-domain JSON body copies are generated.
Unknown fields/references are exposed without guessing their meaning, grading or content repair.
Prompts ask for detailed evidence but a compact navigational profile, change-only review observations,
and explicit ownership rows with reasons only for changed/disputed/unresolved assignments. Complete
domain definitions are inlined when the fully counted review input fits; oversized rosters receive explicit
fact-page × definition-page jobs. Original extraction is not repeated after understanding.
Python assigns stable IDs from the run, source job, saved response version and entry position;
re-paging and reassignment never change the evidence body. All assigned entries appear in Markdown,
without technical IDs or sources. Review patches can explicitly add/remove owners; unchanged
ownership carries forward. Accepted new/changed responsibilities receive one scoped pass over all
earlier evidence. Unchanged scopes are not reassigned; no-proposal reviews skip finalization.
Storage consolidation itself does not reduce model tokens; prompt quality/cost needs a later live comparison.

Execution status is separate from assignment coverage: a complete run may still have unresolved
facts. “No Extra” means every RECORDED fact has an owner, not proof of complete source extraction.
CLI --check-only is observational and makes no writes. The notebook prints only start/final status,
run path and log path.

**Schema 7 is not yet integrated with Layers 3/4.** No misleading legacy missions/ handoff is
generated. Historical schema-2/3/4/5/6 Layer 2 artifacts remain untouched but cannot execute or run checks
through the new Layer 2 CLI. Layers 3/4 and their historical input workflow remain unchanged.
Offline tests prove orchestration, not model quality or extraction completeness.

## Layer 3

Enable live research only for public or invented input:

```powershell
.\run.ps1 -Research '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx' -Online -PublicInputConfirmed
```

Resume an interrupted run, or explicitly retry only failed stages from their checkpoints:

```powershell
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx'
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx' -RetryFailed
```

Layer 3 processes one direct domain researcher at a time. The researcher receives only `search_web`
and `read_source`; operational, regulatory, nearby, economic and geopolitical concerns are a
conditional prompt checklist rather than separate agents. It checks material claims against opened
sources before its final assistant Markdown is saved verbatim. The synthesis harness receives the
available domain responses directly and has no tools.

Citation checking remains model-led rather than using a Python quote parser. Python retains secure
URL handling, raw page bytes, canonical text, query caching, usage, checkpoints, and atomic writes.
It does not require auxiliary model artifacts, non-empty Markdown, hashes, or check results, and it
does not repair or retry completed content. Schema-7 runs remain untouched comparison artifacts and
require a fresh schema-8 run.

## Layer 4

Start external-influence research from an existing schema-8 Layer 3 run:

```powershell
.\run.ps1 -ExternalResearch '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx' -Online -PublicInputConfirmed
```

Resume an interrupted run, or retry only failed model stages from their checkpoints:

```powershell
.\run.ps1 -ResumeL4 '.\runs\<fact-sheet>\L4_YYYYMMDD_HHMMSS_xxxx'
.\run.ps1 -ResumeL4 '.\runs\<fact-sheet>\L4_YYYYMMDD_HHMMSS_xxxx' -RetryFailed
```

Layer 4 schema 2 sends the frozen Layer 3 domain report independently to two sequential, tool-free
calls. The internal result is a stored user-facing artifact only. The candidate result is a compact
external-factor research brief. The direct external researcher receives the unchanged Layer 3
report plus that brief and exposes only `search_web` and `read_source`; final synthesis is
tool-free. Schema-1 runs remain immutable comparison artifacts and cannot resume in schema 2. All
completed Markdown is saved verbatim; Python does not grade, repair or retry completed content.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers the Layer 2/3/4 handoffs, direct-researcher tool
isolation, sequential execution, direct response publication, egress controls, checkpoint
recovery, optional operational reporting, and the 350-line executable-source limit.
