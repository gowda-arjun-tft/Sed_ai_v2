# Notebook factsheet access toggle

## 2026-09-15 IST

**User**

Add an enabled-by-default notebook switch for original-factsheet access, frozen for new
full and linked research runs. Resume uses saved policy; no live execution or report edits.

**Agent**

Completed: Added RESEARCH_FACTSHEET_ACCESS=True in the notebook and a keyword-only Boolean
on workflow and both research creation APIs. New runs freeze the choice; disabled runs omit
the researcher factsheet snapshot/projection, including linked copies. Resume retains saved
policy and displays its status. Reused Deep Agents 0.7.7 native file boundaries; no new tools,
configuration files, review processes, live calls or historical-output changes.

**Verification**

32 focused offline tests passed: native enabled/disabled access, compaction, same-thread
resume, linked creation, workflow handoff, notebook controls, budgets/configuration and
structure checks. Compilation, pip check and git diff --check passed. Notebook kernel
metadata, saved outputs and execution counts match the pre-edit notebook. Docker is not
available in this shell; no container validation or restart was performed. Changes remain local.

## 2026-09-15 08:11 IST

**User**

Restore the notebook toggle after a later save removed its wiring.

**Agent**

Completed: Restored only the notebook Boolean, creation argument, saved-status display and
resume notice. Preserved the notebook's current cleared outputs and kernel metadata.

**Verification**

Four offline notebook/compilation checks passed. Exactly one toggle definition is present;
metadata and outputs match the pre-restoration snapshot. git diff --check passed.
No research execution or backend change.
