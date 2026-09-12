# CDI Deep Research

Layer 2 designs plugin-driven domains and organizes supplied evidence. Layer 3 finds and tests sources
for those dynamic domains, uploads unique documents and runs one persistent researcher per domain,
producing independent cited Markdown reports without final synthesis. Layer 4 remains available for historical
schema-8 research inputs only and is disabled by default in the notebook. Windows Python uses `compute` at
`C:\src\anaconda3\envs\compute\python.exe`.
For VS Code Docker development, follow the [Docker guide](docker/README.md): open the original
project in its Dev Container and select `/usr/local/bin/python`. Layer 2 uses schema 9 on this branch.

## Structure

- `ML/deep_research/layer2/` designs plugin-driven domains, reads original source windows,
  builds subject metadata, decides domains and distributes Markdown without a reviewer.
- `ML/deep_research/layer3/` runs one native source finder per actual Layer 2 domain, up to five
  concurrently, then uploads unique documents and runs persistent domain researchers sequentially without synthesis.
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

The model remains `gpt-5.6-luna`. Layer 3 source discovery defaults to high reasoning, medium native
web-search depth and low verbosity; new runs freeze selected controls. Neither Layer 2 nor Layer 3
sets an application output-token ceiling. Source discovery uses direct Responses API calls, without
Deep Agents graphs, custom tools, new SQLite or conversation memory. Existing Deep Agents helpers
remain for Layer 4's historical workflow.

## Layer 2 — schema 9

Supply original factsheet, selected industry plugin and user requirements. Review all inputs for
public web-assisted planning; the current requirements have a confidential origin. Confirmation
defaults to false and must be explicit before a new run is created.

    .\run.ps1 -FactSheet 'C:\path\facts.md' -DomainPlugin '.\ML\deep_research\layer2\plugins\real_estate.md' -Requirements 'C:\path\requirements.md' -Layer2WebSearchDepth high -Layer2WebSearchVerbosity medium -PublicInputConfirmed
    .\run.ps1 -Resume '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx'

Public Python uses `create_run(factsheet, plugin, requirements, runs_root,
reasoning_effort=..., web_search_context_size=..., web_search_verbosity=...,
public_input_confirmed=True)`, then `run_all(run_dir)`. The notebook exposes the same Layer 2
reasoning, search-depth and verbosity controls plus default-false public-input confirmation.

```text
Factsheet → 50K/5K windows → sequential asset_metadata.md
Metadata + plugin + requirements + optional native web search → internal JSON plan + domain_plan.md
Original windows + metadata + domain plan → ID-keyed Markdown contributions
Python → source-ordered domains/*.md; routing warnings link to the internal trace
```

Only the designer can search. It extends baseline responsibilities or adds distinct domains where
useful; there is no fixed final count. The real-estate plugin and requirements now allow financial,
valuation, ESG/CapEx, alternative-use and local-market research alongside the original priorities.
The designer uses web evidence for planning, not for inventing supplied asset facts.

Domain JSON contains IDs, names and responsibilities, with no Boundaries. Distribution is an ID-to-
Markdown JSON object. The web-enabled designer requests JSON through its prompt; only tool-free
distribution binds native JSON-object mode. Neither adds a strict nested schema or repair loop.
Names label files but IDs route them; duplicate/unusable values remain visible internally.
An unusable plan stops dependent work without resending a completed response. Python copies facts,
qualifications and topic sections without semantic deduplication or paraphrasing.

Keep native distribution concurrency five, direct calls, source seeks, three transport retries,
fresh messages, immediate saves, fingerprints/history and partial publication. No graph, reviewer,
SQLite or extra synthesis. Four source windows still mean nine logical stage calls, not necessarily
nine billed operations when hosted search is used. No application output-token cap.
Account for messages, tools, format and framing against 300K/350K input policy; the designer also
applies the 128K web-search limit. Oversized mandatory input fails safely without truncation.

Open README.md, asset_metadata.md, domain_plan.md, run.log and domains/. The exact JSON plan stays in its designer response trace. Inputs, raw responses, web sources,
usage, routing observations and history stay under _internal/. There is no visible unresolved.md.
Check-only is non-mutating. Historical Layer 2 schemas 2–8 are read-only. Completed schema-9 Markdown
now feeds Layer 3 source preparation and domain research; Layer 4 integration remains separate.

