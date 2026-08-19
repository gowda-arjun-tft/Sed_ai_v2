# CDI Layer 2

Turns one real-estate `fact_sheet.md` into fourteen checked research missions, following every
step in `docs/`.

`ML/deep_research/layer2/` holds the application code. The five pipeline steps are in `ML/deep_research/layer2/pipeline/`, one
file per step, named for what the step does. Shared code sits directly in `ML/deep_research/layer2/`: `settings.py`
(constants and the frozen agent roster), `fs.py` (paths, hashing, atomic writes), `factsheet.py`
(parsing the fact sheet), `planner.py` (loading and validating the roster), `progress.py` (the
resume ledger), `routing_tools.py` (the two Deep Agents tools) and `llm.py` (model wiring). The
single planner prompt is `ML/deep_research/layer2/prompts/planner_prompt.md`. `run.ps1` bootstraps and starts or
resumes a run. Specifications are in `ML/deep_research/docs/`. Offline tests are grouped by behaviour in `tests/`, outside `ML/` so they can cover every component as the repository grows.
Generated `runs/`, caches and `.env` are local-only and ignored.

| Step | File | What it does |
|---|---|---|
| 0 | `pipeline/create_run.py` | creates the run folder, copies and hashes both inputs |
| 1 | `pipeline/split_fact_sheet.py` | writes one piece per retained `##` section |
| 2 | `pipeline/route_facts.py` | routes every fact into one or more of the fourteen buckets |
| 3 | `pipeline/write_missions.py` | turns each bucket into one mission file |
| 4 | `pipeline/run_checks.py` | runs the nineteen checks and writes the record |

## Run

1. Open `.env` and set:

   ```text
   OPENAI_API_KEY=your-key
   ```

2. Install the pinned dependencies into the `compute` Conda environment:

   ```powershell
   & 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
   ```

3. Run:

   ```powershell
   .\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
   ```

The launcher and VS Code use `C:\src\anaconda3\envs\compute\python.exe`. The model is fixed in
code to `gpt-5.6-luna` with `reasoning_effort="high"`; it is intentionally not an `.env` setting.

Each completed run is self-contained under `runs/L2_YYYYMMDD_xxxx/`. The deliverables are the
fourteen files in `missions/`; `check_report.md` must say `19 passed · 0 failed` before they are
used.

## Resume

If a model/network call stops, keep the run folder and resume it:

```powershell
.\run.ps1 -Resume '.\runs\L2_YYYYMMDD_xxxx'
```

Completed pieces and missions are skipped. Bucket appends are idempotent, so retrying an
incomplete piece does not duplicate facts.

## Offline check

No API call is made by the tests:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
```

Phase 0 copies and hashes both inputs. Phase 1 splits only at Markdown `##` section boundaries. Phase 2
routes facts with a Deep Agents harness and two validated append/progress tools. Phase 3 uses the
same configured OpenAI model to write mission prose; exact context transcription is ordinary code.
Phase 4 runs the specified nineteen deterministic checks and writes the final record. An offline
structure test also rejects any executable source file longer than 350 lines.
