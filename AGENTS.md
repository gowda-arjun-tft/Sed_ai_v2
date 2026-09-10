# Repository Guidelines

## Project Structure & Module Organization

`ML/deep_research/layer2/` extracts original evidence once, designs plugin-driven domains,
assigns stable fact IDs and performs one paged correction review. Its CLI is only an adapter;
operations live in `layer2/backend/`, and AI code plus six generic prompts in `layer2/ML/`.
Use package-level `create_run` and `run_all` as public Python entrypoints; the notebook is the UI.
See `layer2/README.md` for the workflow. Industry definitions belong in the selected plugin,
not generic prompts or Python. `inputs/requirement.md` is a user-editable placeholder template.
Operational events go to each run's `run.log`. `ML/deep_research/layer3/` runs eight direct domain researchers
sequentially, then one property synthesis. `ML/deep_research/layer4/` segregates each domain report
through two tool-free calls, reuses the direct researcher for external influences, then synthesizes
the available external reports. Prompts sit below each layer; design notes are in
`ML/deep_research/docs/`; tests are in `tests/`.
Generated runs, secrets, caches, sources, and checkpoints stay local.
Group new runs as `runs/<parent>-<markdown-name>-<short-path-id>/L2_*` and place the derived `L3_*`
beside its historical Layer 2 source. Layer 2 schema-2/3/4/5/6 artifacts are read-only. New Layer 2 runs
use schema 7, not yet integrated with Layers 3/4; do not produce a legacy missions handoff.

## Build, Test, and Development Commands

Use the `compute` interpreter:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip install -r requirements.txt
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
```

Run Layer 2 with `.\run.ps1 -FactSheet <facts.md> -DomainPlugin <plugin.md> -Requirements <requirements.md>` and Layer 3 with
`.\run.ps1 -Research <L2-run> -Online -PublicInputConfirmed`. Resume with `-Resume` or `-ResumeL3`.

## Coding Style & Testing

Use Python 3.11+, four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE`
constants. Prefer existing helpers and the standard library. Keep writes atomic and resumable.
No executable Python, PowerShell, or application source file may exceed 350
lines; split near 300. Prompts, skills, specifications, and documentation are exempt.

Tests use offline `unittest`. Cover changed parsing, resume, schema,
egress, citation, or publication behavior. Do not hardcode check counts.

## Agent and Security Boundaries

Keep secrets only in `.env`. The model is fixed to `gpt-5.6-luna`, with no application output-token
ceiling. Layer 2 freezes the selected reasoning. Layer 3 defaults to low model and web-search proxy
reasoning and low web-search context and verbosity; new runs may select supported levels and
freeze those controls in `run.json`. Do not
restate model, search, token, source, or report limits in prompts.

Layer 2 schema 7 freezes factsheet, ordinary Markdown plugin, user requirements and prompts.
The engine has no fixed domain count or real-estate-specific routing logic. Historical roster and
input helpers live in Layer 3 settings and `legacy_input.py`; the old planner is a test fixture.
Do not reintroduce them into Layer 2. Preserve shared model and operational helper behavior.
Nominal source windows remain 60K tokens, 10K original-source overlap and 50K stride; record actual
Unicode-safe boundaries without losing source characters. Source understanding and distribution
are tool-free, using native abatch_as_completed with frozen concurrency five by default.
Do not add a second semaphore/task scheduler. Review phases/pages run sequentially once.

Choose domains has no tools or evidence backend;
it receives every understanding evidence page as labelled text, plugin, requirements and current definitions explicitly.
Keep it sequential and checkpointed. Reconciliation must include corresponding current definitions
and earlier additions, with bounded pages rather than inaccessible pointers. Historical runners and
designer capability branches are not retained; never convert existing runs implicitly.
Reviewer tools are only native ls/glob/grep/read_file on registered run-owned
SQLite evidence through CompositeBackend; StateBackend holds small thread-local state. No host mount, shell, web, subagents, cross-run memory or model-writable host
files. SQLite checkpoints and source pointers preserve retrieval state without automatic summarization.
Assembled input targets 300K estimated tokens with logged exceptional tolerance through 350K.
Count instructions, messages, evidence, tools and response metadata on all turns. Page/offload first;
never silently truncate. Unfit mandatory/indivisible inputs fail operationally, not on output quality.

