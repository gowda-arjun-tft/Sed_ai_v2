# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` converts Markdown fact sheets into fourteen checked mission files
through three flat steps — `create_run.py`, `agent.py`, `report.py` — wired by `cli.py`. It has no
`pipeline/` package: there are no phases between them. `fs.py`, `planner.py` and `settings.py` are
shared with Layer 3 and are not private to Layer 2.
`ML/deep_research/layer3/` consumes those missions through six phases: run creation, five-lens
research, question aggregation, question-only second rounds, final aggregation, and its own checks.
Shared Layer 3 contracts, tools, source storage, register logic, and providers sit beside its
`pipeline/` directory. Prompts are under `layer2/prompts/` and `layer3/prompts/`; documentation is in
`ML/deep_research/docs/`. Model-free tests live in `tests/`.

Generated `runs/`, `.env`, caches, sources, and checkpoint databases are local-only.

## Build, Test, and Development Commands

Use the compute interpreter:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

Run Layer 2 with `.\run.ps1 -FactSheet <fact_sheet.md>`. Run Layer 3 offline with
`.\run.ps1 -Research <L2-run> -Fixtures <fixture-root>`, or online only with
`-Online -PublicInputConfirmed`. Resume with `-Resume` or `-ResumeL3`.

## Coding Style & Naming Conventions

Use Python 3.11+, four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE`
constants. Prefer standard-library and existing helpers. Keep phase functions explicit and
idempotent. No executable Python, PowerShell, or future application source file may exceed 350
lines; split files near 300 lines. Only prompts, skills, specifications, and documentation are
exempt. Never compress formatting to evade the limit.

## Testing Guidelines

Tests use `unittest` and must not call a model or the public web. Add focused coverage for parser,
resume, egress, citation, register, or schema changes. Both layers must record every check passed
and none failed; never hardcode the count, since both check lists are expected to change.

## Commit & Pull Request Guidelines

Use short imperative commits such as `Add Layer 3 checkpoint recovery`. PRs must state affected
phases, validation results, and any schema, model, prompt, privacy, or resume change.

## Security & Configuration

Keep `OPENAI_API_KEY` only in `.env`. Never place secrets in prompts, logs, checkpoints, or run
artifacts. Layer 2 has no web access. Layer 3 exposes only guarded research tools: no subagents,
host shell, model-writable run folder, or cross-property durable memory.
