# Layer 3 — Source preparation and persistent domain research

New Layer 3 runs prepare sources and continue into one persistent researcher per domain.
Each researcher writes one Markdown report. There is no final synthesizer or Layer 4 invocation.
Older runs without the versioned `research` capability retain their preparation-only behavior.
New runs use operational schema 9; historical schema-8 research runs remain read-only through Layer 3.

```text
Completed Layer 2 schema-9 run
  asset_metadata.md + each domains/*.md
                 +
  inputs/source_suggestion.md
                 ↓
Source finders — up to five concurrent native calls
  Search → attempt to open every proposed URL → assess access
                 ↓
Unique document URLs → temporary bytes → SHA-256 deduplication → OpenAI Files upload
                 ↓
One enriched sources/<domain-file-stem>.json per domain
                 ↓
Independent Deep Agents — one domain at a time (research capability version 2)
  + frozen inputs/user_research_instruction.md
Plan → search/read → save findings → investigate gaps → research/<domain>.md
```

## Edit and run

- Edit `inputs/source_suggestion.md` for preferred sources. Its initial guidance prioritizes relevant
  local, regional and national authorities, regulators, official statistics and primary company
  publications, while allowing necessary reputable secondary coverage. No fixed source/domain count.
- Edit `inputs/user_research_instruction.md` for the desired report. The default asks for supported
  risks and opportunities with corresponding actions, adjacent citations and honest evidence gaps.
  Replace it with a technical assessment or another objective without changing Python. Its frozen
  copy remains active through compaction; asset/source/prior material is evidence, not instructions.
- In the notebook's Layer 3 cell, choose a completed Layer 2 run or leave its path blank to use
  `L2_DYNAMIC_RUN`. Set source guidance, reasoning, search depth and verbosity.
- Review all input for public disclosure before setting `PUBLIC_INPUT_CONFIRMED = True`.
  Creation APIs default confirmation to False; the notebook preserves the user's existing selection.
  Preparation defaults are high reasoning, medium search depth,
  low verbosity and five concurrent jobs; the model remains `gpt-5.6-luna`.
- Resume only the explicitly supplied `LAYER3_RESUME_RUN_PATH`. Frozen consent/settings apply;
  set `LAYER3_RETRY_FAILED = True` only to retry operational failures. Completed empty or malformed
  responses are reused, not repaired. Frozen-input changes require a fresh run.
- New runs automatically upload after discovery. For a saved source-only run, set
  `LAYER3_UPLOAD_ONLY = True` and provide `LAYER3_RESUME_RUN_PATH`: no source finder is called.
  Historical schema-9 runs without this capability remain source-only on ordinary resume.
- To research existing preparation without repeating discovery or uploads, set
  `LAYER3_PREPARED_RUN_PATH` to its settled complete/partial run. This creates a **new linked run**;
  the parent stays unchanged. Clear the resume path and leave upload-only False. Domains without
  usable sources still run. Research reasoning defaults to `max`; source-finder reasoning is separate.
  Matching prior evidence, document answers, archives, reports and available checkpoint notes/plans
  are copied and hashed. New threads start a fresh allowance; parent usage is recorded separately.
  This is reuse of prior work under a new objective, not continuation of the old checkpoint.
- Resuming research uses its explicit new run path and its own checkpoint threads. Once research
  starts, preparation is frozen; resume never reruns it. To change preparation, create another run.
- Layer 4 is disabled by default in the notebook. It can still run explicitly on historical
  schema-8 research inputs; these new source lists are not such inputs.

```powershell
.\run.ps1 -Research '<completed-L2-run>' -SourceSuggestion '.\inputs\source_suggestion.md' -Online -PublicInputConfirmed
.\run.ps1 -ResumeL3 '<explicit-L3-run>' -RetryFailed
.\run.ps1 -UploadDocumentsL3 '<explicit-L3-run>'
python -m ML.deep_research.layer3 --upload-documents '<L3-source-run>'
python -m ML.deep_research.layer3 --check-only '<L3-source-run>'
python -m ML.deep_research.layer3 --research-from '<prepared-L3-run>' --online --public-input-confirmed
.\run.ps1 -ResearchFromL3 '<prepared-L3-run>' -Online -PublicInputConfirmed
```

