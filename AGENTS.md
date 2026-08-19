# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` holds the application code. The five pipeline steps are in `ML/deep_research/layer2/pipeline/`, one
file per step, named for what the step does. Shared code sits directly in `ML/deep_research/layer2/`: `settings.py`
(constants and the frozen agent roster), `fs.py` (paths, hashing, atomic writes), `factsheet.py`
(parsing the fact sheet), `planner.py` (loading and validating the roster), `progress.py` (the
resume ledger), `routing_tools.py` (the two Deep Agents tools) and `llm.py` (model wiring). The
single planner prompt is `ML/deep_research/layer2/prompts/planner_prompt.md`. `run.ps1` bootstraps and starts or
resumes a run. Specifications are in `ML/deep_research/docs/`. Offline tests are grouped by behaviour in `tests/`, outside `ML/` so they can cover every component as the repository grows.
Generated `runs/`, caches and `.env` are local-only and ignored.

## Build, Test, and Development Commands

Run a fact sheet from PowerShell:

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
```

Resume an interrupted run without duplicating completed work:

```powershell
.\run.ps1 -Resume '.\runs\L2_YYYYMMDD_xxxx'
```

Run deterministic tests without an API call:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
```

Use `& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests` for a quick syntax check. Install dependencies with `& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt`.

## Coding Style & Naming Conventions

Use the `compute` Conda interpreter at `C:\src\anaconda3\envs\compute\python.exe`. Use Python 3.11+ syntax, four-space indentation, type hints, and standard-library solutions before adding dependencies. Follow `snake_case` for functions and variables, `UPPER_CASE` for constants, and `test_<behavior>` for tests. Keep phase functions explicit and sequential. Prefer small root-cause fixes over new abstractions. No formatter or linter is configured; follow PEP 8 and keep imports grouped with the standard library first.

Executable source files must not exceed 350 lines; aim to split them once they approach 300–350 lines. This applies to Python, PowerShell, and future application code. Only text-heavy content—such as prompts, skills, specifications, and documentation—is exempt. Do not bypass the limit with compressed formatting or multiple unrelated responsibilities in one file.

## Testing Guidelines

Tests use `unittest` and must remain model-free. Add one focused regression test for every non-trivial branch, parser change, resume rule, or validation change. Preserve exact-string checks for fact blocks, evidence, and source locators. A deliverable is valid only when `check_report.md` records `19 passed · 0 failed`.

## Commit & Pull Request Guidelines

Use short imperative commits such as `Fix section-boundary splitting`. Pull requests should describe affected phases, include the test command and result, and call out any change to mission schemas, agent names, model settings, or resume behavior. Screenshots are unnecessary unless output presentation changes.

## Security & Configuration

Keep `OPENAI_API_KEY` only in `.env`; never commit, print, or place it in prompts or run artifacts. Do not add shell access, web research, subagents, or durable memory to Layer 2 without an explicit requirement.
