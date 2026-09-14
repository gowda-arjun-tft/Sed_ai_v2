# CDI Research

```text
One notebook cell
 → Domain Decider: metadata → domains → supplied domain facts
 → Research Module: sources → document uploads → domain research
 → Independent Markdown reports (no synthesizer)
```

## Setup

Open the original repository with **Dev Containers: Reopen in Container** in VS Code.
Select **SedAI Docker — Python 3.12**, `/usr/local/bin/python`. Follow
[Docker development](docker/development.md) for setup, checkpoint storage and diagnostics.
The shared `/app` mount exposes the original code, Git, inputs and runs. Never use two
writers for one run or restart a container during research. Store `OPENAI_API_KEY` in the
runtime environment or `.env`, never in code or logs.

Review inputs before public-input confirmation: the requirements have a confidential
origin. Freezing them does not make them public. APIs default consent to false; the notebook
retains the user's explicit `True` selection. Review it before running.

## Organization

```text
ML/deep_research/
├── domain_decider/
│   ├── __init__.py + __main__.py
│   ├── backend/       Execution, persistence, publication, CLI
│   ├── ML/prompts/    Three direct-call prompts and model helpers
│   ├── plugins/       Industry responsibilities
│   └── docs/          Audits and fixed quality benchmark
├── research_module/
│   ├── __init__.py + __main__.py
│   ├── backend/       Preparation, uploads, budgets, recovery
│   └── ML/            Agent, tools, middleware, providers/, prompts/
└── docs/              Current architecture and historical evidence
```

The [architecture overview](ML/deep_research/docs/Research_Architecture_Overview.md)
describes all stages, limits, memory, source eligibility and recovery, with a historical
document index. [AGENTS.md](AGENTS.md) defines working rules;
[Railway Track](railway-track/change.md) records changes. There are no old-package wrappers,
new shared-runtime package or installable wheel. The harness and pinned dependencies remain unchanged.

## One notebook execution cell

Open [CDI_Layer2_Layer3.ipynb](CDI_Layer2_Layer3.ipynb). Preserve unsaved editor changes before
reloading it; restart only an idle kernel to clear old imports. The filename and Docker kernel
are unchanged. Historical output is not attached to the new cell.

| Input/control | Meaning |
| --- | --- |
| `FACT_SHEET_PATH` | Original factsheet |
| `LAYER2_DOMAIN_PLUGIN`, `LAYER2_REQUIREMENTS` | Industry duties and user objectives |
| `LAYER3_SOURCE_SUGGESTION_PATH` | Preferred source authorities/classes |
| `LAYER3_RESEARCH_INSTRUCTION_PATH` | Editable report purpose; default risks, opportunities and actions |
| `LAYER3_RESEARCH_CONFIG_PATH` | Per-domain operational call thresholds |
| `LAYER2_REASONING_EFFORT` | Domain-preparation reasoning |
| `DOMAIN_WEB_SEARCH_DEPTH`, `DOMAIN_WEB_SEARCH_VERBOSITY` | Domain designer only |
| `LAYER3_MODEL_REASONING_EFFORT` | Source-discovery reasoning |
| `LAYER3_RESEARCH_REASONING_EFFORT` | Persistent researcher reasoning |
| `SOURCE_WEB_SEARCH_DEPTH`, `SOURCE_WEB_SEARCH_VERBOSITY` | Research Module search settings |
| `PUBLIC_INPUT_CONFIRMED` | Required permission for public provider processing |
| `LAYER3_RETRY_FAILED` | Retry operational failures, never completed-content repair |

Current notebook selections remain max reasoning, medium depth, low verbosity, confirmed
input and retry-failed enabled. API defaults are unchanged. New runs freeze selected settings.
The default research config is `{"maximum_calls":80,"wrap_up_after":60,"finalize_after":70}`.
Three explicit nulls mean unlimited application calls, not unlimited provider credit/context.
Otherwise require integers with `0 <= wrap_up_after < finalize_after < maximum_calls`.
Missing, duplicate, unknown, empty or invalid settings are errors, not unlimited execution.

### Select one action

| Selection | Result |
| --- | --- |
| All action paths blank | Create/run domains, then create/run research from that exact completed run |
| `LAYER3_SOURCE_RUN_PATH` | Existing Domain Decider run: reuse complete output or resume incomplete work, then create research |
| `LAYER3_RESUME_RUN_PATH` | Resume only that Research Module run with frozen settings |
| `LAYER3_PREPARED_RUN_PATH` | New linked research-only run; preserve its settled preparation parent |
| `LAYER3_UPLOAD_ONLY=True` + resume path | Upload-only enrichment; no model calls |

