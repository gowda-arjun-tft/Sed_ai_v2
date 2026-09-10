# System Architecture

## System Overview

The current implemented architecture and layer boundaries are documented in [AGENTS.md](../AGENTS.md) and [README.md](../README.md).

## Components

Layer 2 schema 7 extracts evidence once, designs plugin-driven domains, assigns fact IDs and performs one paged correction review. Its dynamic outputs are not yet integrated with Layers 3/4. The unchanged downstream layers continue using historical inputs: Layer 3 runs eight direct domain researchers and a synthesis; Layer 4 performs segregation, external research and synthesis.
The repository-scoped Railway Track skill maintains concise durable project context for authorized meaningful changes.
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
Understanding retrieval uses raw-response pages and indexed ledger facts, without a duplicate
understanding projection. Tool-free planning skips retrieval snapshots; current definitions are
indexed when review starts. Unchanged-domain assignment stages skip indexing, retaining audits.
One idle evidence connection spans stage execution without a held transaction, avoiding last-close
WAL cleanup during concurrent tool access. Native read operations have three attempts for SQLite
BUSY/PROTOCOL only, fresh query-only connections (5s busy timeout), and 0.25s/0.5s backoff. Writes,
initialization, history indexing and checkpoints are not retried by this mechanism. Safe run.log
diagnostics record context, codes, durations and traceback frames without model/error payloads.
Replaced visible Markdown is archived before refreshing. Unprocessed values are exposed, never repaired.
Historical schema-2/3/4/5/6 execution and checks are rejected without mutation or migration.
Railway Track current-truth records, change history, and outcome checkpoints are stored under this directory.

## External Services

The pipeline uses OpenAI models; only Layers 3/4 perform web research, through the interfaces documented in [README.md](../README.md).

## Deployment

Not established.

## Security

Secrets, URL validation, tool isolation, and model-output boundaries are governed by [AGENTS.md](../AGENTS.md).
Layer 2 new-run design is tool-free, with no evidence backend, while remaining sequential and
SQLite-checkpointed. Historical designer capability branches are removed. Review exposes only native read tools
over registered SQLite evidence via CompositeBackend, with only small StateBackend thread state,
without a host mount or model writes. Every dispatch estimates complete input against the 300K
target/350K maximum; old reviewer read bodies remain retrievable rather than summarized.

## Key Flows

Layer 2: source understanding -> immutable evidence IDs -> domain design -> initial ID assignment -> correction review -> accepted domain changes -> scoped ownership updates -> publication. Independent reading/assignment jobs use native batching; reviewer pages are awaited sequentially without constraining checkpoint-internal concurrency. See [README.md](../README.md) for interfaces and the separate historical Layer 3/4 workflow.
Understanding prompts keep profiles navigational and request detailed same-subject/topic evidence
groups with fact, relationships, contradictions and supplied provenance-ID lists. Qualifications
remain in fact rather than a separate applicability field; the contract is prompt-owned and applies
through new-run snapshots. See the Layer 2 guide for the evidence-field rules.
prompts retain rules with exceptions/actors, distinguish comparable contradictions from scoped differences,
and separate independently useful topics. Ownership requires a specific supported responsibility;
review retrieval is need-driven without reducing scheduled coverage. The fixed manual benchmark is
outside the production pipeline, and real-model quality gains remain unverified.
Review reports changes only; assignment prompts request explicit ownership rows with reasons only for changed/disputed/unresolved
placements. Initial owners are supplied for comparison. Complete catalogues are inlined only when
accounted review inputs fit the normal target; otherwise finite jobs compare every required fact/proposal page with every definition page.
Source reading receives only original evidence; planning/domain review use plugin and requirements.
Distribution and final assignment use derived responsibilities. The original source is tokenized once
for its manifest, then accessed by byte-range seeks and bounded native batches (at most 2 × concurrency).
Extraction happens only during understanding. Large rosters use preserved evidence for ownership-only comparisons. Planning/finalization
apply model-authored explicit updates in source order; unchanged definitions persist automatically.
New-run design receives all scheduled labelled understanding evidence, plugin, requirements and current
definitions explicitly. Large-roster reconciliation carries the corresponding current definitions
and earlier additions in bounded requests; unknown references are audited without content retries.
Checkpoint recovery is independent of tool availability. No historical run is converted automatically.
Application fact IDs include run, source job, saved response content version and entry position.
Raw bodies and historical generations remain unchanged; active evidence is ordered by source.
One ownership mapping drives final domain JSON membership and clean Markdown, with no duplicate bodies.
Compact inputs retain labelled facts/relationships/contradictions and supplemental values; source
bookkeeping stays internal. Dispatch and token accounting use the same text, without an escaped evidence dump.
Reviewer add/remove operations carry unchanged ownership forward and expose conflicts. No proposals means
no finalization call. Accepted new/changed responsibilities trigger one all-evidence pass only for those
scopes. Missing decisions cannot remove owners; partial positive matches remain publishable with coverage
warnings. All assigned entries appear in Markdown without another selection, rewrite or source extraction.
