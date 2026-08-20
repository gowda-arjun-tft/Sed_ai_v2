# CDI Deep Research

CDI turns one structured real-estate fact sheet into checked research missions and then into
evidence-backed subject reports. Python runs through the `compute` Conda interpreter at
`C:\src\anaconda3\envs\compute\python.exe`.

## Structure

- `ML/deep_research/layer2/` converts `fact_sheet.md` into fourteen mission JSON files. It never
  accesses the web and is complete only at `19 passed · 0 failed`.
- `ML/deep_research/layer3/` runs five independent research lenses per mission, writes unattributed
  questions, performs question-only second rounds, optionally adds one sixth lens, and produces
  fourteen answers. It is complete only at `24 passed · 0 failed`.
- `ML/deep_research/docs/` contains the Layer 2 phase specifications.
- `tests/` contains model-free unit and end-to-end fixture tests.

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
0.7.7 with thread-scoped SQLite checkpoints; it intentionally has no cross-property memory,
subagents, host shell, or model-writable run directory.

## Layer 2

```powershell
.\run.ps1 -FactSheet 'C:\full\path\to\fact_sheet.md'
.\run.ps1 -Resume '.\runs\L2_YYYYMMDD_xxxx'
```

Layer 2 splits only on Markdown `##` sections, routes exact fact blocks, writes fourteen missions,
and preserves the existing nineteen deterministic checks.

## Layer 3

Run the whole six-phase pipeline offline. Fixture mode makes no model or web API calls:

```powershell
.\run.ps1 -Research '.\runs\L2_YYYYMMDD_xxxx' -Fixtures '.\tests\fixtures\web'
```

Enable live research only for public or invented input:

```powershell
.\run.ps1 -Research '.\runs\L2_YYYYMMDD_xxxx' -Online -PublicInputConfirmed
```

Resume an interrupted run, or explicitly retry failed sessions and dependent aggregation:

```powershell
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx'
.\run.ps1 -ResumeL3 '.\runs\L3_YYYYMMDD_xxxx' -RetryFailed
```

Layer 3 retains raw page bytes, canonical text, hashes, exact-quote citations, query decisions,
usage, stable thread IDs, and an 84+ row register. Binary/PDF sources are retained but cannot
support claims until deterministic PDF extraction is added.

## Validation

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

The suite makes no model calls. It covers both complete check reports, citation verification,
egress rejection, private-host rejection, idempotent logs, checkpoint construction, second-round
byte preservation, and the 350-line executable-source limit.
