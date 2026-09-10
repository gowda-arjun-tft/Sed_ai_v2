# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` builds cumulative subject metadata, decides plugin-driven domains once,
then distributes original facts by stable domain IDs into Markdown through three direct-call stages. Its CLI is only an adapter;
operations live in `layer2/backend/`, and AI code plus three generic prompts in `layer2/ML/`.
Use package-level `create_run` and `run_all` as public Python entrypoints; the notebook is the UI.
See `layer2/README.md` for the workflow. Industry definitions belong in the selected plugin,
not generic prompts or Python. `inputs/requirement.md` holds user objectives and the explicitly broadened research scope; review its confidential origin before public-input confirmation.
Operational events go to each run's `run.log`. `ML/deep_research/layer3/` runs eight direct domain researchers
sequentially, then one property synthesis. `ML/deep_research/layer4/` segregates each domain report
through two tool-free calls, reuses the direct researcher for external influences, then synthesizes
the available external reports. Prompts sit below each layer; design notes are in
`ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.
Group new runs as `runs/<parent>-<markdown-name>-<short-path-id>/L2_*` and place the derived `L3_*`
beside its historical Layer 2 source. Layer 2 schema-2/3/4/5/6/7/8 artifacts are read-only. New Layer 2 runs
use schema 9, not yet integrated with Layers 3/4; do not produce a legacy missions handoff.

## Build, Test, and Development Commands

For Docker development, follow [docker/README.md](docker/README.md). Use the shared Dev Container
and `/usr/local/bin/python` for offline checks; preserve the Docker workflow and do not restart browser research.
Do not run the same research job from two environments. After branch switches, finish active work
before restarting the notebook kernel.

The original Windows workflow uses the `compute` interpreter:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

Run Layer 2 with `.\run.ps1 -FactSheet <facts.md> -DomainPlugin <plugin.md> -Requirements <requirements.md> -PublicInputConfirmed` and Layer 3 with
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
ceiling. Layer 2 freezes the selected reasoning. Layer 3 defaults to low model and web-search proxy
reasoning and low web-search context and verbosity; new runs may select supported levels and
freeze those controls in `run.json`. Do not
restate model, search, token, source, or report limits in prompts.

Layer 2 schema 9 freezes original inputs, prompts, Unicode-safe source ranges, public-input consent
and model/search policies. No fixed domain count or industry roster lives in Python. Shared model,
usage/filesystem helpers and Deep Agents settings used by Layers 3/4 remain unchanged.

Keep three direct-call stages, without a graph, reviewer or additional synthesis. Metadata receives
only each original window and preceding complete metadata; no plugin, requirements or tools.
Decide domains once from complete metadata, plugin and requirements. Only that call may use native
provider-hosted web_search (auto), to clarify missing research responsibilities. New runs freeze
independently selected low/medium/high search depth and response verbosity; both default to medium.
Preserve baseline duties, extend them or add distinct domains when warranted; no fixed quota.
Web evidence informs duties, never fabricated subject facts. Metadata remains Markdown.

Designer JSON is prompt-requested only: never bind response_format or text.format alongside web_search.
Plan JSON contains domains with domain_id, name and compact responsibilities. No Boundaries or
strict nested schema. Distribution reads original windows plus complete metadata/plan and returns
ID-keyed Markdown strings using native JSON-object mode. No tools there. Native bind passes
response_format directly; never introduce strict Pydantic validation or a custom tool loop.
Public-input confirmation is required before creating a run; notebook defaults False, CLI exposes
--public-input-confirmed and PowerShell uses -PublicInputConfirmed. Resume uses frozen consent.

Use 50K-token windows, 5K original-source overlap and 45K stride; preserve Unicode/BOM source bytes
and stop at source end without redundant tail. Metadata is sequential; distribution uses bounded
native abatch_as_completed at frozen concurrency five. Source-order assembly, not completion order.
Count actual messages, tool definitions, format metadata and framing: 300K target / 350K ceiling,
bounded by model capacity; designer also respects 128K native web-search context limit. Provider
manages its hidden search turns. Unfit mandatory context stops safely without truncation or added
summarization/reconciliation. Keep three provider transport retries and no application output cap.

Save raw completions before parsing, including malformed/empty/unconventional text. Freeze IDs from
the saved plan. Parse JSON object members without losing duplicates; append repeated contributions
for a known ID, preserve ambiguous definitions/unknown IDs/unprocessed values internally. No alias
guessing, paraphrasing, semantic deduplication or keyword stripping. A structurally unusable plan
blocks dependent distribution but remains saved and reusable, not a prompt-repair trigger.
Other unusual output or absent domain/window members do not cause coverage failures or retries.

Visible outputs: README.md, asset_metadata.md, domain_plan.md, domains/*.md, run.json and run.log.
Render the domain plan's names/responsibilities from saved definitions; keep exact JSON in the existing
designer response trace, not a duplicate root file. Archive older views before an authorized republication.
No visible unresolved.md; full routing observations stay in _internal/trace/routing_issues.json
with a README warning/link. Keep designer native web actions, sources, annotations and usage in its
provider_message.json, never in run.log. Log counts/identifiers/durations and safe frames; API errors
may include HTTP status, bounded diagnostic identifiers and recognized diagnostics, never arbitrary payloads.
Log stage/job progress, reuse, queue/handling times, publication and total wall duration. One cancellable
30-second progress task observes pending/queued calls without scheduling work or claiming model progress.
Provider-internal retry attempts remain unavailable unless observed; never infer them from job attempts.
Keep model usage separate from local input estimates. No new SQLite, fact ledger or ownership table.

Reuse completed raw responses on resume, recover missing/operationally failed jobs only, and
fingerprint actual dependencies and native options. Preserve response and publication history.
Metadata/design failure stops dependent work; successful distribution siblings still publish.
Archive old view bytes before atomic refresh. Historical schemas 2–8 reject execution/check before
mutation. Check-only remains observational. Schema 9 is not integrated with Layers 3/4; never emit
a misleading legacy missions handoff or change those layers/cells without separate authorization.
Preserve distinct research-driving facts with scope, conditions, actors, exceptions and dates.
Concision may remove genuinely repeated wording, not unique meaning. Metadata does not substitute
for original-source distribution; routing coverage is not proof of complete extraction.

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

Each Layer 3 domain researcher receives only `search_web` and `read_source`; it has no `task` tool or
subagents, and synthesis has no tools. Python schedules one researcher at a time, saves each final
assistant response verbatim, then synthesizes every available response. Prompts own research,
contradiction mapping, source checking, and corrections. Python may
enforce network safety, persistence, attribution, and atomic publication, but must not grade
Markdown, require auxiliary model-written files, or trigger content-repair calls. Implicit
framework summarization and tool-call repair middleware stay disabled. A run-frozen CDI
summarizer may compact only the direct domain researcher; it must retain source pointers,
must not grade content, and must not block publication. Never add
keyword-based research policy, host shell, `run_python`, cross-property memory, or model-writable
host folders without explicit approval.

Layer 4 follows the same output-freedom contract. Its internal and candidate segregators and final
synthesis have no tools; its external researcher receives only `search_web` and `read_source`.
Python must not inspect segregation or research prose to decide whether another stage runs. Save
each completed response verbatim, continue after failed stages, and use fixed missing-response
markers only as downstream invocation context.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
