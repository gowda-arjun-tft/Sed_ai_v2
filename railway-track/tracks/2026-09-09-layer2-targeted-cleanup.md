# Layer 2 targeted cleanup

## 2026-09-09 22:18 IST

**User**

Implement both reviewed cleanup lists on plain_research_v2. Remove dead/duplicate code and unnecessary indexing without changing schema 7, output freedom, public interfaces, safety or ownership behavior. Preserve existing edits, inputs and historical runs; use offline verification only.

**Agent**

Completed: targeted cleanup retained locally on plain_research_v2, without committing.

Removed the test-only duplicate renderer, unused initial-decision/understanding projections,
unused helper options/return values, redundant manifest filtering and a duplicate metadata write.
Source preparation now serves understanding only and avoids discarded decoded repacking values.
Planning and dispatch reuse input accounting. Tool-free design skips domain index snapshots;
review prepares current definitions, and unchanged ownership scopes skip setup while retaining audits.

Production Python: **2,345 -> 2,320 lines (-25)** versus the pre-cleanup dirty tree, including
blank/docstring lines and excluding tests/docs. This is below the estimated 30-50-line saving;
additional savings are avoided indexing and writes, not deleted safeguards. Renderer tests now
exercise the actual streaming publisher. No new production helper or compatibility branch added.

Schema, model, prompts, public entrypoints, output freedom, raw responses, immutable facts,
ownership protections and SQLite recovery remain intact. Existing research/input/notebook files
and Layer 3/4 implementation were not edited. Consolidated retrieval changes the manifest on a
later explicitly authorized resume; affected reviewer fingerprints invalidate normally, without
converting or resuming any existing run here. Current truth is documented in the Layer 2 README
and railway-track/architecture.md.

**Verification**

- Final complete offline suite: **159 tests passed in 116.311s**. An earlier pass exposed tests
  tied to the removed projection and an assertion counting a parsed header rather than full text;
  both now verify the retained raw-response path and exact dispatched input. No production repair added.
- Focused publication/designer/schema-7/input/scaling suite: 38 tests passed before final test updates.
- Compileall, pip check, PowerShell parsing, notebook compilation/kernel/cell checks,
  production docstrings, 350-line ceilings and git diff --check passed.
- Offline native-graph scale checks passed with HTTP blocked and disposable fixtures:

| Source tokens | Preparation seconds / peak MiB | Execution seconds / peak MiB | Jobs: read/design/assign/review |
| --- | --- | --- | --- |
| 1M | 1.013 / 447.69 | 12.139 / 419.59 | 20 / 1 / 1 / 1 |
| 3M | 2.802 / 576.10 | 31.338 / 421.91 | 60 / 1 / 1 / 1 |
| 10M | 8.681 / 1,024.16 | 94.415 / 422.92 | 200 / 2 / 1 / 1 |

Scale measurements are operational checks, not controlled speed comparisons or evidence of model
extraction accuracy. Finalization/update calls were correctly absent for the empty-proposal fixtures.
At 10M, the evidence DB was 113,164,288 bytes and checkpoints 294,912 bytes; distant original text
remained retrievable. No live model or research calls were made.
