# Layer 2 schema 6 — implementation verification

Verified locally on 9 September 2026 using the `compute` environment. No live model,
web-search or paid API calls were made. Changes are local, not committed or pushed.

## Retained implementation

- Six familiar stages and compact responsibilities-and-facts Markdown; schema 6 only.
- Read facts receives original source only. Plugin and requirements remain frozen inputs
  for planning/review; sorting and final assignment consume derived responsibilities.
- One tokenization pass prepares Unicode-safe 60K/10K source ranges. Execution seeks
  ranges and uses native batches of at most twice frozen concurrency.
- Run-owned SQLite evidence pages replace corpus-sized checkpoint initialization.
  Literal search, directory shards, source continuity and exact session archives remain retrievable.
- Finite subject/proposal updates and complete definition-page comparisons handle large
  rosters. Oversized-roster sorting extracts once, then assigns owners separately.
- Complete input accounting applies on initial and follow-up turns: 300K normal target,
  350K exceptional ceiling, also bounded by model capacity. No application output cap.
- Raw objects, immutable fact bodies, versioned responses and previous publications remain
  preserved. Unknown values and unresolved comparisons are visible without content repair.
- Ledger projections and publication stream records, one domain view at a time.

Deep Agents Builder guidance informed native graphs, tool boundaries and checkpoint recovery;
Prompt Framework guidance informed stage authority and bounded task modes. Railway Track records
the implemented architecture and verification. No framework upgrade or dependency was added.

## Offline checks

The complete `unittest` suite passed: **133 tests, 127.368 seconds**. Coverage includes:

- Schema-6 creation and non-mutating rejection of schema 2/3/4/5 execution/checks.
- Source-only first-stage payloads, plugin-independent planning and frozen prompt mappings.
- Exact 701,133-token case: 14 windows and 831,133 processed source tokens; Unicode,
  overlap, final-window handling and parent-linked oversized records.
- Bounded concurrency, immediate saves, source-order assembly, finite paged planning,
  extraction-once ownership passes and every required definition-page comparison.
- Raw unconventional/empty output preservation, multi-domain ownership, unresolved material,
  unchanged fact values and historical publication bytes.
- Native read-only tool surfaces, denied host paths, run/session isolation, literal search,
  exhaustive shard traversal, same-thread SQLite recovery and exact history offloading.
- Rebuilding deleted/damaged derived indexes without another model call; retained damaged
  bytes; Windows long-path response saving and resume.

Compilation, `pip check`, notebook JSON/top-level-await compilation, PowerShell parsing,
production function-docstring checks, executable-file length checks and `git diff --check`
passed. The notebook retains three code cells and its existing `compute` kernelspec.
Layer 3/4 implementation and notebook cells, user inputs and historical research files
were unchanged. User-authored architecture HTML was not rewritten.

## Scale exercise

Each fixture contains exactly the stated source-token count. A distant marker at the source
end was retrieved through the indexed native backend after completion. HTTP was blocked;
the real agent graphs used compact deterministic fake model responses. Preparation and
execution ran in separate processes. RAM figures are process peak working sets, including
the Python/dependency baseline; MiB means 1,048,576 bytes.

| Source tokens | Windows | Preparation | Preparation peak RAM | Fresh execution | Execution peak RAM | Jobs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 million | 20 | 1.206 s | 447.9 MiB | 21.049 s | 420.0 MiB | 44 |
| 3 million | 60 | 4.364 s | 576.1 MiB | 54.340 s | 421.3 MiB | 124 |
| 10 million | 200 | 11.266 s | 1,024.3 MiB | 190.394 s | 420.3 MiB | 407 |

| Source tokens | Preparation read/write | Execution read/write | Evidence database | Checkpoint database |
| --- | ---: | ---: | ---: | ---: |
| 1 million | 17.2 / 8.6 MiB | 82.2 / 31.6 MiB | 11.05 MiB | 0.15 MiB |
| 3 million | 51.6 / 25.8 MiB | 257.5 / 99.9 MiB | 33.21 MiB | 0.36 MiB |
| 10 million | 171.8 / 85.9 MiB | 1,148.9 / 376.8 MiB | 111.25 MiB | 1.07 MiB |

Read/write figures are Windows process-level **logical I/O**, including SQLite and operational
storage, not physical disk traffic or model token usage. Checkpoint sizes are final on-disk sizes.
The 10M job breakdown was 200 read, 2 choose, 200 sort, 2 review, 1 finalize and 2 assign.
All jobs in the fresh exercises completed. Index bodies are shared across retrieval sessions;
checkpoints do not receive corpus-file copies. Timings vary with other local workloads.

Raw measurements remain in ignored local storage:

- `outputs/schema6-scale/final-1000000/{prepare,execute}-metrics.json`
- `outputs/schema6-scale/final-3000000/{prepare,execute}-metrics.json`
- `outputs/schema6-scale/verified-10m/{prepare,execute}-metrics.json`

The first two measurements preceded the final archive-index and unconventional-disposition
edge-case fixes; their short-response fixtures do not exercise either branch. The final full
suite and fresh 10M exercise ran after those fixes.

### Recovery observation

A separate 10M attempt recorded eight `PermissionError` job failures and published the
available 192 recorded facts as partial output. The specific filesystem denial was not
reproduced during diagnostic recovery. Resuming reused saved responses, recovered failed
jobs on their recorded identities, recomputed affected downstream work and completed all
407 jobs with 200 recorded facts. Recovery took 135.893 seconds and peaked at 417.4 MiB.
These recovery figures are **not** included in the fresh-execution table. The later fresh
10M exercise completed without failures. Filesystem access can still fail; this change
preserves and exposes such operational failures rather than grading or repairing answers.

## What this does not establish

The installed tokenizer still allocates for the whole source during preparation. Execution
RAM stayed approximately flat across these fixtures, but preparation RAM did not. Large
individual model responses and very large plugin/requirement inputs have their own memory
and provider limits; impossible assembled inputs fail operationally without truncation.

The fake model emits one synthetic fact per window, so these figures do not establish
real-model extraction completeness, dense-output throughput, semantic retrieval quality,
cost or provider latency. Exact stored evidence is recoverable; that does not prove an LLM
will find and correctly use every fact. A separately authorized, fixed-settings model
evaluation is still required before claiming semantic reliability at 10 million tokens.
Dynamic Layer 3/4 integration and conversational question answering remain out of scope.

## Reproduce

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
& 'C:\src\anaconda3\envs\compute\python.exe' -m tests.layer2_scale prepare outputs/schema6-scale/example --tokens 10000000
& 'C:\src\anaconda3\envs\compute\python.exe' -m tests.layer2_scale execute outputs/schema6-scale/example --tokens 10000000
```

Use a new fixture directory for a fresh measurement. Executing an existing fixture measures
resume/recovery instead; the benchmark blocks HTTP and never calls the provider.
