# Domain Decider and Research Module Architecture

This is the current architecture. Operational names and stored prefixes `L2_`/`L3_`
remain for recovery compatibility; source packages are `domain_decider` and `research_module`.
The root [README](../../../README.md) owns setup, notebook controls and recovery commands;
[Docker development](../../../docker/development.md) owns environment instructions.

## Domain Decider — original-source preparation

```text
Factsheet + selected industry plugin + user requirements
 → 50K-token original windows, 5K overlap, 45K stride
 → sequential complete asset metadata updates (Markdown)
 → one domain decision (prompt-requested JSON)
 → original-window distribution (ID-keyed Markdown in JSON)
 → source-order domain Markdown assembly
```

| Stage / prompt | Inputs and contract |
| --- | --- |
| `01_build_asset_metadata.md` | Original window + preceding complete metadata only; tool-free, no plugin/requirements; full updated metadata, not a patch |
| `02_choose_domains.md` | Complete metadata, plugin and requirements; optional native web search; IDs, names and compact responsibilities |
| `03_distribute_facts.md` | Original window, final metadata and plan; tool-free ID-keyed Markdown contributions |

Metadata identifies the subject, relationships, systems, jurisdiction and material conditions;
it is navigation, not a detailed fact inventory. Domain design retains plugin baseline duties,
extends responsibilities or adds distinct domains where justified, without a fixed count/quota.
Web evidence informs research duties, never fabricated supplied facts. Generic code/prompts
have no industry roster. The real-estate plugin and user-approved requirements permit financial,
valuation, ESG/CapEx, alternative-use and local-market research.

Source boundaries are Unicode-safe and preserve BOM/original bytes. The final window stops at
source end without a redundant tail. Metadata is sequential; distribution uses native bounded
`abatch_as_completed`, concurrency five, batching at most twice concurrency. Four windows produce
nine logical model invocations; hosted search actions and transport retries are separate.
Each call has fresh messages; there is no graph, reviewer, evidence ledger, SQLite or synthesis.

Only the designer binds native `web_search` with automatic selection. Its JSON is requested in
the prompt, not API-enforced, because JSON mode is incompatible with web search. Distribution
alone uses permissive JSON-object mode. No strict nested response validation is applied.
Actual messages/tools/options/framing count toward the 300K target/350K ceiling and provider
capacity; web design additionally respects 128K. Oversized mandatory context stops without
truncation or an added summarization stage. Three transport retries, `store=False` and no
application output-token cap remain. Preparation tokenizes the complete source once.

Distribution retains complete meanings: parties, conditions, exceptions, separate consequences,
deadlines and figures with subject/component, time, status and cost basis. It may shorten repeated
wording, not distinct meaning. Shared metadata does not replace original-source distribution.
Different parties, dates or scopes are not automatically contradictions. These are instructions,
not verified guarantees of extraction quality.

### Routing, publication and recovery

- Freeze returned domain IDs; names are labels, not routing keys. Repeated known-ID members append
  in source order. Safe filenames handle collisions and Windows-reserved names.
- Preserve duplicate JSON members and save raw completions before interpretation, including
  malformed/empty values. No alias guessing, paraphrasing, semantic deduplication or content repair.
- Unusable definitions, unknown IDs and non-text values remain in
  `_internal/trace/routing_issues.json` with a visible README warning. Nested audit values retain
  ordered member pairs. No visible `unresolved.md` is created.
- An unusable completed plan stops distribution but remains reusable without another model call.
  An absent domain/window contribution is an observation, not a coverage retry trigger.
- Visible `L2_*` files: `asset_metadata.md`, `domain_plan.md`, `domains/*.md`, `README.md`,
  `run.json`, `run.log`. Exact designer JSON stays in the existing response trace, not a root copy.
- Freeze source bytes, prompt hashes, ranges, consent and policies. Fingerprints cover actual
  dependencies/options; upstream changes preserve response history and invalidate dependents.
  Metadata/design failures stop their dependent chain; successful distribution siblings publish.
- Atomic publication archives prior view bytes. Authorized republication archives an older root
  JSON before replacing its visible view. Reuse completed responses after publication interruption.
  Provider-incomplete responses are operational failures, not completed metadata.
- Schemas 2–8 reject execution/checks without mutation. Schema 9 continues through the renamed
  runner without migration. Check-only is observational.

## Notebook handoff

