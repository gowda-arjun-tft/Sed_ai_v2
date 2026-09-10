# Shared original workspace with Docker Python

## 2026-09-10 12:46 IST

**User**

Replace the isolated development copy with the original read-write project, Git, editable inputs
and runs. Keep Docker Python, preserve container-only edits and old volumes, and leave browser
research untouched. Verify offline and update guidance without research or model calls.

**Agent**

Completed: development mounts the original repository read-write at `/app`; nested development
volumes no longer hide Git, inputs, runs or outputs. The previous three development volumes remain
recoverable and unmounted. Comparison of 133 code/configuration files found only the prepared
notebook and a test marker different; both were exported to
`outputs/dev-workspace-before-sharing-20260910` without merging or overwriting host files.

The development image now installs Git, trusts only `/app`, matches the host's CRLF policy and
retains the named Docker kernel. Removed three Windows Conda workspace overrides and the obsolete
notebook-rewriting helper/test. Added a focused shared-mount regression check and corrected Docker
guidance/architecture. No pipeline, dependency-pin, input or original-notebook changes were made.

**Verification**

- Full offline suite: **160 tests passed in 227.958 s**, in the development image with the original
  workspace mounted and networking disabled; includes source-length, docstring and notebook checks.
- Compilation, `pip check`, PowerShell parsing, Compose validation and `git diff --check` passed.
- Host/container Git status and remotes matched exactly without an explicit index refresh; branch
  `plain_research_v2`. Both environments see **24** historical `run.json` files.
- VS Code reconnected to the current development service, showed original folders/Git, and executed
  the diagnostic-only notebook on Linux `/usr/local/bin/python`. All eight dependency/layer imports
  passed. The named `sedai-docker` kernel also passed an independent notebook execution, saved in
  `outputs/shared-workspace-verification/diagnostic-executed.ipynb`.
- Disposable two-way file/input edits and SQLite WAL writes with four concurrent readers passed;
  100 rows and the marker survived development-container recreation. Removed only the disposable
  input marker afterward. This test is not a guarantee for every SQLite workload.
- Browser container `87df437773eb1ecf856430cdab11832f560409d82e427db6c7176257d24bec18`
  retained its `2026-09-10T06:15:21.250073494Z` start time. All three old development volumes remain.
- Original notebook SHA256 stayed
  `2F6F00FC8FB54A8549A9D9F72B65E9BC879CB462CBB62A1D64375936AEAE0FFC`.
  Image-only checks found no `.env`, Git metadata or API-key environment entry; cached tokenization
  worked without networking. No credentials were printed, no research/model calls were made, and
  no historical run was resumed or converted.
- Changes are local and uncommitted. Git authentication and live research remain outside this task;
  historical schema/frozen-path restrictions and Windows-mounted SQLite performance still apply.

## 2026-09-10 13:22 IST

**User**

Complete the approved VS Code terminal/notebook verification and select Docker Python for the
original notebook without executing research cells.

**Agent**

Completed: both the integrated Linux terminal and the diagnostic notebook reported all imports OK.
Left the original notebook open with `/usr/local/bin/python` selected. VS Code automatically
updated only its `language_info.version` metadata from `3.12.13` to `3.12.14`; no cells were run.

**Verification**

The notebook hash became `018B49B187F1CC45D0D596CA1E9210BF99EA78BFB0943E17E1BE49C5C3F30A37`.
Reversing just that version string in memory reproduces the exact pre-task hash recorded above,
proving code, controls and saved outputs remain byte-identical. The earlier unchanged-file hash
describes the state before this final native kernel selection. Git diff whitespace checks passed.
