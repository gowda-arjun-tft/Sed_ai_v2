# Layer 2 schema 7 — offline verification

Date: 2026-09-09. Branch: `plain_research_v2`.

## Retained implementation

Read original source windows once. Preserve each understanding evidence entry with an
application-owned fact ID; design domains before ID-only assignment. Review all recorded
evidence once, apply explicit ownership corrections, and reconsider only accepted new or
changed responsibility scopes. Renaming a domain alone does not schedule reassignment.

Final domain JSON contains membership IDs without duplicate fact bodies. Research Markdown
shows every assigned entry, including meaningful relationships and contradictions, without
source bookkeeping or separate means/applicability fields. The ledger and raw responses
retain complete original values.

## Regression checks

**Result: 159 tests passed in 110.840 seconds.** Compilation, dependency checks,
PowerShell parsing, notebook checks, docstring/file-length checks and `git diff --check` passed.

The offline suite covers:

- Source-window extraction once; every evidence page reaches planning, assignment and review.
- Unicode-safe 60K/10K windows and the 701,133-token boundary fixture.
- Stable IDs across replay, independent equal-text entries, changed response versions and active source order.
- Exact labelled-text paging and matching dispatch/input accounting, including tool follow-ups.
- Complete oversized-definition comparisons, positive partial results and visible missing decisions.
- Explicit additions/removals, conflicting corrections, unchanged scopes and accepted late domains.
- Interrupted review retains completed patches and initial assignments; resume runs only the failed page.
- Empty/unconventional completed values remain reusable and publishable without repair calls.
- Native batching, immediate saves, SQLite recovery, usage attribution and preserved publication history.
- Schema-6 rejection without mutation; unchanged Layer 3/4 tool surfaces and behavior.

Commands:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m compileall -q ML tests
& 'C:\src\anaconda3\envs\compute\python.exe' -m pip check
git diff --check
```

PowerShell parsing, production function docstrings, executable-file lengths below 350 lines,
and notebook JSON/compilation are also checked. Only the notebook's first Markdown cell changes;
all three code cells and the existing `compute` display-name/kernel metadata remain unchanged.

## Native-graph scale exercise

The existing `tests.layer2_scale` exercise used synthetic UTF-8 inputs and fake model responses
through the installed Deep Agents graphs, with synchronous and asynchronous HTTP blocked.
Preparation and execution ran in separate Python processes. Each fake understanding response
contains one evidence entry: this tests source-volume handling, not realistic evidence density.

| Source tokens | Read jobs | Preparation seconds | Preparation peak MiB | Execution seconds | Execution peak MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000,000 | 20 | 1.270 | 448.04 | 13.114 | 419.71 |
| 3,000,000 | 60 | 5.446 | 576.71 | 27.610 | 422.02 |
| 10,000,000 | 200 | 11.845 | 1,024.83 | 87.465 | 421.79 |

All three completed. The 1M/3M fixtures each ran one design, one initial assignment and one review
job after reading. The 10M fixture ran two design jobs, one initial assignment and one review.
No proposals were returned, so domain finalization and scope-update model calls were skipped.
Separate tests exercise accepted proposals, dense/fragmented evidence and oversized definitions.

| Source tokens | Execution logical reads MiB | Execution logical writes MiB | Evidence DB MiB | Checkpoint DB MiB |
| ---: | ---: | ---: | ---: | ---: |
| 1,000,000 | 64.32 | 27.16 | 10.91 | 0.059 |
| 3,000,000 | 186.82 | 83.39 | 32.72 | 0.105 |
| 10,000,000 | 727.65 | 296.91 | 109.78 | 0.281 |

Peak values are process working-set peaks, including the Python/library baseline. Logical I/O
is measured by Windows process counters, not physical-disk traffic. The installed tokenizer's
whole-input preparation allocation remains visible; this is not input-size-independent RAM.
The fixture also verifies literal retrieval of a marker at the distant end of the original source.
Job payloads and fingerprints remain bounded; corpus bodies are not copied into each checkpoint.

Raw local metrics are under `outputs/layer2-schema7-20260909/scale-{1m,3m,10m}/`.
These are offline test artifacts, not user research runs.

## Compact-text token measurement

Read-only measurement used all three completed understanding responses from historical run
`L2_20260909_123721_13fb`: 140 evidence entries. The same application-style IDs and unchanged
fact values were used in each in-memory representation. No historical response was rewritten;
before/after SHA-256 checks matched.

| Representation | Estimated `o200k_base` tokens |
| --- | ---: |
| Indented JSON with complete evidence bodies, IDs and source bookkeeping | 73,054 |
| Same JSON without the dedicated source field | 46,636 |
| Actual labelled-text message format, two bounded pages | 46,473 |

The observed reduction is **36.39% versus complete JSON**, but only **0.35% versus JSON already
excluding source bookkeeping**. Most savings here come from not sending provenance, not from
removing braces. These counts exclude shared prompts, plugin, requirements and domain definitions;
they are not provider usage or an end-to-end cost prediction. Evidence text was not summarized.

## Limits and rollout

Fresh schema-7 runs only; no historical-run migration or execution mode. User inputs, historical
reports, Layer 3/4 implementation and their notebook cells remain outside the change.
No live model, paid API or research calls were made. No application output cap, semantic validator,
content retry, automatic summarizer, dependency or memory service was added.

Offline tests establish operational behavior, not important-fact retention by a real model.
Complete ownership tracking proves coverage of **recorded evidence**, not extraction completeness
from the factsheet. A separately authorized fixed-settings comparison is still needed for quality,
real output size, actual latency, usage and retrieval effectiveness.
