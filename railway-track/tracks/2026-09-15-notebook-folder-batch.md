# Sequential notebook factsheet batch

## 2026-09-15 IST

**User**

Run top-level Markdown factsheets from inputs/facts sequentially through the existing full
workflow. Continue after ordinary failures; explicit resume selects one existing run.
Preserve controls, harness, historical outputs and notebook metadata. Offline checks only.

**Agent**

Completed: Notebook now selects top-level Markdown files once in alphabetical order and
awaits each existing full workflow before starting the next. Ordinary failures/partial
results continue; cancellation stops. Explicit resume selects one run. Kept independent
numbered runs, current settings (factsheet access False), saved outputs and Docker metadata.
No backend/harness/API changes or batch registry. Updated the existing guide and repository guidance.

**Verification**

18 focused offline notebook, structure and workflow tests passed, including five-file ordering,
failure/partial continuation, fresh reruns, cancellation, empty/missing folders and single-run
resume. Notebook compilation and git diff --check passed; metadata/output comparison matched
the pre-edit snapshot. No live research, uploads, container restarts or historical changes.
