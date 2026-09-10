# Layer 2 V3 — stable domain routing and web-assisted design (schema 9)

Layer 2 prepares an asset overview and domain-specific research inputs through three direct model stages.
Only the domain designer can use native web search; there is no reviewer, agent graph, custom tool loop or synthesis.
Industry definitions live in the selected plugin, not Python or the generic prompts.

## Start here

1. Choose your original factsheet and industry plugin, such as [real_estate.md](plugins/real_estate.md).
2. Review [requirements](../../../inputs/requirement.md). The current user's expanded scope includes finance, valuation, ESG/CapEx and local-market research while preserving the original priorities.
3. Review **all three inputs** for public web-assisted planning. The requirements have a confidential origin; copying them into a run does not make them public. Use public or invented input only.
4. In the Layer 2 notebook cell, explicitly set `LAYER2_PUBLIC_INPUT_CONFIRMED = True` only after that review. It defaults to False; unconfirmed runs fail before creating a folder or calling a model.
5. Select paths, reasoning, web-search depth and response verbosity; use the existing [Docker environment](../../../docker/README.md). The notebook prints running/final status, run path and log path only.

The separate `L2_DYNAMIC_RUN` variable does not feed the unchanged Layer 3 cell. Do not execute one run in two environments.

## Workflow and prompt guide

```text
Original factsheet → Python: 50K windows / 5K overlap / 45K stride
       ↓
01 Build asset metadata — sequential, no tools/plugin/requirements
   window 1 → metadata v1
   previous complete metadata + next window → ... → asset_metadata.md
       ↓
02 Choose domains — metadata + complete plugin + requirements
   optional provider-hosted web search → internal raw plan JSON → domain_plan.md view
       ↓
03 Distribute original facts — original window + metadata + complete plan
   independent tool-free calls → domain-ID / Markdown contributions
       ↓
Python: source-order assembly by ID → domains/*.md
```

| Prompt | Purpose |
| --- | --- |
| [01_build_asset_metadata.md](ML/prompts/01_build_asset_metadata.md) | Return complete updated subject metadata; unchanged by schema 9 |
| [02_choose_domains.md](ML/prompts/02_choose_domains.md) | Preserve baseline duties, extend or add justified domains, return IDs/names/compact responsibilities |
| [03_distribute_facts.md](ML/prompts/03_distribute_facts.md) | Read original source again; retain facts and qualifications in ID-keyed Markdown strings |

Metadata is a navigational subject overview, not file properties or a detailed fact inventory.
It does not replace the original source in distribution. There is no fixed industry roster or
quota for new domains. Responsibilities are positive research duties, not Boundaries sections.
Web information can inform what to investigate; it must not become an invented supplied asset fact.

For 159,316 source tokens, windows are 50,000 / 50,000 / 50,000 / 24,316:
four metadata jobs, one designer job and four distribution jobs = nine logical model calls.
Native web actions and transport retries are separate; nine jobs does not mean nine billed operations.

## Minimal routing contract

Domain design requests JSON through the prompt, without API-enforced JSON mode or a strict schema.
Native web search cannot be combined with JSON mode. The requested plan remains:

```json
{"domains":[{"domain_id":"D01","name":"Domain name","responsibilities":["Research duty."]}]}
```

Tool-free distribution retains permissive API JSON-object mode and uses the same frozen IDs:

```json
{"D01":"## Relevant topic\n- Supplied facts and qualifications."}
```

Names label files; they do not route content. Repeated members for a known ID append in source order,
preserving Markdown strings exactly. Filename handling covers collisions and Windows-reserved names.
Python does not paraphrase, semantically deduplicate, strip words or grade completed content.
The distribution prompt prioritizes complete meanings before domain organization or compression: rules retain
their parties, conditions, exceptions, deadlines and separate consequences; figures retain subject/component,
period, status and cost basis. Two generic examples illustrate consequences and whole-versus-component scope.
Different parties, periods or scopes are not automatically contradictions. There is no intermediate inventory,
new call or content check; reducing genuinely repeated wording must not remove distinct qualifications.
These are prompt instructions, not verified guarantees of model extraction quality.

All raw responses are saved before interpretation, including malformed or unconventional output.
The parser preserves duplicate object members rather than silently taking the last value.
Ambiguous definitions, unknown IDs, non-text contributions and unexpected fields remain in the
internal routing audit, with references to the full raw response. Only usable ID definitions are
passed to distribution; the full raw plan remains saved unchanged. Nested objects in the audit use ordered
member-pair lists to retain duplicate keys. Usable sibling content still publishes.

A plan without usable identities stops dependent distribution but remains a completed saved response:
resume does not resend it for repair. An empty distribution object or a missing domain member is not
a factual failure. Routing coverage does not establish extraction completeness.

## Files and recovery

```text
L2_<id>/
├── README.md                Status, outputs and warning link when needed
├── asset_metadata.md
├── domain_plan.md            Domain names and research responsibilities
├── domains/<safe-domain-name>.md
├── run.json
├── run.log
└── _internal/
    ├── inputs/              Original bytes and three prompt snapshots
    └── trace/
        ├── source/manifest.json
        ├── responses/<stage>/<window>/<fingerprint>/<attempt>/
        │   ├── response.md or response.json   Exact returned text, even if malformed
        │   ├── provider_message.json          Designer web actions/sources/annotations/usage
        │   └── completion.json
        ├── routing_issues.json
        ├── history/         Previous operational run records
        ├── publications/    Rebuildable revisions including internal diagnostics
        ├── presentation_history/
        └── usage.jsonl
```

