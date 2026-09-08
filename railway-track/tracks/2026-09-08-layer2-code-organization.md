# Layer 2 plugin-only definitions and code organization

## 2026-09-08 12:25 +05:30

**User**

Separate schema-4 Layer 2 backend operations from AI code; keep industry definitions in plugins, relocate historical helpers and planner fixtures, add an editable requirements template and workflow guide. Preserve runtime behavior, existing changes and research artifacts. Codex implements directly as requested.

**Agent**

Completed: separated Layer 2 operations into backend/ and AI construction/context/six generic prompts into ML/. Exported create_run/run_all, updated callers and notebook imports, moved historical roster/helpers into Layer 3 and preserved the old planner in test fixtures. Removed the unused router. Added the editable requirements template and Layer 2 workflow/file guide. Updated repository guidance and Railway architecture. No runtime behavior, schema, model, tool or research artifact changes; work remains local and uncommitted.

**Verification**

115 offline unittest tests passed, including all six stages with real-estate/insurance/stock-market fixture plugins, frozen prompt paths/hashes, native read-only tool isolation, same-thread recovery and reopened SQLite serialization. Compilation, pip check, CLI help, PowerShell parsing, three notebook cells/compute kernel, recursive function-docstring and 350-line checks, and git diff --check passed. The extra diff check with autocrlf disabled exposed existing CRLF whitespace; the required check using repository configuration passed without changing those files. Compared moved runtime bodies and downstream files against the task baseline: only approved imports/settings/helper locations changed. Historical planner text including original line endings is preserved. All existing input hashes and the 12,300 run/backup file inventory entries (paths, sizes and timestamps) are unchanged. No schema-4 runs existed before relocation; no migration or live model/web calls were made. Dynamic downstream integration remains separate.
