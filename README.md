# CDI Deep Research

CDI turns one structured real-estate fact sheet into checked research missions and then into
evidence-backed subject reports. Python runs through the `compute` Conda interpreter at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` token-splits `fact_sheet.md`, routes chunks through independent
  JSON-mode Deep Agent calls, then appends available domain results in source order.
- `ML/deep_research/layer3/` runs eight domain-scoped STORM coordinators sequentially. Each
  delegates to five research lenses, verifies citation clusters through a sixth specialist, and
  writes one domain report before property synthesis.
- `ML/deep_research/docs/` contains archived run-verification notes; the root architecture HTML is
  the current visual contract.
- `tests/` contains model-free unit and fabricated end-to-end run tests.

Generated `runs/`, `.env`, caches, sources, and checkpoint databases remain local and are ignored.
New runs are grouped by the input path so repeated work stays easy to identify:

```text
runs/<parent>-<markdown-name>-<short-path-id>/
  L2_YYYYMMDD_HHMMSS_xxxx/
  L3_YYYYMMDD_HHMMSS_xxxx/
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
low reasoning for coordinators, lenses, verifiers, synthesis, and web-search proxy calls while live behavior is
measured; this is configuration, not a separate test command. Neither layer sets an application
output-token ceiling; provider limits still apply. Layer 3 uses Deep Agents 0.7.7 with stable SQLite
coordinator threads and thread-scoped `StateBackend` scratch. Only the coordinator receives `task`;
the general-purpose subagent, `StoreBackend`, host shell, `run_python`, model-writable host folders,
and cross-property memory remain disabled. Web-search context remains low.

## Layer 2

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
.\run.ps1 -Resume '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx'
```

Layer 2 targets 50,000 tokens per chunk with a 5,000-token overlap and runs at most five independent
calls concurrently. The reusable graph uses LangChain `ProviderStrategy` with a permissive top-level
JSON-object type and has no tools, subagents, memory, checkpointer, summarizer, semantic schema or
content-repair retry. Transient provider failures receive up to three retries. Responses are saved
under `chunks/`; resume reuses any JSON object and reruns only failed, missing or invalid JSON.
Python appends available results in order without semantic checking or deduplication, so one failed
chunk does not block the others. Partial runs print each failed chunk and the resume command.
Technical checks run only through `--check-only`. `usage.jsonl` records each application attempt
as it finishes and malformed usage lines are ignored.

## Layer 3

Enable live research only for public or invented input:

```powershell
.\run.ps1 -Research '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx' -Online -PublicInputConfirmed
# Optional for a new run; German and English are the default.
.\run.ps1 -Research '.\runs\<fact-sheet>\L2_YYYYMMDD_HHMMSS_xxxx' -Online -PublicInputConfirmed -OcrLanguages 'de,en'
```

Resume an interrupted run, or explicitly retry only failed stages from their checkpoints:

```powershell
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx'
.\run.ps1 -ResumeL3 '.\runs\<fact-sheet>\L3_YYYYMMDD_HHMMSS_xxxx' -RetryFailed
```

Layer 3 processes one domain coordinator at a time. The coordinator has only `task` and delegates
to five fixed lenses: practitioner, academic, skeptic, economist, and historian. Those lenses and
the citation verifier receive only `search_web` and `read_source`. After contradiction mapping,
drafting, and agent-led citation verification, the coordinator's final assistant Markdown is saved
verbatim. The synthesis harness receives the available domain responses directly and has no tools.

For new runs, `read_source` retains every fetched file by content hash. Text, Markdown, and JSON
use the same durable lifecycle directly; PDF, DOCX, PPTX, HTML, and images are converted by an
isolated local Docling worker. A document wait is checkpointed as `waiting_for_documents`, and the
same coordinator thread resumes automatically when extraction finishes. Large documents return a
map and can be reopened with `pages` or `find`; extracted pages, combined Markdown, manifests, and
batch Docling JSON remain under `sources/documents/<source-sha256>/`. Runs created before this
policy retain the legacy source-reading behavior. Before a new-policy run can make a provider call,
a local preflight imports Docling and EasyOCR, constructs the converter, and completes a worker
subprocess; a failure stops locally without API usage.

Citation accuracy is judged by the verifier agents rather than a Python quote parser. Python retains
secure URL handling, raw page bytes, canonical text, query caching, usage, checkpoints, and atomic
writes. It does not require lens files, verifier files, non-empty Markdown, hashes, or check results,
and it does not repair or retry completed content. Schema-6 runs remain untouched and require a
fresh schema-7 run.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers eight-domain handoff, STORM tool isolation, sequential
coordinator execution, direct response publication, egress controls, checkpoint recovery, optional
operational reporting, and the 350-line executable-source limit.
