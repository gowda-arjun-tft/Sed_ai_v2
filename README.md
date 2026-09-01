# CDI Deep Research

CDI turns one structured real-estate fact sheet into routed domain context, property-risk reports and
an external-influence landscape. Python runs through the `compute` Conda interpreter at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` token-splits `fact_sheet.md`, routes chunks through independent
  JSON-mode Deep Agent calls, then appends available domain results in source order.
- `ML/deep_research/layer3/` runs eight direct domain researchers sequentially. Each uses the two
  evidence tools and writes one domain report before property synthesis.
- `ML/deep_research/layer4/` separates internal conditions, forms unresearched external candidates,
  reuses the direct researcher for external pathways, and writes one cross-domain synthesis.
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

## Layer 2

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
.\run.ps1 -Resume '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx'
```

Layer 2 uses fixed 60,000-token source windows with a 10,000-token overlap (50,000-token stride) and
runs at most five independent calls concurrently through the graph's native batch interface. It
does not align chunks to headings or paragraphs. Repeated overlap is labelled as continuity context
so the model allocates output from new source content while retaining cross-boundary meaning. The reusable graph uses LangChain
JSON-object type and has no tools, subagents, memory, checkpointer, summarizer, semantic schema or
content-repair retry. Transient provider failures receive up to three retries. Responses are saved
under `chunks/`; resume reuses any JSON object and reruns only failed, missing or invalid JSON.
Python appends available results in order without semantic checking or deduplication, so one failed
chunk does not block the others. Partial runs print each failed chunk and the resume command.
New runs publish only each domain's routed facts and supported meaning; they do not generate a
separate mission or question section. Layer 2 schema 3 accepts only this fixed-window,
overlap-partitioned contract; schema-2 artifacts remain unchanged but cannot resume or run checks.
Technical checks run read-only through `--check-only`. `usage.jsonl` records each application attempt
as it finishes and malformed usage lines are ignored. `run.log` records append-only operational
status without prompts, source text, model responses or secrets. The notebook prints one start
status followed by final status, run path and log path.

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

For each domain, Layer 4 makes one tool-free internal-segregation call, one tool-free
external-candidate call, and one direct external-research run with only `search_web` and
`read_source`. It copies the source Layer 3 model, web and context settings into its own run,
checkpoints, source store and usage log. The final synthesis is tool-free. All completed Markdown is
saved verbatim; Python does not grade, repair or retry completed content.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers the Layer 2/3/4 handoffs, direct-researcher tool
isolation, sequential execution, direct response publication, egress controls, checkpoint
recovery, optional operational reporting, and the 350-line executable-source limit.
