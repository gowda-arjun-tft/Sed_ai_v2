# System Architecture

## System Overview

Current architecture and boundaries are documented in [AGENTS.md](../AGENTS.md), [README.md](../README.md)
and the [Layer 2](../ML/deep_research/layer2/README.md) and [Layer 3](../ML/deep_research/layer3/README.md) guides. Earlier audits and tracks
remain historical records, not the current execution contract.

## Components

Layer 2 schema 9 has three direct chat-model stages: cumulative asset metadata, one web-assisted
domain decision and original-source distribution by stable domain ID. There is no Layer 2 graph,
reviewer, custom tool loop, fact-ID projection or additional synthesis. Shared model construction
and historical Deep Agents configuration remain available for Layer 4.

Operations/recovery/publication live in layer2/backend; messages, local request options/accounting
and three generic prompts live in layer2/ML. The plugin supplies baseline industry responsibilities;
requirements set priorities and the user-approved broader research scope. Python has no fixed roster.
Public entrypoints remain create_run and run_all, with explicit public-input confirmation for new runs.

Layer 3 schema 9 runs one native source finder per actual Layer 2 domain, with five concurrent jobs,
then uploads unique source documents. New runs freeze research capability version 2 and continue into
one persistent Deep Agents 0.7.7 graph per domain sequentially, with no synthesizer. It accepts
completed schema-9 metadata/domain Markdown and editable source suggestions. Uploading remains ordinary
Python; document analysis is an explicit tool-free file-input request inside the researcher's tool loop.
An editable user research instruction determines the report objective, separately from source guidance.
Existing preparation-only and version-1 policies stay unchanged; create_research_run makes a new linked handoff.
Layer 4 retains segregation/research/synthesis on historical schema-8 research inputs only; its shared
tools/checkpoints remain unchanged, and notebook execution is disabled by default.

Railway Track stores durable authorized-work history. Claude guidance lives in CLAUDE.md and the
dated CLAUDE_HANDOVER.md; personal skills are not bundled into Docker.

## Data and Storage

