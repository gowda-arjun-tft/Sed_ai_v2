# CDI Deep Research

Layer 2 designs plugin-driven domains and organizes supplied evidence. Existing Layers 3/4 research
real-estate risks and external influences using historical Layer 2 inputs. Python uses `compute` at
`C:\src\anaconda3\envs\compute\python.exe`.
For VS Code Docker development, follow the [Docker guide](docker/README.md): open the original
project in its Dev Container and select `/usr/local/bin/python`. Layer 2 uses schema 9 on this branch.

## Structure

- `ML/deep_research/layer2/` designs plugin-driven domains, reads original source windows,
  builds subject metadata, decides domains and distributes Markdown without a reviewer.
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
Check-only is non-mutating. Historical schemas 2–8 are read-only; **schema 9 is not integrated with
Layers 3/4**, whose implementations and notebook cells remain unchanged.

See the [Layer 2 workflow guide](ML/deep_research/layer2/README.md) and
[fixed quality benchmark](ML/deep_research/layer2/docs/research_context_benchmark.md).
Offline tests establish operational behavior, not perfect extraction or live search quality.

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