All paths default blank; upload-only defaults false. Conflicts fail before creating runs.
Fresh execution preflights paths, config, consent, key and checkpoint storage before model
work. Domain failure/partial status stops the chain with its saved status and log location.
A rerun with blank paths creates new runs; recovery requires an explicit path.
The cell shows both paths/logs, discovery/upload/research status, completed-domain counts,
per-domain call usage and report location. It adds no agent or research loop.

## Public APIs and recovery commands

```python
from ML.deep_research.domain_decider import create_run, run_all
from ML.deep_research.research_module import (
    create_run as create_research, create_research_run,
    run_all as run_research, upload_documents, run_checks,
)
```

Domain Decider: `create_run(factsheet, plugin, requirements, runs_root,
public_input_confirmed=True, reasoning_effort=..., web_search_context_size=...,
web_search_verbosity=...)`, then synchronous `run_all(run)`.

Research Module: `create_research(completed_domain_run, runs_root,
source_suggestion=..., research_instruction=..., research_config=...,
public_input_confirmed=True, reasoning_effort=..., research_reasoning_effort=...,
web_search_context_size=..., web_search_verbosity=...)`, then `await run_research(run)`.
`runs_root` remains accepted; research is colocated beside its domain source.
`create_research_run(prepared_run, runs_root, ...)` creates fresh linked threads/allowance
and imports available evidence without repeating discovery/completed uploads.
`await upload_documents(run, retry_failed=False)` performs explicit upload-only processing.

Run Python commands inside the development container. Package names changed; CLI flags
and PowerShell parameters deliberately remain unchanged.

```powershell
.\run.ps1 -FactSheet inputs/new_fact_sheet.md -DomainPlugin ML/deep_research/domain_decider/plugins/real_estate.md -Requirements inputs/requirement.md -PublicInputConfirmed
.\run.ps1 -Resume '<L2-run>'
.\run.ps1 -Research '<L2-run>' -SourceSuggestion inputs/source_suggestion.md -Online -PublicInputConfirmed
.\run.ps1 -ResumeL3 '<L3-run>' -RetryFailed
.\run.ps1 -ResearchFromL3 '<prepared-L3-run>' -Online -PublicInputConfirmed
.\run.ps1 -UploadDocumentsL3 '<L3-run>'
```

```bash
python -m ML.deep_research.domain_decider --help
python -m ML.deep_research.research_module --help
python -m ML.deep_research.research_module --resume-l3 '<L3-run>' --retry-failed
python -m ML.deep_research.research_module --check-only '<L3-run>'
```

New-run options include `--research-instruction`, `--research-config`, `--source-suggestion`
and reasoning/search controls. Resume/upload/check cannot override frozen settings.
Check-only remains observational. Schema 9, `L2_`/`L3_` prefixes, frozen keys, checkpoint
paths and thread IDs are unchanged. Unsupported historical schemas remain read-only.
Missing unfinished checkpoints require recovery, never silent restart.

## Outputs and safety

Runs stay in `runs/<parent>-<markdown-name>-<short-path-id>/`:

| Run | Visible outputs |
| --- | --- |
| `L2_*` | `asset_metadata.md`, `domain_plan.md`, `domains/*.md`, `README.md`, `run.json`, `run.log` |
| `L3_*` | `sources/*.json`, `research/*.md`, `README.md`, `run.json`, `run.log` |

Exact prompts, input bytes, completions, provider actions, usage, upload receipts and history
stay in `_internal/`. Checkpoints stay on the dedicated Linux volume. Generated run README
files are outputs and remain unchanged. Individual document failures are warnings; failed or
uncertain documents remain visible but ineligible. Successful sibling reports publish independently.
Completed empty/unconventional responses are preserved without repair. Files accepted by OpenAI
remain until manually deleted; deleting local data does not remove remote files.
Historical Layer 4 reports remain readable; no execution or replacement synthesis is included.

## Offline verification

```bash
python -m unittest discover -s tests -v
python -m compileall -q ML tests docker
python -m pip check
git diff --check
```

Tests use fake models/network responses and native checkpoints. They establish orchestration
and preservation, not live extraction accuracy, citation fidelity or research quality.
The [fixed quality benchmark](ML/deep_research/domain_decider/docs/research_context_benchmark.md)
is retained for separately authorized evaluation of metadata plus domain content together.