One code cell preflights paths, consent, key, research config and Linux checkpoint storage, then
runs Domain Decider with `asyncio.to_thread`. Only its saved `complete` status permits research
creation from that exact directory. The Research Module async public entrypoint owns all later
scheduling. No new pipeline scheduler, model call or research loop was introduced.

Explicit actions select existing domain output (resume/reuse), research resume, new linked
research or upload-only. Blank paths create fresh runs; conflicting selections fail first.
Resume uses frozen instructions/settings, not current notebook configuration. The notebook's
fresh defaults preserve the user's consent/settings; API consent still defaults false.
Prompts, budget phases, memory, tools, checkpoint paths, schemas and model settings are unchanged.

## 1. Purpose and current scope

Research Module converts the dynamic research domains produced by Domain Decider into independently researched Markdown reports.

| Item | Current implementation |
| --- | --- |
| Branch | `layer3-v1` |
| Operational schema | Research Module schema 9 |
| Research capability | Version 3 for new runs |
| Domain count | Dynamic; inherited from Domain Decider |
| Model | `gpt-5.6-luna` |
| Final output | One Markdown research report per domain |
| Final synthesizer | None |
| Layer 4 dependency | None; supported execution ends at Research Module |

Research Module has three responsibilities:

1. Find and test relevant public sources for every Domain Decider domain.
2. Upload each unique supported document once and prepare reusable file IDs.
3. Run one persistent Deep Agent per domain to investigate its responsibilities and publish a cited report.

## 2. End-to-end flow

```text
Completed Domain Decider schema-9 run
├── asset_metadata.md
└── domains/<domain>.md (dynamic count)
            +
inputs/source_suggestion.md
inputs/user_research_instruction.md
inputs/research_config.json
            │
            ▼
1. Freeze inputs, settings, hashes, prompts and domain-file mapping
            │
            ▼
2. SOURCE DISCOVERY — up to five domains concurrently
   Each finder receives:
   asset metadata + one domain file + source guidance
            │
   Native web search → open proposed URLs → assess access
            │
            ▼
   sources/<domain>.json
            │
            ▼
3. DOCUMENT PREPARATION — sequential Python processing
   document:true URLs → safe download → SHA-256 deduplication
   → OpenAI Files upload → source JSON enrichment
            │
            ▼
4. ELIGIBILITY FILTER — deterministic Python projection
   • document: verified upload + file_id
   • webpage: readable or partial access
   • failed/blocked/uncertain sources remain recorded but excluded
            │
            ▼
5. DOMAIN RESEARCH — one domain at a time
   domain.md + asset metadata + eligible sources
   + frozen user research instruction
            │
   Plan → search/read → save evidence → revisit gaps
   → compact context when needed → final Markdown
            │
            ▼
   research/<domain>.md
            │
            ▼
END — no cross-domain synthesis stage
```

## 3. Inputs and control files

| Input | Role | Authority |
| --- | --- | --- |
| Domain Decider `asset_metadata.md` | Shared identity, location, operating context and material asset characteristics | Evidence/context |
| Domain Decider `domains/*.md` | Domain responsibilities and supplied asset facts | Evidence/context and domain scope |
| `inputs/source_suggestion.md` | Preferred source classes, jurisdictions, languages and authority priorities | User instruction for source discovery |
| `inputs/user_research_instruction.md` | Requested research objective and report presentation | User instruction for domain research |
| `inputs/research_config.json` | Per-domain logical model-call thresholds | Operational configuration |
| Public-input confirmation | Confirms that frozen inputs may be sent to public provider services | Required before new run creation |

All selected inputs are copied into the run, hashed and frozen before execution. Editing an original input later does not change an existing run or its resume behavior.

The default research instruction asks for supported risks, opportunities, corresponding actions, adjacent citations and explicit evidence gaps. It is replaceable with another objective, such as a technical or contractual assessment, without changing Python or the permanent researcher prompt.

## 4. Stage 1 — source discovery

One Source Finder job is created from each frozen Domain Decider domain file. Routing uses the frozen file mapping, not a domain name written by the model.

Each job receives only:

- The complete shared asset metadata.
- Its complete domain Markdown.
- The complete user source-suggestion Markdown.

Execution characteristics:

- Up to five source jobs run concurrently.
- Each job makes one native Responses API invocation with required `web_search` access.
- The prompt requests JSON, but the API does not enforce JSON mode alongside web search.
- The finder must search, attempt to open each proposed URL and report what was actually accessible.
- Raw responses, provider messages, actions, annotations and usage are saved before publication.
- Completed malformed or unconventional responses are preserved; no repair call is made.

