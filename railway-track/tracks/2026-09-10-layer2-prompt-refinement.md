# Layer 2 prompt refinement and offline benchmark

## 2026-09-10 10:21 IST

**User**

Implement prompt-focused improvements to schema-7 fact retention, grouping, responsibility-based
assignment and need-driven reviewer retrieval on plain_research_v2. Prepare a fixed source-backed
benchmark and extend offline tests. Keep Python runtime, schema, tools, interfaces and publication
unchanged; preserve existing edits, inputs and historical runs. No paid/model/research calls.

**Agent**

Implemented on the existing dirty plain_research_v2 checkout using Prompt Framework guidance.
Only five production prompts changed: Read facts now prioritizes complete rules/exceptions/actors,
scoped figures, narrower coherent topics and comparable contradictions; assignment/review/update
share responsibility-based ownership guidance. The three tool-enabled prompts use supplied context
first and retrieve for necessary missing detail, without reducing scheduled or relevant search coverage.
Choose domains is byte-identical. No runtime Python, tools, schema, settings, publication or stages changed.

Extended existing prompt, snapshot, preservation and paging tests with synthetic qualified rules,
compatible pending payment, Unicode and scoped conflicting figures. Added the fixed twelve-case
[manual benchmark](../../ML/deep_research/layer2/docs/schema7_research_context_benchmark.md), grounded
in the frozen source and prior audits. Updated the Layer 2 guide and current architecture notes.

No model/web/paid calls, research-run execution, repair calls, new evaluation framework or output grader.
New instructions are implemented; extraction gains and reduced reviewer navigation are not established.

**Verification**

- Complete offline unittest discovery was attempted: **21 tests passed; 20 test-module imports failed**
  on the same installed `_uuid_utils` DLL, blocked by Windows Application Control. There were no
  assertion failures among the tests that loaded. The normal focused run and an approved elevated
  retry both encountered the same block. Dependencies/security policy were not modified or bypassed.
- Consequently the new integration, fake-model preservation and frozen-snapshot tests are **not
  verified in this environment**. Full suite must be rerun once the installed DLL is permitted.
- Executed five existing dependency-free test methods directly from their AST, without importing the
  blocked harness: two prompt-contract checks and three notebook/docstring/file-length checks passed.
  This is explicitly a subset check, not a replacement for native graph or recovery tests.
- Compileall for ML/tests, pip check, PowerShell parsing and git diff --check passed. Git reported
  existing LF/CRLF normalization warnings; no whitespace errors.
- All 99 provenance IDs mentioned in the benchmark occur in the frozen source; its SHA-256 matches.
  Twelve cases cover all three source windows. This checks reference integrity, not semantic accuracy.
- SHA-256 comparison found **zero changes in 181 protected files**, covering production Python,
  user inputs, notebook and both historical comparison runs. Designer prompt remained unchanged.

Offline prompt-token counts (`o200k_base`, each file counted once; not provider usage):

| Prompt | Before | After | Change |
| --- | ---: | ---: | ---: |
| Read facts | 774 | 752 | -22 |
| Choose domains (unchanged) | 846 | 846 | 0 |
| Assign facts | 347 | 419 | +72 |
| Review assignments | 725 | 836 | +111 |
| Finalize domains | 749 | 787 | +38 |
| Update assignments | 608 | 719 | +111 |
| Total | 4,049 | 4,359 | +310 (+7.7%) |

The added relevance/retrieval guidance increases aggregate prompt text. Actual run cost depends on
stage/page/turn counts, caching and outputs; no net token reduction or improved extraction is claimed.
Benchmark cases must remain fixed for a later separately authorized identical-settings comparison.
