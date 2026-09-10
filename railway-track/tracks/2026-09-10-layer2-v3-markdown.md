# Layer 2 V3: simple Markdown research preparation

## 2026-09-10 17:43 IST

**User**

Implement schema 8 on plain_research_v3: 50K/5K windows, sequential cumulative subject metadata, one domain decision, and direct original-source distribution. Model outputs are Markdown; remove Layer-2-only agents, reviewer, JSON projections and SQLite. Preserve shared helpers, historical runs, public interfaces, Docker, input safety and partial publication. No live model calls.

**Agent**

Completed: retained the schema-8 direct Markdown workflow on plain_research_v3. Three industry-neutral prompts replace six stages; metadata is sequential, design is one call, and distribution uses bounded native concurrency. Removed Layer-2-only graph/tools, SQLite evidence/checkpoints, reviewer/reconciliation, immutable-fact/ownership projections and their obsolete tests. Shared filesystem, model and usage helpers remain unchanged for Layers 3/4.

Retained input/hash preflight, Unicode-safe source seeks, complete input accounting, immediate response saves, dependency-versioned recovery, provider usage/completion attribution, safe logs and recoverable partial publication. Exact H1 routing outside fences exposes unmatched text without grading or repair. Updated Layer 2/root guides, repository instructions, Docker guide schema references and only the Layer 2 notebook description/comment. Source controls, saved outputs and Layer 3/4 cells remain unchanged. All changes are local and uncommitted.

**Verification**

- Full offline unittest discovery in existing `sedai-dev-1`: **128 passed**, 87.885 seconds, with socket connections explicitly blocked. Earlier focused failures were fixture/profile setup and stale notebook-path assertions; final tests preserve the existing Layer 3/4 path literals rather than changing those cells.
- `python -m compileall -q ML tests`: passed in Docker. `python -m pip check`: no broken requirements. All package imports, three notebook code cells, function docstrings and the 350-line file limit passed. Native host PowerShell parsing: one script, zero errors. Host and Docker `git diff --check`: clean.
- Source fixtures verify exact token slices, no redundant tail, Unicode/BOM/line-ending preservation and the 701,133-token case. The actual untouched current factsheet measures **159,316 tokens**, yielding **50,000 / 50,000 / 50,000 / 24,316** windows and **nine logical calls**, not a live execution.
- Direct builder payload inspection (no invocation) confirms the fixed model/reasoning, three transport retries, `store=False`, and no tools, response format, previous-response ID or application output cap. Fake calls verify generic property/stock/bond/policy/mixed inputs, sequential metadata, one design, bounded concurrency, exact message accounting, input-size failure, source-order publication and immediate saves.
- Recovery tests cover missing responses, failed siblings, dependency changes, interruption between response save and job commit, interrupted provider-incomplete results, older matching completion recovery, preserved historical view bytes and publication rebuild without new completed-job calls. Empty/unconventional Markdown remains reusable; routing observations do not change execution status.
- Production Python: **2,177 → 1,079 lines**, **1,098 removed (50.4%)**, 24 → 17 files; largest retained executable file is 164 lines. Prompt tokens (o200k_base): metadata 436, design 292, distribution 443; measurements are not quality claims.
- SHA-256 comparison: **43 protected files unchanged**, including Layer 3/4 implementation, user inputs, requirements/Compose and shared harness/fs/usage helpers. Layer 3/4 notebook cells and all saved notebook outputs equal their HEAD versions. Historical research files were not rewritten or resumed; no container was restarted.

Remaining limits: metadata/domain-plan growth can hit the safe input ceiling; the source tokenizer still allocates for the whole input during preparation. Markdown compliance and important-fact retention are not guaranteed by fake-model tests. No live model/research run or paid comparison was performed. Dynamic Layer 3/4 integration remains separate. Historical Windows path controls in those unchanged cells are not claimed to be Linux-portable by this change.
