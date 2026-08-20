# CDI Deep Research

CDI turns one structured real-estate fact sheet into checked research missions and then into
evidence-backed subject reports. Python runs through the `compute` Conda interpreter at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` converts `fact_sheet.md` into fourteen mission JSON files. One agent
  reads the sheet and writes the missions itself; it does no web research, and a run is complete
  when its report records no failures.
- `ML/deep_research/layer3/` runs fourteen stable mission supervisors. Each delegates to five fixed
  lens subagents, may send direct question-only follow-ups, may add one narrowly scoped lens, and
  returns one complete mission bundle for the application to commit atomically.
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

The model is fixed in code to `gpt-5.6-luna` with high reasoning effort. Layer 3 uses Deep Agents
0.7.7. Each mission has a stable SQLite-checkpointed thread and thread-scoped `StateBackend`
scratch shared with its fixed lens subagents. It has no general-purpose subagent, `StoreBackend`,
host shell, `run_python`, model-writable run directory, or cross-property memory.

## Layer 2

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
.\run.ps1 -Resume '.\runs\L2_YYYYMMDD_xxxx'
```

Layer 2 is one harness agent. It is given the fact sheet, the frozen roster, a filesystem, Python
and two kinds of helper it can spawn, and told what the output must contain rather than how to
produce it — it decides how to read the sheet, how to allocate facts and how to check its own work.
The report that follows counts and records; it never rejects.
`ML/deep_research/docs/260820_Layer2_Code_Walkthrough_ENG.md` walks the code end to end.

## Layer 3

Enable live research only for public or invented input:

```powershell
.\run.ps1 -Research '.\runs\L2_YYYYMMDD_xxxx' -Online -PublicInputConfirmed
```

Resume an interrupted run, or explicitly retry failed mission supervisors:

```powershell
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx'
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx' -RetryFailed
```

Layer 3 exposes only `search_web`, `read_source`, and `cite` as research tools. Five required lens
files per mission produce exactly 70 base files; an optional additional-lens file may be present for
each mission, and fourteen final answers are required. `run.json` records mission status, while
SQLite preserves each mission's resumable agent state. The model never writes the run folder:
application code validates and atomically commits each complete mission bundle.

Raw page bytes, canonical text, hashes, citations, query decisions, and usage remain retained.
Binary/PDF sources cannot support claims until deterministic PDF extraction is added.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers both complete check reports, mission handoff, fixed-lens
isolation, direct question-only follow-up, citation and egress controls, checkpoint recovery,
atomic mission commits, and the 350-line executable-source limit.