Each normal source entry contains:

```json
{
  "url": "https://example.org/report.pdf",
  "description": "Why the source supports this domain.",
  "access": "partial",
  "access_note": "What was and was not readable during the attempt.",
  "document": true
}
```

Access values describe the provider's observed access at that time:

| Value | Meaning |
| --- | --- |
| `readable` | Useful content was opened successfully. |
| `partial` | Some useful content was read, but relevant material remained inaccessible. |
| `blocked` | An explicit restriction was observed. |
| `failed` | Opening failed or readability could not be established. |

A search result or snippet is not treated as proof that the source was readable. A PDF can be readable, and an HTML page can be blocked.

## 5. Stage 2 — document preparation

Document preparation is ordinary Python processing; it does not use an agent or make a model call.

Only unambiguous entries with `document: true` are candidates. The processor:

1. Validates the public URL and every redirect.
2. Streams the response into temporary storage.
3. Rejects unsafe destinations, credential-bearing URLs, HTML error/login pages, unsupported formats and oversized files.
4. Deduplicates conservative normalized URLs.
5. Calculates SHA-256 and deduplicates identical bytes across all domains in the run.
6. Uploads each unique document to the OpenAI Files API with `purpose="user_data"`.
7. Saves upload intent and receipts immediately for recovery.
8. Removes the temporary local document after processing.

The readable source view is enriched with application-owned fields:

```json
{
  "document": true,
  "upload_status": "uploaded",
  "upload": true,
  "file_id": "file-example123"
}
```

| `upload_status` | Research effect |
| --- | --- |
| `uploaded` | Eligible when a verified `file_id` exists. |
| `failed` | Retained for audit; excluded from starting research sources. |
| `uncertain` | Acceptance could not be verified; not uploaded again blindly and excluded. |
| `not_applicable` | No document upload was required. |

The model-reported `access` fields remain unchanged. Web readability, Docker download success, Files API acceptance and later document analysis are separate observations.

Upload failures are non-blocking for other documents and domains. Accepted files remain in the OpenAI project until manually deleted; deleting a local run does not delete remote files.

## 6. Stage 3 — source eligibility

Python builds the researcher's starting-source projection without interpreting research quality:

```text
Document source
└── eligible only when upload_status=uploaded and file_id is present

Webpage or unknown-format URL
└── eligible only when access=readable or access=partial

Blocked, failed, uncertain, ambiguous or unprocessed source
└── retained in records but not sent as a prepared research source
```

A domain with zero eligible prepared sources is still scheduled. Its researcher can use web search to find alternatives.

## 7. Stage 4 — persistent domain research

Research Module creates one Deep Agents 0.7.7 graph per domain. New capability-version-3 runs execute domains sequentially so one domain is completed or safely retained before the next begins.

Each researcher receives:

```text
Complete domain Markdown
+ shared asset metadata
+ eligible source JSON
+ user research instruction
```

The persistent system prompt is generic. It tells the agent to:

- Turn every domain responsibility into research questions.
- Create and maintain a research plan.
- Prefer primary and authoritative evidence.
- Read underlying evidence before making material claims.
- Preserve dates, quantities, scope, conditions, exceptions and uncertainty.
- Investigate contradictions and important gaps.
- Keep evidence and citations in durable private storage.
- Follow the frozen user research instruction for the report objective.
- Return one complete standalone Markdown report.

Coverage and completion remain model decisions. Python does not require headings, grade claims, add conclusions or resend a completed report for repair.

## 8. Research tools

| Capability | Implementation and purpose |
| --- | --- |
| `search_web` | Native OpenAI web search for new candidates and alternatives; snippets are discovery, not final evidence. |
| `read_source` | Safely fetches a public URL, extracts canonical readable text and saves it with the source reference. |
| `read_document` | Uses an authorized existing file ID or safely prepares a newly found document, then sends the actual file input with specific questions. |
| `write_todos` | Native `TodoListMiddleware` plan tracking. |
| Native file tools | `ls`, `glob`, `grep`, `read_file`, `write_file` and `edit_file` within the scoped research workspace. |

The agent has no shell, deletion or delegation tool. File writes are allowed only under `/notes/`. Cross-domain, cross-run and host-path access is unavailable.

