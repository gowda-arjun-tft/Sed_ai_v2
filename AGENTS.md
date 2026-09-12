# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` builds cumulative subject metadata, decides plugin-driven domains once,
then distributes original facts by stable domain IDs into Markdown through three direct-call stages. Its CLI is only an adapter;
operations live in `layer2/backend/`, and AI code plus three generic prompts in `layer2/ML/`.
Use package-level `create_run` and `run_all` as public Python entrypoints; the notebook is the UI.
See `layer2/README.md` for the workflow. Industry definitions belong in the selected plugin,
not generic prompts or Python. `inputs/requirement.md` holds user objectives and the explicitly broadened research scope; review its confidential origin before public-input confirmation.
Operational events go to each run's `run.log`. `ML/deep_research/layer3/` finds and tests sources
for each actual Layer 2 domain, uploads unique documents and runs persistent domain researchers,
sequentially for new version-2 runs, producing independent Markdown reports without synthesis. `ML/deep_research/layer4/` segregates each domain report
through two tool-free calls, reuses the direct researcher for external influences, then synthesizes
the available external reports. Prompts sit below each layer; design notes are in
`ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.
Group new runs as `runs/<parent>-<markdown-name>-<short-path-id>/L2_*` and place the derived `L3_*`
beside its completed Layer 2 source. Layer 2 schema-2/3/4/5/6/7/8 artifacts are read-only. New Layer 2 runs
use schema 9 and feed Layer 3 source discovery directly; never produce a legacy missions handoff.
Layer 3 schema 9 freezes a versioned research capability for new runs; older preparation runs keep
their original behavior. Historical schema-8 Layer 3 execution/checks are read-only; Layer 4 accepts
only historical schema-8 research inputs and is disabled by default in the notebook.

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
Historical Layer 4 helper defaults remain unchanged. Do not
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
mutation. Check-only remains observational. Layer 2 schema 9 feeds Layer 3 source preparation and research;
never emit a misleading legacy missions handoff or implicitly feed Layer 4.
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

Shared historical researcher/checkpoint/memory helpers under Layer 3 remain for Layer 4. Those
researchers expose only search_web/read_source, no task/subagents or host shell. Their run-frozen
compaction retains source pointers without grading content or blocking publication. Do not alter
these helpers to implement source discovery. Layer 4 is disconnected from source-only schema 9.

Layer 3 research capability version 2 extends new full runs after preparation. Linked research-only
runs copy/hash settled complete or partial preparation; never resume/rewrite the parent. Domains
without usable sources remain scheduled. Explicit resume reuses final receipts or the same domain
checkpoint thread. Freeze research reasoning (default max), search controls and input policy.
New researchers run one domain at a time in frozen order. Freeze an editable
inputs/user_research_instruction.md for purpose/presentation; defaults request supported risks,
opportunities and corresponding actions. Keep it active through compaction. Source suggestions
govern discovery; asset/source/prior material remains evidence. Both creation APIs accept the
research_instruction keyword, with CLI/PowerShell/notebook controls; resume uses frozen bytes.
Each domain has 80 logical model invocations shared by main, search, document and summary calls.
Reserve atomically and persist before dispatch; failed/uncertain dispatches consume slots, cached
results/local files/downloads/Files operations do not. Provider transport retries and hosted search
actions remain separate. Append an ephemeral current counter to each request and count that input.
After 60 used calls, prioritize essential gaps. After 70, allow saved-file reads only; no new search,
downloads or document analysis. Summaries share the final ten but cannot use slot 80, reserved for
a tool-free main final report. Never issue call 81. Early final responses are accepted unchanged.
Exhaustion without a final response is budget_exhausted/partial, not a content-repair trigger.
Preserve tool-result ordering for denied pending calls, and continue other domains after failure.
Research owns and closes HTTP clients once per execution, not per domain. Historical version-1
runs retain frozen concurrency and no-call-budget behavior. Native recursion remains sys.maxsize;
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
payloads stay in internal traces. Notebook Layer 4 remains disabled and its shared helpers unchanged.

Layer 4 follows the same output-freedom contract. Its internal and candidate segregators and final
synthesis have no tools; its external researcher receives only `search_web` and `read_source`.
Python must not inspect segregation or research prose to decide whether another stage runs. Save
each completed response verbatim, continue after failed stages, and use fixed missing-response
markers only as downstream invocation context.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
