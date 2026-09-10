# System Architecture

## System Overview

The current implemented architecture and layer boundaries are documented in [AGENTS.md](../AGENTS.md) and [README.md](../README.md).

## Components

Layer 2 schema 6 reads original evidence, designs plugin-driven domains, distributes facts and performs one paged review. Its dynamic outputs are not yet integrated with Layers 3/4. The unchanged downstream layers continue using historical inputs: Layer 3 runs eight direct domain researchers and a synthesis; Layer 4 performs segregation, external research and synthesis.
The repository-scoped Railway Track skill maintains concise durable project context for authorized meaningful changes.
Claude development guidance lives in `CLAUDE.md` and the dated `CLAUDE_HANDOVER.md` at the project
root. The user's Windows personal Claude skills contain exact Codex copies of Deep Agents Builder
and Prompt Framework; these external personal files are not bundled into the Docker environment.
Layer 2 operations live in `backend/`, while AI construction, input accounting and six generic prompts
live in `ML/`. Industry definitions belong to the selected plugin; the editable requirements template
is `inputs/requirement.md`. The public Python entrypoints are package-level `create_run` and `run_all`.
See the [Layer 2 file guide and workflow](../ML/deep_research/layer2/README.md).
Historical roster/parser/rendering ownership is in Layer 3; the obsolete planner is only a test fixture.

## Data and Storage

Run metadata, outputs, sources, usage, logs, and checkpoints are stored under local run folders as described in [README.md](../README.md).
Layer 2 freezes factsheet/plugin/requirements and prompts, preserves immutable fact bodies, stores ownership separately, and versions responses and publications. SQLite checkpoints hold read-only retrieval sessions; input fingerprints isolate changed dependent work.
Its public views are README.md, domain_plan.md, readable domains/*.md and unresolved.md when needed.
Domain research views contain responsibilities and section-grouped facts. Separate top-level means
and applicability fields, technical provenance and ownership explanations stay in internal records.
The publisher changes presentation only, without paraphrasing or deduplicating model content.
One canonical facts.jsonl ledger, definitions, assignments and input snapshots live in _internal/;
raw responses, evidence, revision history, usage and SQLite checkpoints live in _internal/trace/.
The rebuildable evidence.sqlite3 stores immutable virtual-page versions outside checkpoints; literal
search scans exact text and supports exhaustive traversal through shards. Full older message/tool groups
are archived by session before eviction. Fact bodies are streamed from the canonical ledger; active
facts and ownership use references. Publications are streamed one domain at a time.
One idle evidence connection spans stage execution without a held transaction, avoiding last-close
WAL cleanup during concurrent tool access. Native read operations have three attempts for SQLite
BUSY/PROTOCOL only, fresh query-only connections (5s busy timeout), and 0.25s/0.5s backoff. Writes,
initialization, history indexing and checkpoints are not retried by this mechanism. Safe run.log
diagnostics record context, codes, durations and traceback frames without model/error payloads.
Replaced visible Markdown is archived before refreshing. Unprocessed values are exposed, never repaired.
Historical schema-2/3/4/5 execution and checks are rejected without mutation or migration.
Railway Track current-truth records, change history, and outcome checkpoints are stored under this directory.

## External Services

The pipeline uses OpenAI models; only Layers 3/4 perform web research, through the interfaces documented in [README.md](../README.md).

## Deployment

The plain_research branch provides Docker infrastructure with pinned Linux dependencies and a
VS Code Dev Container mounting the original repository at /app. Development follows the checked-out
branch and uses /usr/local/bin/python; Layer 2 research behavior remains schema 6. Browser/CLI
containers retain separate volume-backed research state and image-backed application code.
See the [Docker guide](../docker/README.md) for branch, kernel and storage boundaries.

## Security

Secrets, URL validation, tool isolation, and model-output boundaries are governed by [AGENTS.md](../AGENTS.md).
Layer 2 new-run design is tool-free, with no evidence backend, while remaining sequential and
SQLite-checkpointed. The frozen design_tool_free setting defaults to the original tool-enabled
behavior for older schema-6 runs. Review and historical design expose only native read tools
over registered SQLite evidence via CompositeBackend, with only small StateBackend thread state,
without a host mount or model writes. Every dispatch estimates complete input against the 300K
target/350K maximum; old reviewer read bodies remain retrievable rather than summarized.

## Key Flows

Layer 2: source understanding -> domain design -> original-source distribution -> observation pages -> final catalogue -> assignment pages -> publication. Independent source jobs use native batching; reviewer pages are awaited sequentially without constraining checkpoint-internal concurrency. See [README.md](../README.md) for interfaces and the separate historical Layer 3/4 workflow.
Understanding prompts keep profiles navigational and request detailed same-subject/topic evidence
groups with fact, relationships, contradictions and supplied provenance-ID lists. Qualifications
remain in fact rather than a separate applicability field; the contract is prompt-owned and applies
through new-run snapshots. See the Layer 2 guide for the evidence-field rules. Review reports changes only;
assignment prompts request explicit ownership rows with reasons only for changed/disputed/unresolved
placements. Initial owners are supplied for comparison. Complete catalogues are inlined only when
accounted review inputs fit the normal target; otherwise finite jobs compare every required fact/proposal page with every definition page.
Source reading receives only original evidence; planning/domain review use plugin and requirements.
Distribution and final assignment use derived responsibilities. The original source is tokenized once
for its manifest, then accessed by byte-range seeks and bounded native batches (at most 2 × concurrency).
Large-roster distribution extracts once and schedules ownership-only comparisons. Planning/finalization
apply model-authored explicit updates in source order; unchanged definitions persist automatically.
New-run design receives all scheduled understanding JSON evidence, plugin, requirements and current
definitions explicitly. Large-roster reconciliation carries the corresponding current definitions
and earlier additions in bounded requests; unknown references are audited without content retries.
Checkpoint recovery is independent of tool availability. No historical run is converted automatically.
Distribution requests concise facts and useful topic labels, with qualifications inside fact rather
than separate means or applicability fields;
design/catalogue request concise duties with rationale kept separate. These changes use the existing
three stage prompts and new-run snapshots, not semantic response schemas. Schema 6 adds bounded job modes, not new agent stages.
