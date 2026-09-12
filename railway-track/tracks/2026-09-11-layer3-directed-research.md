# Layer 3 user-directed, bounded sequential research

## 2026-09-11 18:59 IST

**User**

Implement research capability version 2 with one domain at a time, a frozen editable
user research instruction, and an 80-logical-call allowance including search, document
analysis and summarization. Begin wrap-up after 60 calls, retain saved-file reading
after 70, and reserve the last call for final Markdown. New linked runs reuse prior
research evidence and notes without modifying their parent. Preserve historical
policies, Layer 2/4, current edits and outputs. No live execution is authorized.

**Agent**

Completed: New full and linked schema-9 runs freeze research capability version 2:
one domain at a time, an editable user objective, and 80 durable logical-call slots
shared across main, search, document and summary requests. Wrap-up/finalization notices
do not accumulate in history; saved-file reading remains available during finalization,
and only the tool-free main report may use the last slot. Exhausted unfinished domains
remain partial while successful siblings publish. Historical policies remain frozen.

Added CLI, PowerShell and notebook instruction controls, run/README/notebook counters,
and execution-owned HTTP clients. The existing shared model helper accepts optional
native client overrides; default Layer 2/4 behavior is unchanged. New linked runs copy
and hash prior evidence, compatible caches, reports, usage and notes/plans into fresh
threads without modifying their parent. Read-only SQLite opens were observed to create
WAL sidecars in a disposable test; handoff now inspects a disposable database/WAL copy
and uses native DeltaChannel reconstruction to retain checkpoint-backed notes.

Used Deep Agents Builder for native middleware/checkpoint/client integration and Prompt
Framework for the generic researcher/user-objective separation. Updated Layer 3/root
guides, AGENTS.md, Docker guidance, Railway Track vision/architecture and this track.
Changes remain local and uncommitted. No real run, search, upload, container restart or
historical-run rewrite was performed.

**Verification**

- Docker full offline suite: 208 tests passed (final full run: 135.485 seconds).
- Final focused budget, handoff, memory, document and controls suite: 22 tests passed.
  Includes an actual 80-turn fake native graph, no 81st invocation, tool-free last call,
  readonly finalization tools, atomic concurrent reservations, failures/cancellation,
  same-thread resume, parent checkpoint byte preservation and client lifecycle.
- Compilation of ML/tests/docker and dependency checks passed; no broken requirements.
- Notebook JSON and all three code cells compile; PowerShell parsing passed.
- File-length/docstring checks passed; largest changed production file is 261 lines.
- Docker checkpoint preflight passed with disposable SQLite data on the dedicated volume;
  interpreter is Linux /usr/local/bin/python. Browser container identity/start time was
  unchanged across verification; neither container was restarted.
- Baseline SHA-256 comparison preserved existing input bytes and Layer 4 files. Only the
  optional shared model-builder extension changed under Layer 2. Only the Layer 3 cell
  changed in the notebook; other cells and saved outputs remain intact.
- git diff --check passed. Live report quality, API credit availability and real-model
  risk/opportunity/action fidelity remain unverified; execution requires separate consent.