See the [Layer 2 workflow guide](ML/deep_research/layer2/README.md) and
[fixed quality benchmark](ML/deep_research/layer2/docs/research_context_benchmark.md).
Offline tests establish operational behavior, not perfect extraction or live search quality.

## Layer 3 — source preparation and domain research, schema 9

Review the completed Layer 2 metadata/domain files and editable source guidance before public-input
confirmation. New runs find sources, upload documents and continue into domain research.
Research requires the dedicated checkpoint volume in the Docker development service:

```powershell
.\run.ps1 -Research '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx' -SourceSuggestion '.\inputs\source_suggestion.md' -Online -PublicInputConfirmed
```

Resume a specific source run, or explicitly retry its operationally failed jobs:

```powershell
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx'
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx' -RetryFailed
.\run.ps1 -UploadDocumentsL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx'
```

Each finder receives complete shared metadata, its domain Markdown and source suggestions. Native
web search is required; the prompt asks it to open every proposed URL and report observed access.
It returns prompt-requested JSON (no API JSON mode) with URL, relevance, access/note and document flag.
New runs then fetch document candidates into temporary storage, deduplicate URLs and byte hashes,
upload once to OpenAI Files and add `upload_status`/`upload`/`file_id` to every matching source entry. File IDs are
reusable across the run's domains and resumptions. The versioned research capability then writes
`research/<domain>.md` through Deep Agents, with native planning and retrievable evidence. No synthesizer.

Outputs include readable `sources/*.json`, independent `research/*.md`, README, metadata and `run.log`. Exact raw
model text, full provider messages,
available actions/annotations and usage remain under `_internal/trace`. Completed invalid or empty
responses stay saved with visible warnings, without repair calls or coverage-based failures.
Frozen inputs, file-based recovery and successful-sibling publication are retained. The effective
source-finder input limit is the smaller of model capacity, application ceiling and the 128K web-search allowance.
Main research uses a 300K target/350K ceiling with explicit retrievable compaction beginning at 250K.
Historical schema-8 research execution/checks are rejected without mutation.

The notebook exposes explicit source/resume paths and preserves the user's current consent selection;
new-run APIs still default public-input confirmation to False.
blank source path uses `L2_DYNAMIC_RUN`. `LAYER3_UPLOAD_ONLY = True` requires an explicit resume path
and enriches saved source JSON without searches. Older runs otherwise remain source-only.
Uploaded files persist until manually deleted; upload success does not establish readability. Individual
document failures remain visible and excluded from future research without making completed source discovery partial.
See the [Layer 3 guide](ML/deep_research/layer3/README.md) for safety, recovery and retention details.

For existing preparation, set `LAYER3_PREPARED_RUN_PATH` in the notebook, or use
`python -m ML.deep_research.layer3 --research-from '<prepared-L3-run>' --online --public-input-confirmed`
inside the development container. A new linked run preserves the parent and starts research without
repeating source discovery/uploads. Main research reasoning defaults to `max`. Resume its explicit new
run path to reuse completed reports and interrupted checkpoint threads. New research capability version 2
uses one domain at a time and 80 shared logical model calls per domain, including search, document
analysis and summarization. Wrap-up starts after 60 calls; after 70 only saved-file reading and
finalization remain; the last call is reserved for tool-free report writing. An exhausted unfinished
domain stays partial without blocking other domains. Historical policies are not changed.
Edit `inputs/user_research_instruction.md` (notebook `LAYER3_RESEARCH_INSTRUCTION_PATH`, CLI
`--research-instruction`, PowerShell `-ResearchInstruction`) to request risks/opportunities/actions
or another objective. Linked runs import available prior evidence and notes into fresh threads;
parent usage remains separate. No dollar or output-token cap is added. Offline checks do not establish live quality.

## Layer 4

Layer 4 is disabled by default in the notebook. For explicit historical use only, start from an
existing schema-8 Layer 3 research run, not the new source-discovery JSON:

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

The suite makes no model calls. It covers dynamic source inputs, bounded concurrency, native request
serialization, exact JSON preservation, file recovery, non-mutating checks and notebook safety.
Historical Layer 4 harness/egress/checkpoint tests and the 350-line source limit remain covered.
