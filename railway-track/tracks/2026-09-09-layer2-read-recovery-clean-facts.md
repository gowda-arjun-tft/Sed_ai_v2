# Layer 2 read recovery and cleaner facts

## 2026-09-09 17:40 IST

**User**

Implement bounded SQLite evidence-read recovery and safe run logging; remove separate means and applicability from future extraction and domain views. Preserve schema 6, model behavior, existing runs and Layers 3/4. No live model calls or current-run recovery.

**Agent**

Completed: added shared three-attempt native evidence-read recovery for SQLite BUSY/PROTOCOL, fresh query-only connections and safe contextual run logging. Initialization, history indexing, writes and checkpoints remain outside retries. The disposable concurrency baseline reproduced locking protocol; retries alone also exhausted. Retaining the runner's existing connection idle and committed across stage execution made the same workload pass, without a global lock or reduced concurrency. This is tested lifecycle stabilization, not proof that all SQLite failures are eliminated.

Sort facts no longer requests separate means/applicability. Both domain-rendering paths omit those exact top-level fields while raw responses/ledger remain intact and nested values/prose remain untouched. New-run snapshots receive the prompt change. Updated Layer 2 guide and architecture. Changes remain local and uncommitted; no current run resumed or republished.

**Verification**

Full offline suite: 150 tests passed in 124.828s. Covers 480 native backend tool operations overlapping 30 writes at five workers; injected BUSY/PROTOCOL recovery/exhaustion; non-retryable errors; partial iterator cleanup; fresh connections; idle-connection cleanup on failure; safe logging; native graph follow-ups/checkpoint reuse without extra model calls; both Markdown renderers and unchanged fact bodies. Compilation, pip check, notebook structure/compilation, function docstrings, 350-line limits and git diff --check passed. Hash comparison confirmed the current failed run, user inputs, notebook and Layer 3/4 source files unchanged. No live model or web calls. Semantic extraction accuracy and real-run recovery were not evaluated.
