# SEDAI-1140 — Jira update pack

## Recommended summary

Build configurable Layer 2 domain routing for multiple research verticals

## Parent

SEDAI-1139 — Deep research module

## Recommended status

Development complete / Ready for review

The implementation and offline verification are complete in the current checkout. Move to the
team's final Done status after the required commit, review or merge step for this repository.

## Description — copy into Jira

Build Layer 2 as an industry-neutral evidence-routing engine. A selected Markdown plugin defines
the vertical and baseline research responsibilities; a requirements file supplies the user's
objectives, priorities and exclusions. Layer 2 reads the original factsheet, creates or extends
domains for the actual subject, assigns every recorded fact to all relevant domains, performs one
bounded review, and publishes compact domain Markdown for downstream research.

The implementation supports dynamic responsibilities and additional subject-specific
domains/subdomains without a fixed domain count in Python. The supplied real-estate plugin contains
the current baseline domains. Other verticals, such as insurance or defence, require their own
plugin file and use the same Layer 2 machinery.

Layer 2 preserves original facts, applicability, uncertainty and contradictions. It does not
perform web research, risk scoring, valuation or recommendations.

## Scope delivered

- Three frozen inputs: factsheet, domain plugin and research requirements.
- Six-stage flow: read facts, choose domains, sort facts, review domains, finalize domains and
  assign facts.
- Dynamic responsibility extension and evidence-supported domain/subdomain creation.
- Original-source distribution with multi-domain ownership and temporary Extra handling.
- One finite reviewer pass over every recorded fact, not only unassigned facts.
- Compact responsibilities-and-facts Markdown for each final domain.
- Visible unresolved/unprocessed material without inventing ownership.
- Run logging, usage attribution, immutable inputs, raw responses, checkpoints and safe resume.
- Scalable paging, indexed evidence retrieval and complete definition-page comparisons.
- 60K source windows, 10K original-source overlap and concurrency five.
- 300K normal assembled-input target and 350K exceptional ceiling.
- Model-output freedom: no semantic grading, repair prompt or content-driven retry.

## Suggested subtasks

### 1. Define configurable Layer 2 inputs — Done

Accept and freeze factsheet, vertical plugin and user requirements. Keep industry definitions out
of generic prompts and Python.

### 2. Build scalable source preparation — Done

Create Unicode-safe 60K/10K source windows, record exact boundaries and load source ranges
incrementally during execution.

### 3. Implement source-only fact understanding — Done

Read each original source window without plugin or requirement bias; retain entities,
relationships, quantities, applicability, uncertainty and contradictions.

### 4. Implement dynamic domain design — Done

Start from the selected plugin, apply user priorities, extend responsibilities and add justified
subject-specific domains/subdomains with recorded reasons.

### 5. Implement fact distribution and ownership — Done

Extract original facts once, assign all relevant domains, retain temporary Extra, and separate
fact bodies from ownership decisions.

### 6. Implement bounded domain review — Done

Review every fact and initial owner once, finalize domain definitions, disposition proposed
changes and assign final owners across all required definition pages.

### 7. Implement persistence and human-readable publication — Done

Save raw responses, immutable facts, indexed evidence, session history, usage and checkpoints;
publish compact domain Markdown plus an unresolved-material audit.

### 8. Verify recovery and large-input operation — Done

Test stage contracts, concurrency, resume, output preservation, Windows long paths and synthetic
1M/3M/10M-token execution with network access blocked.

## Acceptance criteria

- [x] Layer 2 accepts factsheet, plugin and requirements as independent Markdown inputs.
- [x] Generic prompts and Python contain no fixed industry roster or fixed domain count.
- [x] The plugin supplies baseline responsibilities; the model may extend them or add justified
  domains from requirements and evidence.
- [x] Read facts receives only original source content.
- [x] Every recorded fact enters review and final ownership processing.
- [x] Facts may be owned by multiple domains; missing/unusable ownership remains visible.
- [x] Original fact bodies and raw completed model objects are preserved without semantic repair.
- [x] Large inputs use bounded jobs, indexed evidence and finite definition-page comparisons.
- [x] Input accounting applies to initial and tool-follow-up calls.
- [x] Operational failures preserve available sibling output and support checkpoint resume.
- [x] Final domain files contain research responsibilities and grouped facts without internal IDs
  or byte-offset metadata.
- [x] Layer 2 performs no web research, risk scoring or recommendations.
- [x] Historical Layer 2 runs remain unchanged and read-only.

## Test coverage — copy into Jira

133 offline tests passed. Coverage includes input freezing, exact source windows and overlap,
Unicode preservation, dynamic plugins, domain additions, multi-domain ownership, complete reviewer
page coverage, bounded native concurrency, immediate saves, same-thread checkpoint recovery,
read-only tool isolation, exact archived history, unconventional model output, partial publication,
atomic replacement and Windows long paths. Compilation, dependency checks, notebook compilation,
PowerShell parsing, docstrings, file-length rules and diff whitespace checks passed.

Synthetic native-graph scale tests completed at 1M, 3M and 10M source tokens with HTTP blocked.
The fresh 10M run completed 407 jobs in 190.394 seconds with 420.3 MiB peak execution memory;
preparation peaked at 1,024.3 MiB because the installed tokenizer allocates for the whole source.
This verifies orchestration, not real-model extraction completeness.

## Completion comment — copy into Jira

Layer 2 dynamic domain routing is implemented and offline-verified. The engine now uses a selected
vertical plugin plus user requirements to create/extend research domains, routes original source
facts with multi-domain ownership, reviews all recorded facts, and publishes compact domain-ready
Markdown. Persistence, recovery, indexed evidence retrieval, bounded input handling and visible
unresolved material are included. The full offline suite passed (133 tests), including a synthetic
10M-token operational exercise. No live model or web calls were used for implementation testing.

Current boundary: the real-estate plugin is supplied. Additional verticals require their own
plugin Markdown. Schema-6 dynamic output is not yet connected to Layer 3/4; that integration should
be tracked separately.

## Recommended labels

- `deep-research`
- `layer-2`
- `dynamic-domains`
- `configuration`
- `evidence-routing`

## Recommended attachments

1. `SEDAI-1140_Layer_2_Architecture.md` — compact implementation architecture.
2. `schema6_verification.md` — detailed offline tests and scale measurements.
3. `layer2/README.md` — operator workflow, files and execution boundaries.

Do not attach a customer requirements file or generated research run unless its confidentiality
and sharing scope have been approved.

## Follow-up work item

**Suggested title:** Connect Layer 2 dynamic domains to Layer 3/4 research orchestration

Schema-6 Layer 2 intentionally does not emit the historical fixed-domain handoff consumed by the
current Layer 3/4 pipeline. Track dynamic researcher creation, downstream prompt routing and
cross-layer resume compatibility separately.
