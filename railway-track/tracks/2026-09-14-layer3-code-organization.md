# Layer 3 Code Organization

## 2026-09-14 IST

**User**

Reorganize Layer 3 like Layer 2: keep operational code under `backend/`, model-facing Deep Agents code under `ML/`, and prompts under `ML/prompts/`, without changing behavior or public package APIs.

**Agent**

Completed: moved Layer 3 operational code into `backend/`, model-facing Deep Agents code into `ML/`, providers and unchanged prompts below `ML/`, and split graph construction from research scheduling. Package-level APIs remain unchanged; obsolete internal import paths have no forwarding wrappers.

**Verification**

Passed: 160 offline tests in the `compute` environment; full Layer 3/package compilation; dependency check; notebook-cell compilation through the suite; PowerShell parsing; 350-line and docstring checks; exact Git blob hashes for all four moved prompts; no old internal imports; and `git diff --check`. Historical capability-v1 concurrency and schema-9 checkpoint/config recovery passed. Docker verification is blocked because `docker` is not available in this shell.
