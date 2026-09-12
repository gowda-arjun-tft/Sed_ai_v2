# Layer 3 unique document uploads

## 2026-09-11 12:09 IST

**User**

Implement consented document-byte retrieval, run-scoped URL/content deduplication and one OpenAI
Files upload per unique document, enriching source JSON with upload/file_id. New runs continue
after discovery; existing runs require explicit upload-only selection. Preserve raw responses,
history and partial results. Files persist until manually deleted. Offline verification only;
no live downloads, uploads, research or changes to Layers 2/4.

**Agent**

Partial: implementation is retained and verified offline on Windows compute. New schema-9 Layer 3
runs freeze an upload capability and continue after source discovery; explicit upload-only
API/CLI/PowerShell/notebook actions enrich saved runs without source-finder calls. Sequential public
downloads use temporary storage, URL/hash deduplication, native Files user_data uploads and immediate
intent/receipt persistence. Lost responses reconcile remote metadata and byte hashes without blindly
re-uploading. The existing JSON publisher preserves duplicate members/raw responses, adds trusted
upload/file_id fields and archives previous views. Transfer status stays separate from discovery.

OpenAI Docs informed native Files behavior and retention; Ponytail guidance kept the change on
existing URL safety, JSON, logging and atomic-history helpers plus the installed SDK/httpx, with
no new dependency, agent, database or research stage. Updated the Layer 3 guide, notebook controls,
repository guidance, vision and implemented architecture. All changes remain local, uncommitted.

Remaining: Docker is not installed/discoverable in this shell, so development-container verification
is outstanding. A live run remains separately authorized; no real downloads, uploads or models ran.

**Verification**

Verified 2026-09-11 12:35 IST:

- Full offline suite: 180 tests passed (final full run: 99.404 seconds) using Windows compute.
- Native OpenAI SDK serialization exercised through mocked HTTP, including multipart purpose,
  no automatic expiry, duplicate URLs, different URLs with identical bytes, successful-ID reuse,
  deletion/inaccessibility, rejected uploads, lost responses and remote hash reconciliation.
- Tested interrupted downloads/uploads, receipt-save interruption, publication failure/rebuild,
  exact create-attempt limits, explicit retries, successful siblings and OS writer-lock release.
- Tested unsafe redirects/credentials, actual/declared byte limits, HTML impostors, unsupported
  representations, ambiguity, duplicate JSON members, Unicode, arbitrary/empty objects and no
  content repair. Upload-only execution makes no model call and preserves source-response bytes.
- Executed the upload-only notebook branch with a fake uploader, checked its required explicit run
  path, CLI/PowerShell dispatch, new-run continuation and source-only behavior without the capability.
- Compilation, pip check, PowerShell parsing, three notebook code-cell compilation, executable
  file-length tests, new/affected production function-docstring checks and git diff --check passed.
- Layer 2/4 notebook cells and every saved code-cell output compare unchanged with the pre-edit
  snapshot. Layer 2/4 implementation, factsheet/requirements, dependencies and Docker files have no
  changes from this work. The actual completed L3 run still has no upload registry and its newest
  file timestamp predates implementation; historical artifacts were not republished or resumed.
- Verification establishes offline operational behavior, not live download availability, upload
  acceptance, later file-input readability or research accuracy.

## 2026-09-11 13:27 IST

**User**

Keep failed document uploads visible but exclude them from future research, preserve web-access
observations separately, and let otherwise-complete source discovery finish with upload warnings.
Apply this only to fresh Layer 3 runs; do not rerun research or modify historical runs.

**Agent**

Completed: fresh Layer 3 runs now freeze document-upload policy version 2. Published source
entries retain the model's original `access` and `access_note`, and add application-owned
`upload_status`, `upload` and `file_id` fields. Verified uploads are eligible for later research;
failed or uncertain documents are preserved but excluded. Readable or partial ordinary/unknown-
format URLs remain eligible. Per-document failures no longer downgrade completed source discovery:
the run stays `complete`, the nested upload status is `partial`, and README/notebook presentation
reports `complete with upload warnings`. Source-finder failures and preservation failures retain
their existing operational effect.

The implementation reused the existing projection, registry, publication and notebook status paths;
it added no failure file, research stage, model call or retry. Historical runs were not opened for
mutation, resumed or republished. All changes remain local and uncommitted.

**Verification**

Verified 2026-09-11 13:38 IST using Windows compute:

- Full offline suite: 181 tests passed in 82.069 seconds.
- Covered definitive download/upload failures, uncertain acceptance, verified IDs, preserved access
  observations, continued sibling uploads and the future research-eligibility rule, including a
  domain with no eligible sources.
- Existing raw-response, deduplication, recovery, source-discovery failure and publication-history
  tests passed without adding model calls or content repair.
- Python compilation, dependency checks, PowerShell parsing, all three notebook code-cell
  compilation, executable file-length/function-docstring checks and `git diff --check` passed.
- No live model call, web request, file upload or Layer 3 rerun was performed. Docker verification
  remains outside this Windows-shell result.
