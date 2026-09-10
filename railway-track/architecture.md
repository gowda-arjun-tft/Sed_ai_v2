# System Architecture

## System Overview

Current architecture and boundaries are documented in [AGENTS.md](../AGENTS.md), [README.md](../README.md)
and the [Layer 2 workflow guide](../ML/deep_research/layer2/README.md). Earlier audits and tracks
remain historical records, not the current execution contract.

## Components

Layer 2 schema 9 has three direct chat-model stages: cumulative asset metadata, one web-assisted
domain decision and original-source distribution by stable domain ID. There is no Layer 2 graph,
reviewer, custom tool loop, fact-ID projection or additional synthesis. Shared model construction
and Deep Agents configuration remain unchanged for Layers 3/4.

Operations/recovery/publication live in layer2/backend; messages, local request options/accounting
and three generic prompts live in layer2/ML. The plugin supplies baseline industry responsibilities;
requirements set priorities and the user-approved broader research scope. Python has no fixed roster.
Public entrypoints remain create_run and run_all, with explicit public-input confirmation for new runs.

Unchanged Layer 3 runs eight direct researchers plus synthesis using historical inputs; Layer 4
performs segregation, external research and synthesis. Dynamic schema-9 outputs are not integrated
with those layers. Their tools, checkpoints and settings are unchanged.

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

## External Services

The same fixed OpenAI model, selected reasoning, three transport retries and store=False remain.
The domain designer alone binds native Responses API web_search (auto). New runs freeze independently
selected low/medium/high search depth and response verbosity; both default to medium.
Provider-hosted search actions require no application agent loop or separate L3 researcher.
Metadata is tool-free Markdown. The designer requests JSON through its prompt without API format
enforcement, because web search cannot use JSON mode; tool-free distribution retains JSON-object mode.
There is no application output-token ceiling.

## Deployment

The VS Code Dev Container mounts the original checkout read-write at /app and uses
/usr/local/bin/python. It follows the checked-out branch, currently plain_research_v3.
Browser containers retain separate volume-backed state and image-backed code. No restart or
dependency change is part of this task; see the [Docker guide](../docker/README.md).

## Security

New Layer 2 runs require public_input_confirmed=True before any directory or model call.
The notebook defaults False; CLI and PowerShell require explicit confirmation. Resume uses frozen
consent. The confidential-origin requirements must be reviewed/sanitized before opt-in.
Only the designer may search, to clarify responsibilities, not to establish new supplied asset facts.
No shell, host-file tool, delegation or application-managed web fetch is introduced.

Fresh messages carry only the explicit stage inputs. Local accounting includes messages, tool and
format definitions plus framing: 300K target / 350K ceiling, bounded by model capacity; the designer
also applies the documented 128K web-search context ceiling. Provider manages hidden search turns.
Oversized mandatory input fails without truncation, automatic summary or reconciliation.

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
