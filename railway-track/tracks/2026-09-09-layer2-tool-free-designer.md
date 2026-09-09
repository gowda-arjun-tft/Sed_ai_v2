# Layer 2 tool-free initial domain designer

## 2026-09-09 14:16 IST

**User**

Make Choose domains tool-free for fresh schema-6 runs. Supply all understanding pages,
plugin, requirements and current definitions explicitly, including bounded large-roster
reconciliation. Preserve historical runs, sequential checkpoints, reviewer tools and output freedom.

**Agent**

Completed: New schema-6 runs freeze design_tool_free=true. Choose domains exposes no tools
or evidence backend; sequential SQLite checkpoints and usage remain. Tool availability is
shared by graph construction and input accounting, independently of scheduling/recovery.
Every understanding page remains explicit input; bounded reconciliation carries current
definitions and earlier additions, with unknown references audited without content retries.
Older runs retain their original capability, prompt snapshots and fingerprint behavior.
Updated the designer prompt, Layer 2/root guides, AGENTS.md and architecture record.
Changes remain local and uncommitted. No historical run was restarted or modified.

**Verification**

- Full offline unittest suite: 141 tests passed (121.996 seconds), including native tool
  surfaces, sequential interruption/reopening recovery, complete evidence paging, large-value
  reconciliation, historical fingerprints, preserved unconventional objects and downstream regressions.
- Compilation, pip check, function-docstring and 350-line checks passed; git diff --check passed.
- Notebook compilation is covered by the full suite. No notebook or Layer 3/4 implementation edits.
- No live model/web calls. Offline tests do not establish extraction quality or a general
  SQLite-locking fix; operational checkpoints and the evidence index still use SQLite.