Runs freeze original input bytes, three prompt snapshots/hashes, source ranges, model/input/search
policies and consent. Visible views are README.md, asset_metadata.md, domain_plan.md, domains/*.md,
run.json and run.log. Domain plan JSON requests domain_id, name and responsibilities; distribution
JSON maps the exact IDs to Markdown. No strict nested schema or content validator is applied.
The domain-plan Markdown renders usable names and responsibilities without routing IDs; raw plan JSON
remains in the existing designer response trace. No extra model call or duplicate root JSON is needed.

Raw responses, completion metadata, usage, source manifest and history remain under _internal/.
Only designer responses retain a full provider_message.json for native web actions/sources/citations
and available usage. Malformed completed JSON is still saved verbatim, not repaired. JSON duplicate
members are preserved; ambiguous/unprocessed values appear in the internal routing_issues.json with
a README warning/link. No visible unresolved.md, SQLite, evidence index, fact ledger or ownership table.

Python routes by ID and copies Markdown text in source order, without paraphrasing or semantic
deduplication. Only usable definitions reach distribution; ambiguous definitions are not guessed.
The distribution prompt prioritizes complete rules/consequences and scoped figures before compression;
its examples and combined metadata/domain evaluation contract are documented in the Layer 2 guide and benchmark.
This changes instructions, not runtime stages or demonstrated extraction accuracy.
Replaced views and diagnostics are archived before atomic per-file refresh. Interrupted publication
rebuilds from saved responses; historical schemas 2–8 cannot execute/check through the new runner.

Layer 3 freezes its three input kinds, source prompt, file mapping, hashes, consent and settings in a
sibling L3 folder. Visible source JSON files are two-space-indented hierarchical views that preserve
member order, duplicate members and values; exact model text stays internal. Malformed/empty responses
remain in the trace with README warnings, not
invented source lists. Provider messages, available search/open actions, annotations, usage and response
versions remain internal. Preparation recovery and atomic prior-view history need no SQLite.
Historical Layer 3 execution/checks reject before mutation. Output quality does not gate completion.

Fresh Layer 3 run records freeze document_uploads policy. Explicit upload-only execution can opt a
saved source-discovery run into enrichment without rerunning models. The run-scoped upload registry
stores source-response versions, URL references, SHA-256 byte identities, intents and Files receipts.
Source views add application-owned upload_status/upload/file_id; exact source claims and raw responses remain.
Provider access observations and application upload outcomes stay distinct. Research eligibility
uses only verified file IDs for documents and readable/partial access for other URLs; failed or uncertain
entries remain visible. Per-document transfer failures leave completed discovery complete with nested warnings.
Prior views are archived atomically. Temporary document bytes are removed, with no permanent copies
or global cache. Normal source-only resume without the capability never schedules uploads.

Research reports, frozen contexts, full tool/provider records, evidence and compaction archives stay
in the run. Each domain has an independent AsyncSqliteSaver database/thread in the development-only
checkpoint volume outside /app. Missing unfinished checkpoints require recovery, not silent restart.
CompositeBackend exposes read-only inputs/evidence/archive/prior routes and StateBackend private notes.
Native file permissions restrict model writes to /notes; no shell, deletion, delegation or cross-domain
paths. Native TodoListMiddleware tracks a model-authored plan without completion gates. Explicit native
summarization starts at 250K estimated tokens, retains the latest 100K where feasible and archives full
dialogue for retrieval. Final assembled input checks apply a 300K target/350K ceiling and provider capacity;
search alone retains 128K. Research version 2 shares a durable 80-logical-call ledger across main,
search, document and summarization requests. Every dispatch has an atomic reservation and ephemeral
counter; failures/uncertain responses consume slots. After 60 calls, wrap up; after 70, use saved-file
reading and finalization only. Slot 80 belongs to a tool-free main report, not a summary. Unfinished
exhaustion is partial and does not block other domains. There is no dollar or output-token cap.
Execution owns HTTP transports across domains and closes them after joined completion/cancellation.

Linked runs copy/hash matching prior evidence, cached answers, archives and reports. A disposable
read-only database/WAL copy supplies notes/plans through native DeltaChannel reconstruction, never
executing the parent graph or creating sidecars beside its database. Missing notes are disclosed.
Fresh threads and allowances retain parent usage separately; compatible caches and source references
remain reusable. The frozen user instruction stays active during compaction; prior work is evidence.

## External Services

The same fixed OpenAI model, selected reasoning, three transport retries and store=False remain.
Within Layer 2, the domain designer alone binds native Responses API web_search (auto). New runs freeze independently
selected low/medium/high search depth and response verbosity; both default to medium.
Provider-hosted search actions require no application agent loop or separate L3 researcher.
Metadata is tool-free Markdown. The designer requests JSON through its prompt without API format
enforcement, because web search cannot use JSON mode; tool-free distribution retains JSON-object mode.
There is no application output-token ceiling.

Layer 3 reuses the installed direct model builder with high reasoning, medium web-search depth and low
verbosity defaults. Each job requires the specific native web_search tool; JSON is prompt-requested,
not API-enforced. The prompt requires opening every proposed URL and distinguishes readable, partial,
explicitly blocked and failed access. Recorded claims describe provider access at that time, not a
verified Docker download capability. No content repair or automatic access grader is implemented.

The installed OpenAI Files SDK uploads user_data without expiration; files persist until manually
deleted in the same API project. Creation has no automatic SDK retry. Ambiguous acceptance is reconciled
through deterministic names, matching receipt size and streamed remote-byte hash; absent/ambiguous
results never trigger a blind duplicate create. Read-only API calls retain bounded retries. Upload
acceptance does not establish later file-input compatibility, readability or analysis. Research verifies
authorized IDs on use, enforces the separate file-input size/type boundary, and caches exact-question
answers with content/prompt/settings identities. A shared run-local async lock reuses upload machinery
for newly discovered documents; failed prepared URLs are not automatically retried. Original access
claims are unchanged. Native search actions/citations and file-reading usage are retained separately.

## Deployment

The VS Code Dev Container mounts the original checkout read-write at /app and uses
/usr/local/bin/python. It follows the checked-out branch; source-discovery work is on layer3-v1.
Browser containers retain separate volume-backed state and image-backed code. Development alone was
rebuilt/recreated after checking its kernel was idle to attach checkpoint storage; browser identity
and start time were preserved. Python dependencies were not upgraded. See the [Docker guide](../docker/README.md).

## Security

New Layer 2 and Layer 3 runs require public_input_confirmed=True before any directory or model call.
The notebook defaults False; CLI and PowerShell require explicit confirmation. Resume uses frozen
consent. The confidential-origin requirements must be reviewed/sanitized before opt-in.
Within Layer 2 only the designer may search, to clarify responsibilities, not to establish new supplied
asset facts. Layer 3 source finders receive complete frozen inputs and native web access only.
No shell, arbitrary host-file tool or delegation is introduced. The upload worker fetches only public HTTP(S)
documents with redirect/DNS checks, temporary storage, representation checks and a frozen byte ceiling.
It does not bypass login/paywalls. An OS-released file lock serializes public writers to one run.

Fresh messages carry only the explicit stage inputs. Local accounting includes messages, tool and
format definitions plus framing: 300K target / 350K ceiling, bounded by model capacity; the designer
also applies the documented 128K web-search context ceiling. Provider manages hidden search turns.
Oversized mandatory input fails without truncation, automatic summary or reconciliation.
Layer 3 applies the smaller of model capacity, application ceiling and the 128K web-search limit to
each complete domain request; an oversized job does not prevent its siblings from running.

Safe operational logs contain counts, identifiers, durations, local estimates and traceback frames
without source lines, locals, facts, queries, URLs, credentials or exception payloads. API failures
include HTTP status, bounded code/parameter/request identifiers and the recognized web-search/JSON-mode
diagnostic, not arbitrary error messages. Detailed provider
traces and usage remain internal. Check-only makes no mutations or model calls.
The existing run.log records stage counts/wall times, native dispatch and local queue/handling times,
raw-response saves, reuse, publication and total run duration. A single cancellable batch progress task
reports waiting/queued jobs every 30 seconds; it neither schedules calls nor observes hidden provider
progress. Transport-attempt counts are unavailable unless observed, separate from job attempts.

## Key Flows

Original factsheet → 50K-token windows / 5K overlap → sequential complete metadata updates →
one designer from metadata/plugin/requirements, with optional native search → settled ID definitions →
original-source distribution → Python source-order Markdown publication.

Tokenize once in preparation, seek original byte ranges in both source-reading stages. Metadata
receives neither plugin nor requirements. Distribution uses bounded native abatch_as_completed,
concurrency five and batches at most twice concurrency. Every completion saves immediately.
Fingerprints cover actual inputs/native options/frozen settings, preserving older response versions
when upstream recovery changes inputs. Completed unconventional output remains reusable.

A metadata failure stops its chain; failed or structurally unusable design stops distribution.
An unusable completed plan stays saved and is not called again for repair. Failed distribution
siblings do not block available publication. Empty/missing distribution members and unprocessed
content are observations, not quality failures or retry triggers. No preservation claim equates
routing coverage with source extraction completeness.

Completed Layer 2 → freeze metadata + actual domain files + source suggestions → bounded parallel
native source finders → immediately save completions/traces → collect exact document:true entries →
URL/byte deduplication → upload each unique document → publish enriched per-domain JSON →
capability-enabled domain researchers → independent verbatim Markdown reports. Old preparation-only
runs still stop at JSON. Linked research starts from a new frozen copy without rediscovery or re-upload.
The notebook uses an explicit resume path or L2_DYNAMIC_RUN for a blank new-run input; it never
auto-selects an older matching run. Failed jobs retry only on request; completed unusual responses
remain reusable. Local cancellation stops outstanding workers before recovery can start.
Uploads persist intent before dispatch and receipts immediately. Transfer failures preserve successful
siblings and remain separate from discovery job completion. Publication always reapplies saved mappings.