Python: `create_run(l2_run, runs_dir, source_suggestion=..., public_input_confirmed=True,
reasoning_effort="high", web_search_context_size="medium", web_search_verbosity="low")`, then
`await run_all(run_dir)`. `runs_dir` remains accepted; the new run is placed beside its Layer 2 source.
CLI also exposes `--source-suggestion`, `--reasoning-effort`, `--web-search-depth` and
`--web-search-verbosity` for new runs.
Python also exports `await upload_documents(run_dir, retry_failed=False)` for explicit upload-only work.
`create_research_run(prepared_run, runs_dir, public_input_confirmed=True,
research_reasoning_effort="max")` creates the linked research-only run; call `await run_all(new_run)`.
Full creation also accepts `research_reasoning_effort`. CLI exposes `--research-reasoning-effort`.
Both creation APIs accept `research_instruction=Path(...)`; CLI uses `--research-instruction`,
PowerShell uses `-ResearchInstruction`, and the notebook uses `LAYER3_RESEARCH_INSTRUCTION_PATH`.
These are new-run inputs; resume always uses the frozen copy. Source suggestions remain separate.
Conflicting linked/resume/upload actions are rejected before run creation.

## Outputs and meaning

```text
L3_<id>/
  README.md                 Status, output links and warnings
  sources/<domain>.json     Readable model source JSON plus application-owned upload status/file ID
  research/<domain>.md      Final assistant Markdown, verbatim; no synthesis
  run.json                  Frozen file mapping/settings and job state
  run.log                   Progress, timings and safe errors
  _internal/
    inputs/                 Exact Markdown and prompt snapshots
    trace/                  Raw responses, provider messages, usage and history
      document_uploads.json URL/hash mappings, upload intents, receipts and failure reasons
```

The prompt requests `domain` and a `sources` list. Published views use two-space indentation while
the exact raw model text remains in `_internal/trace`; formatting preserves member order, duplicate
members and values without grading or repairing them. Each source has `url`, `description`, `access`,
`access_note` and `document` (true, false or null). Output routing uses frozen input-file identities,
not model-written names. JSON duplicate members and unconventional values remain unchanged.
Malformed or empty text is retained internally and linked from README, never replaced by a fake
successful empty list. Failed siblings do not block successful outputs.

| Access | Observed through the provider at the time of the attempt |
| --- | --- |
| readable | Useful content was successfully read. |
| partial | Useful content was read, but relevant material was inaccessible. |
| blocked | An explicit access restriction was observed. |
| failed | Opening failed or could not establish readability. |

Search snippets/citations alone do not establish readability. PDFs may be readable, HTML may be
blocked, and an uncertain format is null. Results describe OpenAI access, not our Docker downloader.
The application preserves provider search/open actions, annotations and usage in `provider_message.json`;
it does not infer that every URL was tested from a tool-call count. Access accuracy and relevance need
a separately authorized live evaluation. Upload status does not change these model-reported access claims.

## Document uploads and recovery

Only unambiguous `document: true` source entries are download candidates. Ordinary webpages,
unknown document types and unusable entries are not guessed into documents. Source fields remain
unchanged; `upload_status`, `upload` and `file_id` are application-owned fields in the derived view:

```json
{"document": true, "upload_status": "uploaded", "upload": true, "file_id": "file-example123"}
```

Definitive failures use `upload_status: "failed"`; ambiguous acceptance uses `"uncertain"`; and
ordinary webpages use `"not_applicable"`. All three receive `upload: false` and `file_id: null`.
Other source fields, extra values and duplicate members remain represented; exact raw model bytes are never rewritten.
Ambiguous/unprocessed material is recorded in the registry and linked from README, without repair calls.

Research may use a prepared document only when its upload status is `uploaded` and it has a file ID.
Non-document or unknown-format URLs may be used only when provider access is `readable` or `partial`.
Blocked, failed, uncertain and unprocessed entries stay visible but are excluded. A domain with no
prepared usable source is still scheduled for web research.

One sequential worker deduplicates normalized URLs (retaining path/query meaning), then downloaded
SHA-256 hashes. All domains in the run reuse the same accepted file ID for identical bytes. Linked
research inherits only its parent's receipts; no unrelated cross-run/global cache is introduced.
Temporary byte files are closed and removed after processing;
the registry, timestamps, response-version pointers and receipts remain. Byte downloads are streamed;
the installed SDK may buffer an individual file during multipart preparation.

Public HTTP(S) destinations and every redirect pass the existing DNS/public-address checks.
No login, paywall bypass or source credentials are used. HTML/error pages, unsupported formats and
oversized downloads remain failures, not successful uploads. Supported representations are PDF,
Word/Excel/PowerPoint (legacy or OOXML), RTF and plain-text/Markdown/CSV/TSV documents. No conversion,
OCR or content extraction is performed. The frozen ceiling is 512,000,000 bytes, within the Files API
512 MB limit. Download attempts are at most three, with 0.25/0.5-second backoff for transient transport,
408/429 or server failures; each uses a fresh empty temporary body. Files API reads use two SDK retries.

