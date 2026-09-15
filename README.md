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
defaults to `False`. Confirm only after reviewing/sanitizing the inputs.

## Organization

```text
ML/deep_research/
├── domain_decider/
│   ├── __init__.py + __main__.py
│   ├── backend/       Execution, persistence, publication, CLI
│   ├── ML/prompts/    Three direct-call prompts and model helpers
│   └── docs/          Audits and fixed quality benchmark
├── research_module/
│   ├── __init__.py + __main__.py
│   ├── backend/       Preparation, uploads, budgets, recovery
│   └── ML/            Agent, tools, middleware, providers/, prompts/
├── workflow.py        Thin full-run coordinator
└── docs/              Current architecture and historical evidence
inputs/plugins/real_estate.md  Editable industry responsibilities
```

The [architecture overview](ML/deep_research/docs/Research_Architecture_Overview.md)
describes all stages, limits, memory, source eligibility and recovery, with a historical
document index. [AGENTS.md](AGENTS.md) defines working rules;
[Railway Track](railway-track/change.md) records changes. There are no old-package wrappers,
new shared-runtime package or installable wheel. The core agent graph and pinned dependencies are retained.

## One notebook execution cell

Open [CDI_Layer2_Layer3.ipynb](CDI_Layer2_Layer3.ipynb). Preserve unsaved editor changes before
reloading it; restart only an idle kernel to clear old imports. The filename and Docker kernel
are unchanged. Historical output is not attached to the new cell.

| Input/control | Meaning |
| --- | --- |
| `FACT_SHEETS_DIR` | Folder of top-level Markdown factsheets, processed alphabetically one at a time |
| `DOMAIN_PLUGIN`, `REQUIREMENTS_PATH` | Industry duties and user objectives |
| `SOURCE_SUGGESTION_PATH` | Authority, jurisdiction and source preferences |
| `RESEARCH_INSTRUCTION_PATH` | Editable report objective, including external reassessment |
| `RESEARCH_CONFIG_PATH` | Per-domain call thresholds: 80/60/70 or three explicit nulls |
| `STAGE_SETTINGS` | Independent reasoning, verbosity and applicable search context |
| `REASONING_SUMMARIES` | Request provider-supported summaries; default true |
| `RESEARCH_FACTSHEET_ACCESS` | Original-source access for researchers; current notebook selection false, new runs only |
| `PUBLIC_INPUT_CONFIRMED` | Explicit consent; default false |
| `RESUME_RUN_PATH` | One full numbered run root; blank creates fresh runs for every selected factsheet |
| `RETRY_FAILED` | Explicit operational retry during resume; default false |

The notebook supports **sequential folder execution or one explicit root resume**. Set
`FACT_SHEETS_DIR = Path("inputs/facts")`; the top-level `.md` files are selected once in
alphabetical order, without recursion. Missing folders/empty selections fail before work.
Each file completes its Domain Decider and Research Module before the next starts, using
the same controls and its own existing numbered run group. Ordinary failures/partial results
do not stop later files; cancellation stops the queue. The final notebook summary lists
outcomes, report locations and individual resume paths; no batch record is written.
A blank resume always starts fresh runs for every selected file, even after an interrupted
batch. Explicit resume ignores the folder and resumes only its selected workflow.
Linked research,
standalone phase execution and upload-only remain advanced APIs/CLI actions below.
Resume ignores current creation controls and uses frozen bytes, settings, counters and
checkpoint identities. Completed full-run resume makes no model calls. A fresh invocation
freezes both phases' inputs/prompts before its first model request and passes the exact
completed domain run into research. Domain failure stops the handoff; document failures
remain non-blocking warnings. Reports stay independent per domain.

Cancellation during synchronous domain preparation waits for that phase's worker to exit before
releasing the workflow lock; it does not start research. Python cannot safely kill that thread.
Research-phase cancellation uses the existing native graph cleanup and checkpoints.

| Stage key | Reasoning | Search context | Verbosity |
| --- | --- | --- | --- |
| metadata | high | — | medium |
| design | high | medium | medium |
| distribution | high | — | medium |
| source_discovery | high | medium | low |
| research | high | via search tool | medium |
| research_search | high | medium | low |
| document | high | — | medium |
| summary | medium | — | medium |

Reasoning accepts low/medium/high/max. Verbosity and search context accept low/medium/high.
Search context controls context size, not a promised number of searches. Supporting document,
search and summary requests retain their own task instructions and share the existing domain
call counter. Provider summaries are saved privately, separate from report text; hidden
chain-of-thought is neither available nor logged. A provider rejection remains an operational
failure, never silently retried with summary settings removed.

The JSON call config requires three integers with
`0 <= wrap_up_after < finalize_after < maximum_calls`, or three explicit nulls.
Unlimited removes the application call ceiling, not provider limits, timeouts or spending.

## Public APIs and recovery commands

```python
from ML.deep_research.workflow import create_run as create_full_run, run_all as run_full
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

All creation APIs accept keyword-only `stage_settings`; explicit stage values override legacy
arguments. Module creators also accept `destination` for coordinator-owned directories.
Without it, standalone module storage remains compatible. Full-run execution is
`full = create_full_run(factsheet, public_input_confirmed=True, ...)`, then `await run_full(full)`.

Run Python commands inside the development container. Package names changed; CLI flags
and PowerShell parameters deliberately remain unchanged.

```powershell
.\run.ps1 -FactSheet inputs/new_fact_sheet.md -DomainPlugin inputs/plugins/real_estate.md -Requirements inputs/requirement.md -PublicInputConfirmed
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

