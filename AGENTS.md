# Repository Guidelines

## Project Structure & Module Organization

Current package names are `domain_decider` (formerly Layer 2) and `research_module`
(formerly Layer 3). Layer labels below describe frozen operational contracts; keep
schema 9, L2_/L3_ prefixes, metadata keys, checkpoint threads and CLI flags unchanged.
No old-package forwarding wrappers are supported. One notebook cell preflights full execution
or explicit workflow-root resume, completes domain preparation and passes that exact run to research.
Blank resume creates a numbered full run. Advanced module/linked/upload actions remain in APIs/CLI.
Resume uses frozen settings and never repeats completed domain preparation. Preserve the harness.
Current guides are README.md, ML/deep_research/docs/Research_Architecture_Overview.md
and docker/development.md. Do not recreate module READMEs; preserve generated run READMEs.

`ML/deep_research/domain_decider/` builds cumulative subject metadata, decides plugin-driven domains once,
then distributes original facts by stable domain IDs into Markdown through three direct-call stages. Its CLI is only an adapter;
operations live in `domain_decider/backend/`, and AI code plus three generic prompts in `domain_decider/ML/`.
Use package-level `create_run` and `run_all` as public Python entrypoints; the notebook is the UI.
See `README.md` for the workflow. Industry definitions belong in the selected plugin,
not generic prompts or Python. `inputs/requirement.md` holds user objectives and the explicitly broadened research scope; review its confidential origin before public-input confirmation.
Operational events go to each run's `run.log`. `ML/deep_research/research_module/` finds and tests sources
for each actual Layer 2 domain, uploads unique documents and runs persistent domain researchers,
sequentially for new version-4 runs, producing independent Markdown reports without synthesis. The supported workflow ends at Layer 3. Prompts sit below each layer; design notes are in
`ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.
Group new full workflows as `runs/<factsheet-name>/run_001/`, with `domain_decider/` and
`research_module/` phase directories, one canonical root log and one private event index.
Use the OS-locked durable counter and source-path identity; changed contents increment the same
group, while same-name/different-path inputs get readable numeric group disambiguation.
Freeze all selected inputs and both phases' prompts before model work; persist phase destinations
and use public phase runners. Preserve internal L2/L3 IDs and checkpoint threads.
Standalone module defaults retain `runs/<parent>-<markdown-name>-<short-path-id>/L2_*`, with `L3_*`
beside its completed Layer 2 source. Layer 2 schema-2/3/4/5/6/7/8 artifacts are read-only. New Layer 2 runs
use schema 9 and feed Layer 3 source discovery directly; never produce a legacy missions handoff.
Layer 3 schema 9 freezes a versioned research capability for new runs; older preparation runs keep
their original behavior. Historical schema-8 Layer 3 execution/checks are read-only. Layer 4 execution has been removed;
preserve its historical reports, inputs, traces and checkpoints without executing or migrating them.

Layer 3 mirrors Layer 2's code separation. Keep CLI, run creation, orchestration, persistence,
publication, downloads, checkpoint policy and recovery under `research_module/backend/`. Keep model-facing
request construction, Deep Agent assembly, middleware, research tools, provider adapters and all
production prompts under `research_module/ML/`. Both package roots contain public entrypoints only;
do not restore compatibility wrappers for retired internal import paths.

## Build, Test, and Development Commands

For Docker development, follow [docker/development.md](docker/development.md). Use the shared Dev Container
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
`.\run.ps1 -Research <L2-run> -SourceSuggestion <guidance.md> -Online -PublicInputConfirmed`.
Resume with `-Resume` or an explicit `-ResumeL3` path; do not auto-select a matching run.
Use `-UploadDocumentsL3 <L3-run>` or `--upload-documents <L3-run>` for upload-only enrichment.

## Coding Style & Testing

Use Python 3.11+, four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE`
constants. Prefer existing helpers and the standard library. Keep writes atomic and resumable.
No executable Python, PowerShell, or application source file may exceed 350
lines; split near 300. Prompts, skills, specifications, and documentation are exempt.