Document answers are cached by document content hash, exact questions, prompt and model settings. Cached answers do not consume another logical model-call slot. A file ID is never treated as document content; the ID must be submitted as a real provider file input.

## 9. Memory and context management

Each domain has isolated working memory:

| Virtual path | Storage and permission |
| --- | --- |
| `/inputs/` | Frozen domain context and sources; read-only filesystem route |
| `/evidence/` | Saved web, source and document evidence; read-only to the model |
| `/archive/` | Application-owned offloaded conversation/tool history; readable |
| `/prior/` | Imported work from a linked parent run; read-only evidence |
| `/notes/` | `StateBackend`; the model's only writable area |

`CompositeBackend` isolates these routes. `AsyncSqliteSaver` stores each domain's graph state under a stable thread ID in a dedicated Docker-managed checkpoint volume outside `/app`.

Context policy:

- Main assembled-input target: 300,000 estimated tokens.
- Exceptional ceiling: 350,000 estimated tokens, also bounded by model capacity.
- Summarization begins at approximately 250,000 estimated tokens.
- The latest approximately 100,000 tokens are retained where complete tool-message groups allow.
- Older dialogue and offloaded tool results remain accessible in `/archive/`.
- Summaries are navigation aids, not replacements for preserved evidence.
- Search requests separately respect the 128,000-token web-search allowance.
- Oversized mandatory context fails visibly; it is not silently truncated.

## 10. Model-call policy

The default `inputs/research_config.json` applies per domain:

```json
{
  "maximum_calls": 80,
  "wrap_up_after": 60,
  "finalize_after": 70
}
```

The same durable counter covers main-research, web-search, document-analysis and summarization requests.

| Calls already used | Next behavior under the default policy |
| --- | --- |
| 0–59 | Normal research; an adequate early final report is accepted. |
| 60–69 | Prioritize essential gaps and prepare to finish. |
| 70–78 | Finalize from saved evidence; new network research is disabled. |
| 79 | Reserve the last invocation for a tool-free final Markdown response. |
| 80 | Make no further model call; unfinished work becomes `budget_exhausted`. |

Reservations are persisted before dispatch. Failed or uncertain dispatched calls consume their slot; cached responses, local file operations, downloads and Files API operations do not. Provider transport retries and hosted search actions are tracked separately from logical calls.

Unlimited application execution is explicit only when all three configuration values are `null`. Counting, provider/context limits, timeouts, available credit and manual cancellation still apply.

## 11. Persistence, resume and linked research

The run is file-backed and resumable:

- Every raw completion and receipt is saved immediately.
- Job fingerprints include the actual frozen dependencies and settings.
- A completed response is reused without another model call.
- Interrupted research resumes the same domain thread and call ledger.
- Missing checkpoints for unfinished work are reported; research is not silently restarted.
- Successful sibling source files and reports remain publishable after another job fails.
- One operating-system writer lock prevents simultaneous mutation of the same run directory.

Two supported creation paths exist:

| Path | Behavior |
| --- | --- |
| Full Research Module run | Source discovery → document preparation → research. |
| Linked research-only run | Creates a new run from settled complete/partial Research Module preparation without repeating discovery or completed uploads. |

A linked run copies and hashes matching prior evidence, document answers, archives, reports and available notes/plans. It creates fresh researcher threads and a fresh configured allowance. Prior work is evidence to reassess, not active instructions or automatically verified conclusions. The parent run remains unchanged.

## 12. Output structure

```text
L3_<id>/
├── README.md
├── sources/
│   └── <domain>.json
├── research/
│   └── <domain>.md
├── run.json
├── run.log
└── _internal/
    ├── inputs/
    └── trace/
        ├── document_uploads.json
        ├── source/provider responses and usage
        └── research/<domain-id>/
            ├── inputs/
            ├── evidence/
            ├── archive/
            ├── prior/
            ├── trace/
            ├── calls.json
            ├── working_state.json
            └── response.md + final.json
```

Output meaning:

- `sources/*.json` is a readable, two-space-indented view; exact source-finder text remains internal.
- `research/*.md` is the final assistant response saved verbatim for that domain.
- `run.json` is the authoritative operational record for frozen settings, hashes, states and counts.
- `run.log` contains payload-free progress, timings, call/tool counts, phase changes, safe failures and a 30-second waiting heartbeat.
- `_internal/trace/` retains evidence, provider records, usage, upload receipts and recovery history.

There is no merged portfolio report. Cross-domain synthesis is intentionally outside the current workflow.

