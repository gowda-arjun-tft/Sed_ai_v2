# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` converts Markdown fact sheets into fourteen checked mission files
through three flat steps — `create_run.py`, `agent.py`, `report.py` — wired by `cli.py`. It has no
`pipeline/` package: there are no phases between them. `fs.py`, `planner.py` and `settings.py` are
shared with Layer 3 and are not private to Layer 2.
`ML/deep_research/layer3/` consumes those missions through fourteen stable mission supervisors.
Each supervisor delegates to five fixed custom lens subagents, asks direct question-only follow-ups,
may use one optional additional lens, and returns one bundle for an atomic application commit.
`StateBackend` plus SQLite preserves mission-scoped agent memory; `run.json` owns mission status.
Prompts are under `layer2/prompts/` and `layer3/prompts/`; documentation is in
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

Run Layer 2 with `.\run.ps1 -FactSheet <fact_sheet.md>`. Run Layer 3 with
`.\run.ps1 -Research <L2-run> -Online -PublicInputConfirmed`. Resume with `-Resume` or `-ResumeL3`.

## Coding Style & Naming Conventions

Use Python 3.11+, four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE`
constants. Prefer standard-library and existing helpers. Keep mission commits and resume behavior
idempotent. No executable Python, PowerShell, or future application source file may exceed 350
lines; split files near 300 lines. Only prompts, skills, specifications, and documentation are
exempt. Never compress formatting to evade the limit.

## Testing Guidelines

Tests use `unittest` and must not call a model or the public web. Add focused coverage for parser,
resume, egress, citation, mission-status, or schema changes. Both layers must record every check passed
and none failed; never hardcode the count, since both check lists are expected to change.

## Commit & Pull Request Guidelines

Use short imperative commits such as `Add Layer 3 checkpoint recovery`. PRs must state affected
layers, validation results, and any schema, model, prompt, privacy, or resume change.

## Security & Configuration

Keep `OPENAI_API_KEY` only in `.env`. Never place secrets in prompts, logs, checkpoints, or run
artifacts.

Layer 2 is deliberately unsandboxed and must be described accurately. It gives the agent a
model-writable run folder and `run_python`, which executes model-authored code in a subprocess on
the host: that subprocess inherits the environment (`OPENAI_API_KEY` included), the host filesystem
and host network access, with no timeout, no output cap and no import restriction. The
`FilesystemPermission` deny on `inputs/**` constrains the built-in file tools only — it cannot
constrain a subprocess. So Layer 2 *does no web research*, but it is wrong to say it *cannot* reach
the web; earlier versions of this file claimed that and were incorrect. Run Layer 2 only on input
you would run any untrusted script against.

Layer 3 exposes only three guarded research tools: `search_web`, `read_source`, and `cite`. It uses
five fixed custom lens subagents and at most one additional-lens subagent per mission. It has no
general-purpose subagent, host shell, `run_python`, `StoreBackend`, model-writable run folder, or
cross-property durable memory. `StateBackend` scratch and SQLite checkpoints stay mission-scoped;
application code alone atomically commits durable run artifacts.
