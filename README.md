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

The model is fixed in code to `gpt-5.6-luna`. Layer 2 uses maximum reasoning. Layer 3 currently uses
low reasoning for domain research, synthesis, and web-search proxy calls while live behavior is
measured; this is configuration, not a separate test command. Neither layer sets an application
output-token ceiling; provider limits still apply. Layer 3 uses Deep Agents 0.7.7 with stable SQLite
researcher threads and thread-scoped `StateBackend` scratch. Each researcher receives only
`search_web` and `read_source`; the general-purpose subagent, `task`, `StoreBackend`, host shell,
`run_python`, model-writable host folders, and cross-property memory remain disabled. Web-search
context remains low.

## Layer 2 — schema 4

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

Flow: read every original source window → profile fragments and evidence inventory → initial
domain catalogue → distribute ORIGINAL facts → ONE reviewer stage (observation pages, final
catalogue, assignment pages) → publish recorded facts by domain. Profiles are navigation, not
replacement evidence. Domains retain concise change reasons; review includes existing owners AND
temporary Extra. A fact can belong to multiple domains.

Inputs, prompts, hashes and policies are frozen. Nominal windows are 60K tokens with 10K
original-source overlap and 50K stride. Unicode-safe actual byte/token boundaries and any original
BOM offset are recorded; headings do not move nominal boundaries. Native abatch_as_completed
handles reading and distribution at frozen concurrency five by default; review pages are sequential.
Large source inputs are repacked before dispatch. The normal assembled-input target is 200K
estimated tokens; exceptional 200–250K inputs carry a logged reason. Mandatory or indivisible
content that cannot fit fails operationally, never silently truncates. Accounting includes
instructions, messages, tools, schema and a conservative reserve; provider usage is separate.

Reader/distributor graphs are tool-free. Designer/reviewer graphs expose only native ls, glob,
grep and read_file against explicitly seeded run-owned StateBackend files. There is no host
filesystem mount, shell, web, delegation, cross-run memory or automatic summarizer. SQLite saves
retrieval sessions and lossless read-result pointers; original source and detailed evidence remain
stored outside model context.

All completed objects are saved using the permissive provider-native top-level JSON contract.
No semantic validator, deduplication, grading, repair prompt or content retry is added. Unknown
references and unusual response shapes remain visible; Python never invents missing assignments.
Operationally failed or unreadable jobs resume their recorded checkpoint thread. Input fingerprints
start fresh dependent jobs when recovered inputs change, preserving prior responses/publications.

Run layout:

- inputs/: exact three input copies and prompts; source/manifest.json and source/s*.json: windows.
- responses/phase/page/fingerprint/response.json: saved completed model objects.
- understanding/: readable profile fragments and source-linked evidence inventory.
- catalogues/initial.json, final.json and final.md: domain definitions and change reasons.
- facts/fact-id.json: immutable bodies/source references; facts/index.json: currently active IDs.
- initial_assignments.json and review/: independent ownership and review records.
- publication.json: pointer to the current publication under publications/id/.
  It contains domains/domain-id/facts.json and facts.md, plus JSON and Markdown assignment audits.
- run.json, run.log, usage.jsonl and checkpoints.sqlite3: execution, safe operational events,
  provider token usage and retrieval recovery.

Execution status is separate from assignment coverage: a complete run may still have unresolved
facts. “No Extra” means every RECORDED fact has an owner, not proof of complete source extraction.
CLI --check-only is observational and makes no writes. The notebook prints only start/final status,
run path and log path.

**Schema 4 is not yet integrated with Layers 3/4.** No misleading legacy missions/ handoff is
generated. Historical schema-2/3 Layer 2 artifacts remain untouched but cannot execute or run checks
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