## 13. Status and failure semantics

| Event | Behavior |
| --- | --- |
| One source finder fails | Successful source siblings are preserved; preparation is partial. |
| One document fails to download/upload | Remaining documents continue; source discovery may still be complete with upload warnings. |
| One domain has no eligible sources | Research still runs and may find alternatives. |
| A research tool cannot read a source | The limitation is saved and returned to the agent; other research continues. |
| A domain researcher fails | Its checkpoint/evidence remain; completed domain reports remain published and later domains continue. |
| Call allowance ends without a report | Domain status is `budget_exhausted`; overall research is partial. |
| A completed response is empty or unconventional | It is preserved and disclosed; no content-repair retry occurs. |
| Mandatory context exceeds limits | Operational failure; no silent truncation or summarization workaround. |

Execution completion does not prove source relevance, access accuracy, citation correctness or responsibility coverage. Those are evaluated separately against the saved evidence and report.

## 14. Security and data boundaries

- New runs require explicit confirmation that frozen inputs may be sent to public provider services.
- Secrets stay in runtime environment variables and are not written to prompts or `run.log`.
- Public URL checks reject private/local network targets, credentials and unsafe redirects.
- Evidence is treated as untrusted data and cannot override system or user instructions.
- Each domain's memory is isolated; only application-approved files and routes are exposed.
- Logs exclude prompts, source content, URLs, queries, credentials and unrestricted provider error bodies.
- No File Search, vector store, OCR service, host shell or sub-agent delegation is used.

## 15. Interfaces

| Interface | Supported action |
| --- | --- |
| Python `create_run(...)` + `await run_all(...)` | Create and execute the full Research Module workflow. |
| Python `create_research_run(...)` | Create a linked research-only run from prepared Research Module outputs. |
| Python `upload_documents(...)` | Explicit upload-only enrichment without source-finder model calls. |
| CLI | New run, linked research, explicit resume, upload-only and observational check-only actions. |
| PowerShell `run.ps1` | Windows adapter for the same Research Module actions and Docker path translation. |
| `CDI_Layer2_Layer3.ipynb` | User controls for Domain Decider input, Research Module creation/resume/upload mode, source guidance, research instruction, config, reasoning and search settings. |

### Code organization

```text
ML/deep_research/research_module/
├── __init__.py + __main__.py       Public package and CLI entrypoints
├── backend/                        Operations and recovery
│   ├── creation, validation and CLI
│   ├── source/document runners and publication
│   └── research scheduling, budgets, checkpoints and handoff
└── ML/                             Model-facing implementation
    ├── source request and Deep Agent construction
    ├── research tools, document analysis and memory middleware
    ├── providers/
    └── prompts/
```

`backend/research_runner.py` owns domain scheduling, checkpoint connections, status and publication.
`ML/domain_agent.py` owns `create_deep_agent`, model construction and middleware composition. This
keeps operational recovery separate from model behavior while preserving the package-level API.

## 16. Operational defaults

| Setting | Default |
| --- | --- |
| Source-finder reasoning | High |
| Research reasoning | Max |
| Source-discovery concurrency | 5 |
| Research-domain concurrency | 1 (sequential) |
| Web-search depth | Medium |
| Response verbosity | Low |
| Provider request timeout | 600 seconds |
| Provider transport retries | 3 |
| Research logical calls | 80 per domain |
| Wrap-up / finalization | After 60 / after 70 used calls |
| Document upload processing | Sequential |
| Download ceiling | 512,000,000 bytes |
| Direct file-input ceiling | 50,000,000 bytes |
| Application output-token cap | None |

## 17. Explicit boundaries

Research Module does not:

- Re-run or rewrite Domain Decider.
- Assume a fixed domain roster or count.
- Repair completed model content.
- Grade report headings or semantic quality in Python.
- Guarantee that every source is accessible or correct.
- Guarantee successful document extraction from an accepted upload.
- Combine reports into a synthesized final answer.
- Execute or resume historical Layer 4 workflows.

The implemented contract is therefore:

> Prepare domain-specific sources, retain recoverable evidence, run an isolated persistent researcher for every dynamic Domain Decider domain, and publish each completed Markdown report independently.

## Operational details retained from the module guides

