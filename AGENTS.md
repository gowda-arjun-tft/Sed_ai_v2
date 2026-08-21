# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` splits Markdown fact sheets and merges structured chunk responses into
eight mission JSON files. `ML/deep_research/layer3/` runs eight direct researchers concurrently,
one comprehensive review, one optional clarification batch, and synthesis. Prompts sit below each
layer's `prompts/` folder; design notes are in `ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.

## Build, Test, and Development Commands

Use the `compute` interpreter:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

Run Layer 2 with `.\run.ps1 -FactSheet <fact_sheet.md>` and Layer 3 with
`.\run.ps1 -Research <L2-run> -Online -PublicInputConfirmed`. Resume with `-Resume` or `-ResumeL3`.

## Coding Style & Testing

Use Python 3.11+, four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE`
constants. Prefer existing helpers and the standard library. Keep writes atomic and resumable.
No executable Python, PowerShell, or application source file may exceed 350
lines; split near 300. Prompts, skills, specifications, and documentation are exempt.

Tests use offline `unittest`. Cover changed parsing, resume, schema,
egress, citation, or publication behavior. Do not hardcode check counts.

## Agent and Security Boundaries

Keep secrets only in `.env`. The model is fixed to `gpt-5.6-luna`, with no application output-token
ceiling. Layer 2 uses maximum reasoning; Layer 3 currently uses low reasoning for every model and
web-search proxy call while live behavior is measured. Do not
restate model, search, token, source, or report limits in prompts.

Layer 2 uses 50K-token chunks, 5K overlap, concurrency five, and no tools, subagents, memory,
checkpointer, or summarizer. Save chunk responses atomically and merge them in order without
semantic verification or deduplication.

Layer 3 researchers receive `search_web`, `read_source`, `cite`, `append_report`, and offload-only
`read_file`. Python schedules eight isolated initial stages, one review, one optional clarification
batch, and synthesis; it does not impose a model-turn quota. Prompts own research choice, domain
boundaries, handoffs, source selection, and terminal `supported / inference / unknown / immaterial`
judgement. Append each decision-relevant unit immediately with a stable fragment ID.
Python may enforce network safety, exact quotations, persistence, attribution, idempotent appends,
atomic publication, and structural checks. Never add keyword-based research policy, host shell,
`run_python`, cross-property memory, or model-writable run folders without explicit approval.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
