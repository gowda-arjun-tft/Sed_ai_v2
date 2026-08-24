# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` splits Markdown fact sheets and merges available JSON chunk responses
into eight mission files. `ML/deep_research/layer3/` runs eight domain-scoped STORM coordinators
sequentially, then one property synthesis. Prompts sit below each layer's `prompts/`; design notes
are in `ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.
Group new runs as `runs/<parent>-<markdown-name>-<short-path-id>/L2_*` and place the derived `L3_*`
beside its Layer 2 source. Keep legacy flat run folders resumable.

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
ceiling. Layer 2 uses maximum reasoning. Layer 3 defaults to low model and web-search proxy
reasoning and low web-search context and verbosity; new runs may select supported levels and
freeze those controls in `run.json`. Do not
restate model, search, token, source, or report limits in prompts.

Layer 2 uses 50K-token chunks, 5K overlap, concurrency five, and no tools, subagents, memory,
checkpointer, summarizer, semantic response schema, or content-repair retry. Use LangChain
`ProviderStrategy` only to require one top-level JSON object and three provider retries for transient
transport failures. Accept any keys and nested values, save the object atomically, and merge
available results in order without semantic verification, deduplication, all-or-nothing publication,
or automatic completion checks.

## Model-Output Freedom

Prompts guide model behavior; application code must not grade or control completed model content.
Do not add exact Pydantic response schemas, required-key or extra-key rejection, semantic coverage
checks, keyword/language filters, content-repair calls, schema-based resume retries, auxiliary-file
completion gates, or checks that change run status. Never make one failed model call prevent
available sibling outputs from being saved or published. Explicit `--check-only` diagnostics must
remain observational and non-mutating.

Python may parse the selected wire format, reject unreadable serialization, enforce authentication
and network safety, protect atomic writes, record attribution and usage, and expose transport
failures. These operational boundaries must never resend completed content to an LLM for repair or
replace the model's judgement with application-authored conclusions.

Each Layer 3 coordinator receives only `task`. Its five lens subagents and citation verifier receive
only `search_web` and `read_source`; synthesis has no tools. Python schedules one coordinator at a
time, saves each final assistant response verbatim, then synthesizes every available response.
Prompts own research, contradiction mapping, citation verification, and corrections. Python may
enforce network safety, persistence, attribution, and atomic publication, but must not grade
Markdown, require auxiliary model-written files, or trigger content-repair calls. Implicit
framework summarization and tool-call repair middleware stay disabled. A run-frozen CDI
summarizer may compact only the five lenses and citation verifier; it must retain source pointers,
must not grade content, and must not block publication. Never add
keyword-based research policy, host shell, `run_python`, cross-property memory, or model-writable
host folders without explicit approval.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
