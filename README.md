# CDI Deep Research

CDI turns one structured real-estate fact sheet into checked research missions and then into
evidence-backed subject reports. Python runs through the `compute` Conda interpreter at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` token-splits `fact_sheet.md`, routes chunks through independent
  structured Deep Agent calls, then appends eight domain mission JSON files in source order.
- `ML/deep_research/layer3/` starts eight isolated domain researchers concurrently, performs one
  comprehensive review, optionally runs one targeted clarification batch, and writes one property
  synthesis.
- `ML/deep_research/docs/` contains the Layer 2 code walkthrough and the global-readiness notes.
- `tests/` contains model-free unit and fabricated end-to-end run tests.

Generated `runs/`, `.env`, caches, sources, and checkpoint databases remain local and are ignored.

## Setup

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
```

Set only the API key in `.env`:

```text
OPENAI_API_KEY=your-key
```

The model is fixed in code to `gpt-5.6-luna`. Layer 2 uses maximum reasoning. Layer 3 currently uses
low reasoning for its research, review, synthesis, and web-search proxy calls while live behavior is
measured; this is configuration, not a separate test command. Neither layer sets an application
output-token ceiling; provider limits still apply. Layer 3 uses Deep Agents 0.7.7 with stable SQLite
stage threads and thread-scoped `StateBackend` scratch. It has no general-purpose subagent, `task`,
`StoreBackend`, host shell, `run_python`, model-writable run directory, or cross-property memory.
Web-search context remains low.

## Layer 2

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
.\run.ps1 -Resume '.\runs\L2_YYYYMMDD_xxxx'
```

Layer 2 targets 50,000 tokens per chunk with a 5,000-token overlap and runs at most five independent
calls concurrently. The reusable graph has provider-native structured output and no tools,
subagents, memory, checkpointer or summarizer. Responses are saved under `chunks/`; resume reruns
only missing or invalid-JSON chunks. Python appends results in order without semantic checking or
deduplication, writes eight missions and performs four technical completion checks. `usage.jsonl`
records each chunk call as it finishes. Legacy checkpoint-based runs must be restarted fresh.
`ML/deep_research/docs/260820_Layer2_Code_Walkthrough_ENG.md` walks the code end to end.

## Layer 3

Enable live research only for public or invented input:

```powershell
.\run.ps1 -Research '.\runs\L2_YYYYMMDD_xxxx' -Online -PublicInputConfirmed
```

Resume an interrupted run, or explicitly retry only failed stages with clean threads:

```powershell
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx'
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx' -RetryFailed
```

Layer 3 gives each domain researcher `search_web`, `read_source`, `cite`, `append_report`, and
offload-only `read_file`. Eight initial researchers start together. Each works through a finite
five-facet decision ledger, uses result snippets to choose sources, and durably appends every
decision-relevant unit as soon as it is ready. `Unknown` is a completed finding, not a reason to keep
searching. One reviewer returns the comprehensive review and optional bare questions; Python runs
one clarification batch for the addressed domains, then synthesis finishes without another review.
`run.json`, SQLite checkpoints, partial reports, and `usage.jsonl` make progress resumable and visible.

Raw page bytes, canonical text, hashes, citations, query decisions, and usage remain retained.
Binary/PDF sources cannot support claims until deterministic PDF extraction is added.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers both complete check reports, eight-domain handoff, parallel
research, the finite ledger and append contract, one optional clarification batch, citation and
egress controls, checkpoint recovery, publication, and the 350-line executable-source limit.