Use ProviderStrategy only for a permissive top-level JSON object and three transient transport
retries. Save all returned objects without semantic grading, deduplication, repair or content retry.
Store immutable fact bodies separately from ownership. Review all recorded facts, not only Extra;
retain unknown/unusable references in the audit. Execution status and assignment coverage are separate.
Coverage does not prove exhaustive source extraction. Input fingerprints preserve historical response
versions/publications when recovery changes downstream input. Schema-2/3/4/5/6 resume/check is rejected
without mutation. Layer 2 must not create a misleading eight-domain handoff to Layers 3/4.

Publish readable README/domain_plan/domain Markdown views plus unresolved.md when needed. Keep one
immutable facts.jsonl ledger, domain/ownership JSON and snapshots under _internal/, with raw responses,
publication history, usage and checkpoints under _internal/trace/. Retain replaced views before refresh.
Expose unprocessed values without guessing field meanings or retrying completed objects. Prompts request
change-only review observations and concise ownership rows; every supplied fact still receives review.
Inline complete domain definitions only when accounted input fits; otherwise schedule every required
definition-page comparison. Do not substitute ranked retrieval for exhaustive scheduled coverage.
Source-only understanding receives neither plugin nor requirements. Planning/domain review receive both;
initial assignment and scoped updates use domain responsibilities. Read original source only during
understanding, by manifest seeks in bounded
native batches of at most twice concurrency. Planning/review jobs use fresh contexts per page and stable
checkpoint threads on resume. Archive complete older exchanges before pointer eviction, without summaries.
Original snapshots/raw responses/ledger are authoritative; the SQLite evidence index is rebuildable.
Avoid corpus-sized checkpoint state and fingerprints. There is no application output-token limit;
page oversized completed values for downstream jobs, preserving their parent IDs and locations.

Understanding evidence entries are the immutable fact ledger. Application-owned IDs distinguish run,
source job, saved response content version and entry position; re-paging/renaming/reassignment retain
IDs. Preserve identical entries separately and retain old versions. Assign settled domains by IDs,
not by extracting source again. Compact model evidence omits source bookkeeping but preserves labelled
facts, relationships, contradictions and supplemental values; count the exact dispatched message.
Review every recorded fact once, return explicit add/remove ownership operations and separate domain
proposals. Preserve unchanged owners and audit conflicting/unknown operations without repair. Skip
finalization without proposals. Revisit all evidence only for accepted new/changed responsibilities;
missing decisions never remove owners and incomplete comparison coverage remains visible. Final domain
JSON membership is derived from one ownership mapping. Publish every assigned entry without another
selection or rewrite, hiding technical IDs and separate means/applicability/source fields in Markdown.

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

Each Layer 3 domain researcher receives only `search_web` and `read_source`; it has no `task` tool or
subagents, and synthesis has no tools. Python schedules one researcher at a time, saves each final
assistant response verbatim, then synthesizes every available response. Prompts own research,
contradiction mapping, source checking, and corrections. Python may
enforce network safety, persistence, attribution, and atomic publication, but must not grade
Markdown, require auxiliary model-written files, or trigger content-repair calls. Implicit
framework summarization and tool-call repair middleware stay disabled. A run-frozen CDI
summarizer may compact only the direct domain researcher; it must retain source pointers,
must not grade content, and must not block publication. Never add
keyword-based research policy, host shell, `run_python`, cross-property memory, or model-writable
host folders without explicit approval.

Layer 4 follows the same output-freedom contract. Its internal and candidate segregators and final
synthesis have no tools; its external researcher receives only `search_web` and `read_source`.
Python must not inspect segregation or research prose to decide whether another stage runs. Save
each completed response verbatim, continue after failed stages, and use fixed missing-response
markers only as downstream invocation context.

## Commits and Pull Requests

PRs must list affected layers, validations, and schema, model, prompt,
privacy, or resume changes.