The installed SDK sends `purpose="user_data"`, with no expiration. Files remain in the same OpenAI
project until manually deleted; deleting a local run does not delete remote files. Use the registry
to identify files for a separately authorized cleanup. API upload acceptance is not readability,
analysis or a searchable index. Later direct model inputs have separate type/context limits and the
documented 50 MB aggregate request limit. See [Files API](https://developers.openai.com/api/reference/python/resources/files/methods/create)
and [file inputs](https://developers.openai.com/api/docs/guides/file-inputs).

Every upload intent is saved before its single create request; successful IDs are saved immediately.
File creation disables SDK automatic retries. A timeout, interruption or uncertain response is
reconciled by deterministic filename/size and a remote-byte hash before reusing its ID. Missing,
ambiguous or mismatching candidates stay uncertain, including when retry is requested: no blind
re-upload. Saved IDs are checked on resume. Missing/inaccessible IDs remain unavailable rather than
silently uploading another copy. Definitively rejected uploads and failed downloads can retry with
the existing explicit retry control. This is conservative recovery, not an exactly-once network guarantee.

One OS-released writer lock protects public execution/upload entrypoints. Do not run one research
directory from two environments. Registry-backed publication is rebuildable without model calls;
previous JSON views are archived before enrichment. Discovery job status stays separate from upload
status. Individual transfer failures do not make completed discovery or research partial; the
nested upload status, README and notebook expose the warnings. Discovery failures still make the run partial.

## Runtime and code guide

- `pipeline/create_run.py`: input validation, schema/consent checks, snapshots and dynamic mapping.
- `source_finder.py` and `prompts/source_finder.md`: native request and prompt, complete input accounting,
  fingerprints and durable raw completions. Prompt-requested JSON only; no API JSON-mode binding.
- `source_runner.py`: bounded native `abatch_as_completed`, immediate saves, cancellation and resume.
- `source_publication.py`: readable JSON views, warnings and prior-view history; exact responses stay internal.
- `document_uploads.py`, `document_files.py`, `document_download.py`, `document_records.py`:
  upload orchestration/registry, Files recovery, safe temporary downloads and source enrichment.
- `cli.py`, `runner.py`, `pipeline/run_checks.py`: thin public execution/check entrypoints.

During source discovery only native provider-hosted `web_search` is bound, with specific required tool choice. The provider
may search/open/find within one logical invocation; there is no application tool loop, Deep Agents
graph, SQLite or conversation memory in this preparation stage. Legacy researcher/checkpoint helpers
remain solely for Layer 4 and its historical tests; the new research harness is separate.

## Persistent researcher

`domain_research.py` builds Deep Agents 0.7.7 graphs and native async batches; `research_run.py`
owns linked handoffs, frozen settings and checkpoint preflight. `research_memory.py` provides
domain-private native file tools, explicit compaction, final input accounting and full traces.
`research_budget.py` owns durable logical-call reservations; `research_handoff.py` imports prior work.
`domain_tools.py` and `research_documents.py` reuse source safety, Files receipts and native Responses
requests. Prompts are `domain_research.md`, `research_summary.md` and `read_document.md`.

Each graph gets complete domain Markdown, shared asset metadata and eligible source JSON.
Native `write_todos` tracks the model-authored plan. `search_web` finds candidates; `read_source`
retains canonical source text; `read_document` verifies an authorized file ID or safely prepares a
new alternative document URL and submits an actual file input with specific questions. Previously
failed prepared URLs are not automatically retried. Failed/unavailable/uncertain documents are tool
limitations, not reasons to cancel other domains. New uploads share one run-local async registry lock.
Exact-question document answers are cached by content hash, prompt and settings in private evidence.
Upload deduplication spans domains; evidence/answer visibility does not cross domain boundaries.

The model can read `/inputs/`, `/evidence/`, `/archive/`, `/prior/` and write/edit only `/notes/`. Notes use
StateBackend; immutable inputs/evidence and application-owned archives use scoped CompositeBackend
routes. Shell, deletion, delegation and cross-run/host access are unavailable. Instructions embedded
in evidence are untrusted. The native summarizer retains original dialogue in accessible archives;
summaries are navigation, not factual replacements. No auxiliary-file or semantic completion gate exists.

Main research input target/ceiling is 300K/350K estimated tokens, with compaction starting at 250K
and the latest 100K retained where complete tool-message groups permit. The exact assembled request
is counted again after middleware, including tool definitions and framing. Search requests use 128K;
provider capacity can reduce allowances. Unfit mandatory requests fail operationally without silent
truncation. File bytes/tokens are not estimated from a file ID; the separate 50 MB file-input limit
and provider context failures remain explicit. No File Search, vector store or OCR is introduced.

Research capability **version 2** runs domains sequentially and permits **80 logical model calls per
domain**, shared by main research, web-search requests, document analysis and summarization. Atomic
reservations in each domain's `calls.json` survive failure, cancellation and resume. A failed or
uncertain dispatched request consumes its slot; cached results, files, downloads and Files API
operations do not. Provider retries and hosted search actions are separate, so this is not an
80-HTTP-request or dollar limit. All requests carry a current counter included in input accounting,
without accumulating counter messages in checkpoint history.

| Already used | Next-call behavior |
| --- | --- |
| 0–59 | Research normally; accept an early final response. |
| 60–69 | Prioritize essential gaps and prepare to finish. |
| 70–78 | Finalize from saved evidence; only native read-only file tools remain. Summaries share the reserve. |
| 79 | Tool-free main-model request for the final Markdown; no summary can consume this slot. |
| 80 | No further model calls. Without a final response, mark the domain `budget_exhausted` and research partial. |

Pending tools denied by a phase transition return an operational limitation with their original
tool-call ID. Unfit mandatory final context still fails safely; the reserve cannot guarantee a
successful report if a provider or input failure occurs. Successful siblings publish and later
domains continue. No repeated reports, quality grading or content-repair calls are introduced.
The log, README and notebook show used/remaining calls and phases. Request timeouts, input limits,
manual cancellation and `sys.maxsize` graph recursion remain; there is no output-token or dollar cap.
Historical capability-version-1 runs keep their frozen five-domain/no-call-budget policy and prompts.

Research execution owns its HTTP transports and closes them after all domains finish or cancellation
is joined; a completed domain does not close the next domain's client. Linked creation reads a
disposable copy of the parent's SQLite database and committed WAL, using native delta-channel state
reconstruction without executing a graph. Parent storage is never opened for writes. Missing notes
are disclosed; available evidence remains reusable. Prior findings are not automatically verified.

Each domain has its own AsyncSqliteSaver database and stable thread in the dedicated Docker volume
configured by `SEDAI_RESEARCH_CHECKPOINT_DIR`. Storage is validated **before any paid phase**; it
cannot fall back to `/app` or Windows SQLite. Missing checkpoints for unfinished work require explicit
recovery, not a silent restart. Reports, input snapshots, evidence and full traces remain in the project.
Checkpoints may grow with retained message state; this is not constant-size memory. See the Docker guide
for mount setup, persistence and deletion consequences. Only the development service configuration changes.

Completed reports publish immediately, independently of failed siblings. An interrupted run retains
completed reports and checkpoints. Resume joins the same domain thread, while publication recovery
can reuse a final-response receipt even if the previous view write failed. Logs contain domain IDs,
observed model/tool counts, elapsed timings, compaction/checkpoint activity and a 30-second waiting
heartbeat—not prompts, URLs, questions, evidence or credentials. Search/document usage remains separately
attributed in each domain's internal evidence; main/compaction usage is in its trace `usage.jsonl`.

Before every source-finder dispatch, count complete messages, native tool/options and framing. Use the
smaller of model capacity, application ceiling and the 128K web-search allowance. Oversized jobs fail
independently without truncation. Three provider transport retries and no application output cap remain.

`run.log` records local scheduling/handling times, waiting messages every 30 seconds, reuse,
available action counts and safe traceback frames. It excludes URLs, queries, content and credentials.
Provider-internal retry counts are not inferred. Raw completions and version history support rebuilding
publication without model calls; execution status is separate from source-list usefulness.

## Verification

Use the shared Docker Dev Container and `/usr/local/bin/python` as described in `docker/README.md`.
Run `python -m unittest discover -s tests -v`, `python -m compileall -q ML tests` and `python -m pip check`.
Offline fakes cover orchestration, preservation, access instructions and request serialization, not
real-world source accuracy or improved risks/opportunities/actions. No live source-finder or research
run is part of implementation verification. See the [version-2 implementation record](../../../railway-track/tracks/2026-09-11-layer3-directed-research.md).
