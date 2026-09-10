# Layer 2 extract once and review corrections

## 2026-09-09 21:07 IST

**User**

Implement schema 7 on plain_research_v2: preserve understanding evidence with stable IDs, decide domains before ID-only assignment, review once and apply scoped corrections. Keep every assigned entry in compact Markdown. Preserve historical runs, Layer 3/4, interfaces, operational safeguards and output freedom. No live model or research calls.

**Agent**

Completed on `plain_research_v2` at 2026-09-09 21:42 IST.

Schema 7 uses understanding as its only scheduled original-source extraction. Each preserved
entry receives a stable content-versioned fact ID; planning and ownership use bounded labelled
text. Initial assignment is ID-only. One review applies explicit owner patches, with conflicts
audited; accepted new/changed responsibilities trigger only scoped all-evidence updates.
Unchanged scopes carry forward. Empty proposal sets skip finalization and follow-up calls.

Final domain JSON derives membership from the ownership mapping; clean Markdown retains every
assigned entry. Existing storage, paging, SQLite read recovery, checkpointing, native concurrency,
model settings and output freedom remain in place. Historical runs, user inputs, Layer 3/4 and
all notebook code cells remain unchanged. Updated prompts, documentation, guidance and architecture.

**Verification**

- Full offline unittest suite: **159 passed** (110.840 seconds), including extraction once,
  stable IDs/version history, every-page coverage, explicit removals/conflicts, scoped updates,
  interrupted-review recovery, output freedom and protected downstream behavior.
- Compilation, `pip check`, PowerShell parsing, notebook JSON/top-level-await compilation,
  function docstrings, executable-file length checks and `git diff --check`: passed.
- Existing native-graph scale exercise completed at **1M, 3M and 10M source tokens**, with
  HTTP blocked and synthetic outputs. At 10M: preparation 11.845s / 1,024.83 MiB peak;
  execution 87.465s / 421.79 MiB peak. No claim of input-size-independent tokenizer RAM.
- Read-only in-memory measurement of 140 historical evidence entries: labelled text 46,473
  tokens versus full JSON 73,054; source-free JSON 46,636. Savings were mainly source bookkeeping.
  Historical response hashes matched before and after measurement.
- No live model/research calls. Operational tests do not prove source extraction completeness
  or real-model quality. Layer 3/4 integration and a live comparison remain separate authorization.

Details: [schema-7 verification](../../ML/deep_research/layer2/docs/schema7_verification.md).