There is no visible unresolved.md, SQLite database, evidence ledger or ownership table in schema 9.
The complete raw plan stays in the designer's existing trace response.json; malformed saved text may not parse as JSON.
The root domain_plan.md renders usable names and responsibilities without routing IDs and links to that original response.
It is a Python view, not another model call or summary. No duplicate root JSON plan is created.
Only usable projections enter domain files. Internal audit details are not injected into later prompts.

Freeze original bytes, prompt snapshots, source ranges, consent and model/search/input settings.
Metadata is sequential. Distribution uses native `abatch_as_completed`, frozen concurrency five,
and batches at most twice concurrency. Every call starts fresh; only the preceding metadata is carried forward.

Reuse completed responses on resume. Fingerprints include exact message dependencies, native request
options and frozen policies. Changed upstream versions preserve history and invalidate dependent jobs.
Metadata failure stops its chain; designer failure prevents distribution; failed distribution siblings
still publish. Provider-reported incomplete text remains an operational failure, never complete metadata.

Prepare publication revisions before atomic per-file refresh, archiving previous visible bytes first.
Interrupted publication rebuilds from saved responses without calls for completed jobs. Nothing automatically
deletes response history, source snapshots or replaced views.
This presentation applies to future publications; implementation does not refresh historical runs.
A later explicitly authorized republication archives the old domain_plan.json before removing that redundant view.

## Model, privacy and input policy

Reuse the fixed model and selected reasoning, three provider transport retries and `store=False`.
Metadata has no bound tool/format. Only distribution uses native `response_format={"type":"json_object"}`.
The designer binds `web_search` with automatic selection and no output-format enforcement;
its prompt still requests JSON, saved verbatim before parsing. New runs freeze independently selected
`low`, `medium` or `high` search depth and response verbosity; both default to `medium`.
Use the installed model's native `bind`, not a strict schema helper. Do not silently fall back to a
different model or disable search if the provider rejects the request; retain an operational failure.

No application output-token cap. Account for actual messages, tools, format metadata and conservative
framing: normal target 300K estimated tokens, exceptional ceiling 350K, bounded by model capacity.
The designer also applies the documented 128K web-search context limit. Provider-hosted intermediate
search context is managed by the provider, not an application conversation we can inspect before each turn.
If mandatory input does not fit, stop safely: no truncation, automatic summarization or added reconciliation.
The tokenizer still allocates for the complete source during preparation; scale is not unlimited.

### Reading run.log

The existing append-only UTF-8 log uses UTC timestamps. Stage start/end events show expected,
completed, reused, failed and outstanding job counts, with stage wall-clock duration. Job events
show scheduling, native model dispatch, raw-response saving and reuse. Every 30 seconds while calls
are outstanding, `waiting_for_provider` lists active/pending and queued jobs with batch elapsed time;
it does not claim to observe provider reasoning or search progress. One local task observes each
bounded batch and is cancelled/joined on completion, failure or cancellation; it never schedules model work.

`queued_seconds` measures local time from prepared job to native model start. Job `elapsed` includes
that queue and response handling; `dispatch_to_handled_seconds` excludes the queue but includes local
response handling, including failure handling. Neither is pure provider processing time. Publication
has its own wall duration; final run duration and finished_at include publication. Reused jobs do not
produce a new dispatch. Job attempt numbers and configured provider transport retries are separate;
hidden transport attempts are labelled unavailable rather than inferred from job counts.

Keep the single append-only run.log free of source text, prompts, responses, queries, URLs, credentials
and unrestricted error messages. It records stages, attempts, durations, estimates, completion state,
web-action counts and safe error frames. API failures also record HTTP status, bounded diagnostic
identifiers (code, parameter and provider request ID), and a known web-search/JSON-mode incompatibility
diagnostic when that exact provider error is received; arbitrary error bodies/messages are not logged.
Full designer tool output and available citations/usage stay
in the internal provider message; existing usage.jsonl attribution remains separate from estimates.

## Interfaces and verification

```python
from ML.deep_research.layer2 import create_run, run_all
run = create_run(factsheet, plugin, requirements, runs_root,
                 reasoning_effort="high", web_search_context_size="high",
                 web_search_verbosity="medium", public_input_confirmed=True)
run_all(run)
```

CLI new runs accept `--web-search-depth` and `--web-search-verbosity` and require
`--public-input-confirmed`. PowerShell uses `-Layer2WebSearchDepth`,
`-Layer2WebSearchVerbosity` and `-PublicInputConfirmed`. Layer 2 does not require `-Online`;
that flag retains its Layer 3/4 meaning.
Resume uses frozen consent. Check-only is observational and makes no writes, log appends or model calls.
Schemas 2–8 are read-only history, unavailable for execution/check through this runner; no migration.
**Dynamic Layer 2 is not yet integrated with Layers 3/4.**

Run the existing offline unittest suite, compileall, pip check and git diff --check in Docker.
Tests cover native request serialization, consent, source windows, generic subject inputs, exact routing,
input limits, unusual outputs, safe logs, recovery and partial publication. They do not establish actual
provider acceptance, extraction completeness or useful web discovery on a live run.
Use the [fixed research-context benchmark](docs/research_context_benchmark.md) for a separately authorized
comparison. Its schema-9 baseline records observed omissions and distortions; earlier schema audits remain
historical evidence. Evaluate shared metadata plus domain content together: no mandatory duplication of common
context, but correct metadata cannot cancel misleading domain prose. New runs snapshot the revised distribution
prompt; existing runs keep their frozen instructions and outputs. No run is automatically refreshed.