Tests use offline `unittest`. Cover changed parsing, resume, schema,
egress, citation, or publication behavior. Do not hardcode check counts.

## Agent and Security Boundaries

Keep secrets only in `.env`. The model is fixed to `gpt-5.6-luna`, with no application output-token
ceiling. Layer 2 freezes the selected reasoning. Layer 3 source discovery defaults to high reasoning,
medium native web-search depth and low verbosity; new runs freeze those controls in `run.json`.
Do not
restate model, search, token, source, or report limits in prompts.

Layer 2 schema 9 freezes original inputs, prompts, Unicode-safe source ranges, public-input consent
and model/search policies. No fixed domain count or industry roster lives in Python. Shared model,
usage/filesystem helpers and Deep Agents settings used by Layer 3 remain unchanged.

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
mutation. Check-only remains observational. Layer 2 schema 9 feeds Layer 3 source preparation and research;
never emit a misleading legacy missions handoff or schedule a downstream synthesizer.
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

Layer 3 source discovery accepts completed Layer 2 schema-9 asset_metadata.md and domains/*.md,
plus editable inputs/source_suggestion.md. Freeze all copies, prompt, hashes, consent and domain-file
mapping before calls; do not require missions, planner or original factsheet. Model names never route
outputs. Expose source_suggestion as a keyword/CLI/PowerShell input. The notebook uses L2_DYNAMIC_RUN
only when its Layer 2 path is blank, explicit resume, high/medium/low controls and fresh consent False.

Use one native Responses invocation per domain with specific required web_search tool choice, no
JSON mode, graph, custom tool loop, separate verifier or consolidation during source discovery.
Prompt-requested source JSON includes URL, relevance, observed access/note and document true/false/null.
Attempt every proposed URL; snippets/citations are not proof of readability. Never claim a failed
open proves a paywall or that OpenAI readability proves Docker download access.

Use native abatch_as_completed in bounded batches with concurrency five. Save raw text before
parsing, full provider messages/actions/annotations and usage, then publish valid JSON as readable,
two-space-indented views in sources/<frozen-domain-stem>.json. Preserve member order, duplicate members
and unconventional JSON values; keep exact raw model text internally and link malformed
or empty responses in README, and keep execution status separate from usefulness/access coverage.
Reuse completed responses, retry operational failures only when requested, and preserve successful
siblings. Source discovery itself uses file fingerprints/history, not SQLite or conversation memory.
Account for actual messages/tools/options/framing against the smaller of model capacity, application
ceiling and 128K search allowance. Oversized jobs fail independently; no truncation or summarization.
Reuse safe run.log helpers for progress, timings, action counts and payload-free errors.

Fresh Layer 3 runs freeze document_uploads policy and continue to a sequential Python upload step.
Older schema-9 source-only runs gain uploads only through explicit upload-only selection; normal
resume retains their original behavior. Notebook LAYER3_UPLOAD_ONLY requires an explicit resume path.
Keep discovery status separate from transfer status. Require frozen public-input consent and runtime
authentication. Uploading itself makes no model calls and creates no File Search, vector store or OCR pipeline.

Collect exact document:true and unambiguous URLs from preserved completed responses. Deduplicate
URLs conservatively and temporary downloaded bytes by SHA-256 across this run and its resumptions.
Validate public destinations and redirects, reject credentials, HTML impostors and unsupported/oversized
documents. Temporary byte storage is deleted on close; no permanent downloads or cross-run cache.
Files use purpose=user_data, with no automatic expiration. Uploaded files remain until manually deleted;
local run deletion does not delete remote storage. Upload success is not proof of readability/analysis.

Persist intent before Files create, disable create retries, and save receipts immediately in the one
_internal/trace/document_uploads.json registry. Reconcile uncertain uploads through exact remote receipt
and byte hash; never blindly resend them. Definitive rejections/download failures retry only explicitly.
Reuse verified IDs and preserve unavailable/uncertain states with diagnostics. One OS-released run writer
lock protects public discovery/upload entrypoints. Preserve successful siblings on transfer failure.

Source publication adds only trusted upload_status/upload/file_id fields. Preserve provider access
claims, original fields, duplicate members and immutable raw responses. Use documents later only when
uploaded with a file ID; use ordinary/unknown-format URLs only when access is readable or partial.
Blocked, failed, uncertain and unprocessed entries remain visible but ineligible. Per-document transfer
failures do not make otherwise-complete source discovery partial; expose nested upload warnings instead.
Keep ambiguity/failures in the registry with a README link. Atomic publication/history applies to
enrichment too; rebuilding must not erase upload mappings or reuse unprocessed source versions.

Layer 3 research capability version 4 extends new full runs after preparation. Linked research-only
runs copy/hash settled complete or partial preparation; never resume/rewrite the parent. Domains
without usable sources remain scheduled. Explicit resume reuses final receipts or the same domain
checkpoint thread. Freeze research reasoning (default max), search controls and input policy.
New researchers run one domain at a time in frozen order. Freeze an editable
inputs/user_research_instruction.md for purpose/presentation; defaults request supported risks,
opportunities and corresponding actions. Keep it active through compaction. Source suggestions
govern discovery; asset/source/prior material remains evidence. Both creation APIs accept the
research_instruction keyword, with CLI/PowerShell/notebook controls; resume uses frozen bytes.
Freeze inputs/research_config.json separately from the report objective, with research_config,
--research-config, -ResearchConfig and LAYER3_RESEARCH_CONFIG_PATH controls for new runs only.
Read once, hash exact bytes and freeze resolved values. Require exactly maximum_calls,
wrap_up_after and finalize_after: three integers with 0 <= wrap < finalize < maximum, or three nulls.
Reject missing/duplicate/unknown keys, wrong types and unreadable files before creating a run.
Default per-domain limits are 80/60/70, shared by main, search, document and summary calls.
Reserve atomically and persist before dispatch; failed/uncertain dispatches consume slots, cached
results/local files/downloads/Files operations do not. Provider transport retries and hosted search
actions remain separate. Append an ephemeral current counter to each request and count that input.
At configured wrap-up, prioritize essential gaps; at finalization, allow saved-file reads only,
without new search, downloads or document analysis. Summaries share the reserve but cannot consume
the last slot, reserved for a tool-free main report. Never exceed the configured ceiling.
Three nulls disable budget-driven phases/tool restrictions/exhaustion, not accounting or summarization.
Remaining allowance is null and displayed as unlimited. Early final responses are accepted unchanged.
Exhaustion without a final response is budget_exhausted/partial, not a content-repair trigger.
Preserve tool-result ordering for denied pending calls, and continue other domains after failure.
Research owns and closes HTTP clients once per execution, not per domain. Historical version-1
runs retain frozen concurrency and no-call-budget behavior. Historical version-2 runs retain frozen
80/60/70 limits without reading the new config. New linked runs freeze the selected config with fresh
allowances; resumes never reset them. Native recursion remains sys.maxsize;
keep request/input/provider limits, manual cancellation and three transport retries, without a dollar
or output-token cap. Logs/README/notebook expose used/remaining calls and phases.
New linked runs copy/hash matching prior evidence, answers, archives and reports; export notes/plans
from disposable read-only checkpoint copies using native delta-channel reconstruction. Missing notes
are disclosed. Preserve parent bytes and source references, reuse compatible caches, create fresh
threads/allowances and record parent usage separately. Prior findings are evidence to reassess,
not verified conclusions or active instructions. No model calls occur during run creation.

Use one create_deep_agent graph per domain with native todos and file tools. Expose search_web,
read_source and read_document, but no shell, deletion or delegation. CompositeBackend scopes frozen
inputs/evidence/archives to this domain; only StateBackend /notes/ is model-writable. Native explicit
research summarization starts at 250K estimated tokens and retains the latest 100K where tool groups
permit; archives must remain readable. Count final assembled instructions/messages/tools again before
dispatch against 300K target/350K ceiling and model capacity; search retains 128K. No silent input
truncation, implicit overflow repair or completed-content retry. Coverage remains prompt-owned.

read_document authorizes registered IDs per domain, or safely uploads a newly discovered document
URL under one run-local registry lock. Reuse URL/content hashes and immediate receipts. Never blindly
repeat uncertain upload POSTs or automatically retry failed prepared URLs. Submit verified IDs as
actual file inputs, preserve answers/usage/references and cache exact questions/settings. Upload and
file-input format/size limits differ; file-ID text cannot measure document tokens. Failed documents
return limitations without stopping other research. Source access observations remain unchanged.

Persist one AsyncSqliteSaver database per domain on the dedicated Docker Linux volume identified by
SEDAI_RESEARCH_CHECKPOINT_DIR, outside /app. Validate before paid phases; no Windows-mounted fallback.
Missing unfinished checkpoints require recovery, never silent fresh execution. Reports/evidence/raw
responses remain project-local. No model-authored auxiliary file or heading is a completion gate.
Save final assistant Markdown verbatim and publish each sibling independently with presentation history.
Log safe timings, observed model/tool activity, checkpoints, compaction and a single 30-second heartbeat;
payloads stay in internal traces. The notebook contains one full-workflow/resume execution cell.

## Workflow-strengthening policy (fresh runs)

Industry plugins live in `inputs/plugins/`; the default real-estate plugin provides external
asset-linked responsibilities, not cross-agent communication. Risk/opportunity/action format and
external reassessment belong in the editable user instruction, within the existing research loop.
Preserve user requirements and confidential-origin warnings. Frozen source guidance also remains
in the researcher's persistent system context through compaction. Search/open exact URLs;
record proposed-URL versus available explicit-open evidence observationally, without altering
access claims, statuses or retry behavior. An open action alone is not proof of readability.

One notebook STAGE_SETTINGS dictionary controls metadata, design, distribution, source_discovery,
research, research_search, document and summary. Full-workflow defaults: high reasoning except
medium summary; medium verbosity except low discovery/search; medium search context where applicable.
Keep supported levels including max selectable. Separate summary/document settings use shared
execution-owned clients and call accounting. Keyword stage_settings overrides corresponding legacy
API arguments; --stage-settings/-StageSettings JSON adapters reject mixed legacy generation flags
and creation-setting overrides on resume/check/upload-only. Freeze resolved values and include
options in request accounting/fingerprints. Historical policies without stage settings are unchanged.
New provider requests use reasoning.summary=auto unless disabled; retain returned summaries
privately and separately from report text. Never claim hidden chain-of-thought is available or
silently drop rejected provider options. Domain schema9 keeps a versioned stage-settings policy;
research capability4 freezes settings, persistent source guidance and webpage allowance. Versions
1/2/3 retain original behavior, including config, counters, threads and prompts.

New webpage reads enforce declared/actual 52,428,800-byte limits (50 MiB); historical fallback
remains 10 MiB. Keep document-upload and model-file limits separate, public-address checks and
safe redirects. Encode Unicode components without changing existing escapes/queries. Exact-URL
search merging preserves order and fills missing title/snippet values only from real later records.
Expose restrictions/missing endpoints/encoding/size/extraction failures honestly. The agent may
search for an authoritative exact alternative by title/publisher/topic; no Python search loop,
access bypass, crawler or OCR is added.

Extend existing callbacks and saver boundaries, not a new monitoring/middleware framework.
Private append-only events correlate workflow, request, logical reservation, tool and checkpoint
IDs with timestamps, settings, usage, durations and artifact references. Capture todo/note proposals
and native applied writes, file/archive results, selected/retained compaction messages, summary,
archive hash and next dispatch context. Preserve the native algorithm/thresholds; no extra checkpoints.
Operational logs stay payload-free; private traces require research-data access protection and
must not expose credentials. Record only observed provider action order/timing. Todo completion is
not verified coverage. Keep existing cancellable heartbeats; never simulate provider thinking.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