- Supported download representations: PDF, legacy/OOXML Word/Excel/PowerPoint, RTF and
  plain text/Markdown/CSV/TSV. Uploading performs no OCR, conversion or extraction. Streaming
  temporary storage is bounded to 512,000,000 bytes; SDK multipart creation may buffer one file.
  The direct model file-input ceiling is separately 50,000,000 bytes, not an upload guarantee.
- Download retries: at most three attempts, 0.25/0.5-second backoff for transient transport,
  408/429 or server errors; each attempt uses a fresh temporary body. Read-only Files calls
  use two SDK retries; create uses none. Persist intent before create and receipt immediately.
  Reconcile uncertain acceptance through deterministic name/size and remote-byte hash.
  Missing/ambiguous receipts never authorize blind re-upload. Definitive failures retry only
  when explicitly selected. No unrelated cross-run cache is added.
- Source JSON enrichment always reapplies the run registry and preserves member order,
  duplicates, Unicode and raw model bytes. Old source-only runs opt into uploading only through
  explicit upload-only selection. Capability-enabled full runs continue automatically.
- Version-1 research retains its frozen concurrency/no-budget behavior; version 2 retains
  frozen 80/60/70 limits. Version 3 freezes exact config bytes/hash and resolved values.
  Config applies to research calls, not discovery/upload operations. Invalid config fails before
  creation. Three nulls disable budget phases/restrictions, not counting or summarization.
- Denied pending tools preserve tool-call/result ordering. Finalization permits saved-file reads;
  summaries cannot spend the final main-report slot. Early final reports are accepted verbatim.
  Input/provider failure can still prevent a report despite reserved capacity.
- Linked runs inspect disposable read-only checkpoint/WAL copies using native delta-channel
  reconstruction. Missing notes are disclosed. Parent bytes and usage remain separate; new
  threads receive fresh allowance. Client ownership spans the execution, not each domain.
- Logs are append-only UTF-8 with UTC timestamps. Stage wall time, local queue time, job elapsed
  time, dispatch-to-handled time and publication/total duration are distinct—not provider
  processing time. One cancellable 30-second observer reports queued/pending work without
  scheduling calls or claiming hidden provider progress. Handler/tasks are cleaned up.
  Safe errors include bounded HTTP/code/parameter/request IDs and traceback frames; unrestricted
  errors, source lines/locals, credentials, URLs, prompts and source payloads remain excluded.
- Exact response/usage/action records and previous operational/publication versions remain
  under `_internal/trace/`. Job attempts, logical calls and observed provider retries are
  distinct; unobserved transport retries are not inferred from job counts.

## Historical documents and evaluation index

These dated documents retain their original findings and proposals, not current runtime contracts.
Only duplicated HTML exports were removed; Markdown sources and standalone historical artifacts remain.

| Record | Historical purpose |
| --- | --- |
| [Target architecture](markdown/260908_Deep_Research_Target_Architecture_ENG.md) | Proposed 2026-09-08 architecture |
| [Domain design and fact memory](markdown/260908_Layer2_Domain_Design_And_Fact_Memory_ENG.md) | Earlier domain/evidence design |
| [Document ingestion](markdown/260908_Document_Ingestion_Design_ENG.md) | Proposed extraction and fallback strategy |
| [World-model redesign](markdown/260908_Layer3_Layer4_World_Model_Redesign_ENG.md) | Historical audit and recommendations |
| [Cost/context baseline](markdown/260908_Layer3_Cost_And_Context_Baseline_ENG.md) | Measurements and implementation at its recorded date |
| [Fixed quality benchmark](../domain_decider/docs/research_context_benchmark.md) | Source-backed retained evaluation cases; not a production validator |
| [Schema-6 audit](../domain_decider/docs/260909_Layer2_Schema6_Run_Audit_ENG.md) | Historical output audit |
| [Schema-6 verification](../domain_decider/docs/schema6_verification.md) | Historical test evidence |
| [Agent anatomy HTML](../domain_decider/docs/260909_Layer2_Agent_Anatomy_ENG.html) | Standalone historical artifact, retained |
| [Jira update](jira/SEDAI-1140_Jira_Update.md) | Dated handover pack |
| [Jira architecture](jira/SEDAI-1140_Layer_2_Architecture.md) | Earlier domain preparation attachment |

Evaluate shared metadata and domain content together: correct metadata does not cancel misleading
domain prose. Routing completeness, test passes and execution completion do not establish real-model
fact retention, source relevance, access accuracy or citation support. Live evaluation needs separate
authorization. No model calls, uploads or historical-run migrations accompany this organization change.
