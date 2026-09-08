# System Architecture

## System Overview

The current implemented architecture and layer boundaries are documented in [AGENTS.md](../AGENTS.md) and [README.md](../README.md).

## Components

Layer 2 schema 4 reads original evidence, designs plugin-driven domains, distributes facts and performs one paged review. Its dynamic outputs are not yet integrated with Layers 3/4. The unchanged downstream layers continue using historical inputs: Layer 3 runs eight direct domain researchers and a synthesis; Layer 4 performs segregation, external research and synthesis.
The repository-scoped Railway Track skill maintains concise durable project context for authorized meaningful changes.
Layer 2 operations live in `backend/`, while AI construction, input accounting and six generic prompts
live in `ML/`. Industry definitions belong to the selected plugin; the editable requirements template
is `inputs/requirement.md`. The public Python entrypoints are package-level `create_run` and `run_all`.
See the [Layer 2 file guide and workflow](../ML/deep_research/layer2/README.md).
Historical roster/parser/rendering ownership is in Layer 3; the obsolete planner is only a test fixture.

## Data and Storage

Run metadata, outputs, sources, usage, logs, and checkpoints are stored under local run folders as described in [README.md](../README.md).
Layer 2 freezes factsheet/plugin/requirements and prompts, preserves immutable fact bodies, stores ownership separately, and versions responses and publications. SQLite checkpoints hold read-only retrieval sessions; input fingerprints isolate changed dependent work.
Railway Track current-truth records, change history, and outcome checkpoints are stored under this directory.

## External Services

The pipeline uses OpenAI models; only Layers 3/4 perform web research, through the interfaces documented in [README.md](../README.md).

## Deployment

Not established.

## Security

Secrets, URL validation, tool isolation, and model-output boundaries are governed by [AGENTS.md](../AGENTS.md).
Layer 2 design/review exposes only native read tools over seeded StateBackend files, without a host mount or model writes. Every dispatch estimates complete input against the 200K target/250K maximum; old read bodies remain retrievable rather than summarized.

## Key Flows

Layer 2: source understanding -> domain design -> original-source distribution -> observation pages -> final catalogue -> assignment pages -> publication. Independent source jobs use native batching; reviewer pages are awaited sequentially without constraining checkpoint-internal concurrency. See [README.md](../README.md) for interfaces and the separate historical Layer 3/4 workflow.