CLI `--stage-settings <settings.json>` and PowerShell `-StageSettings` accept the same dictionary
(with optional `reasoning_summaries`). Do not mix them with legacy generation flags or use them
on resume/check/upload-only actions. PowerShell translates this path for Docker research.

New-run options include `--research-instruction`, `--research-config`, `--source-suggestion`
and reasoning/search controls. Resume/upload/check cannot override frozen settings.
Check-only remains observational. Schema 9, `L2_`/`L3_` prefixes, frozen keys, checkpoint
paths and thread IDs are unchanged. Unsupported historical schemas remain read-only.
Missing unfinished checkpoints require recovery, never silent restart.

## Outputs and safety

Full runs now use:
```text
runs/<factsheet-name>/run_001/
  README.md · run.json · run.log
  domain_decider/
  research_module/
  _internal/inputs/ · _internal/trace/events.jsonl
```

The same source path keeps its group when contents change. Different paths with the same
name get readable numeric group suffixes. An OS-locked durable counter reserves increasing
run numbers; abandoned reservations can leave gaps. Do not delete/edit the counter registry.
Friendly folder names do not replace internal L2/L3 identities. Historical folders are not migrated.

Standalone module APIs retain `runs/<parent>-<markdown-name>-<short-path-id>/` and these views:

| Run | Visible outputs |
| --- | --- |
| `L2_*` | `asset_metadata.md`, `domain_plan.md`, `domains/*.md`, `README.md`, `run.json`, `run.log` |
| `L3_*` | `sources/*.json`, `research/*.md`, `README.md`, `run.json`, `run.log` |

Exact prompts, input bytes, completions, provider actions, usage, upload receipts and history
stay in `_internal/`. Checkpoints stay on the dedicated Linux volume. Generated run README
files are outputs. Unified phase README log links point to the one parent operational log. Individual document failures are warnings; failed or
uncertain documents remain visible but ineligible. Successful sibling reports publish independently.
Completed empty/unconventional responses are preserved without repair. Files accepted by OpenAI
remain until manually deleted; deleting local data does not remove remote files.
Historical Layer 4 reports remain readable; no execution or replacement synthesis is included.

## Evidence and observability

New research capability **5** keeps a verified, byte-identical factsheet snapshot when
available from the selected Domain Decider and access is enabled. Each domain can search/read it through the
existing read-only `/inputs/fact_sheet.md` route; only an availability notice is in the
persistent prompt, not the whole source. Native file access remains available after
compaction and during finalization. The source describes what was supplied, not independently
verified reality. Access can resolve an uncertain clause but cannot guarantee detection of omissions.

New linked runs prefer their parent's frozen source, otherwise only its recorded Domain
Decider snapshot. Missing historical source locations are disclosed; missing/corrupt bytes
with a recorded hash are errors. The current editable input is never substituted. Existing
capability 1–4 resumes retain their frozen behavior, prompts and checkpoints.

Set `RESEARCH_FACTSHEET_ACCESS = False` to disable original-source access for new researchers.
The full-workflow and both research creation APIs accept `research_factsheet_access=True`.
The Boolean is frozen at creation; explicit resume ignores the current notebook toggle and
shows the saved availability (`available`, `unavailable` or `disabled`). Disabled runs do not
copy/project the original into researcher inputs, including linked runs. Domain Decider still
uses the factsheet; derived facts and prior evidence are not redacted. No new tool or repair stage.

The distribution prompt preserves relationship direction and scoped estimates. Generic research
instructions require source, arithmetic and citation checks; risk-specific protections,
financial assumptions and allocation checks remain in `inputs/user_research_instruction.md`.
The [fixed benchmark](ML/deep_research/domain_decider/docs/research_context_benchmark.md) scores
preparation and final-report fidelity separately.

The real-estate plugin expands asset-specific external duties without requiring communication
between isolated agents. The editable research instruction asks for preliminary findings,
external drivers, exposure, safeguards/counterevidence and refined consequences/actions within
the same loop. Requirements and their confidential origin remain unchanged.

Frozen source guidance stays in the researcher's persistent instruction context through
compaction. Exact source URLs must be opened; snippets/index listings are not readability
proof. Per-response `access_audit.json` compares entries to available explicit opens without
changing claims, completion status or retry behavior.

Capability-v4 and later research fetches webpages with a 50 MiB (52,428,800 byte) bound on headers
and actual bytes. Upload and file-input limits remain separate. Unicode components are encoded
without guessing paths. Failed reads return operational distinctions; the agent can search
for the exact title/publisher and open an authoritative alternative. No bypass or crawler exists.

`run.log` contains safe identifiers, counts and durations. Protected internal traces retain
effective inputs/options, provider summaries, ordered web actions, todo/note changes,
tool/file reads, compaction inputs/retained messages/archive hashes, actual next contexts,
checkpoint receipts and final/publication receipts. The append-only event index correlates
these with domain threads and logical calls. Todos are model plans, not verified coverage.
Provider-internal timings/retries are reported only when available, never invented.
Archives remain retrievable; thresholds and the persistent Deep Agents graph are unchanged.

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
