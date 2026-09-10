# Docker support for plain_research

## 2026-09-10 14:51 IST

**User**

Bring the proven V2 Docker infrastructure to plain_research without importing its research changes. Share the original project, preserve schema 6 and historical runs, make notebook paths portable, and verify offline without restarting browser research.

**Agent**

Completed: Restored only Docker infrastructure from b66a57c, with a branch-specific guide,
portable notebook path literals and Docker instructions. Removed only the three Conda workspace
overrides. Reused the existing development container; no image rebuild, container restart,
research execution, dependency upgrade or branch/commit change was needed. Schema-6 code and
prompts remain unchanged. Added the shared-workspace regression check and portable notebook tests.

**Verification**

151 offline unit tests passed in 117.111s. Compilation (ML/tests/docker), pip check, quiet Compose
validation, PowerShell parsing and git diff --check passed. Terminal and a separate disposable
sedai-docker notebook kernel verified Linux, /usr/local/bin/python, required imports and schema 6.
Only the diagnostic kernel was started/stopped; existing user kernels were not touched.
Shared host-to-container and container-to-host visibility passed; the temporary marker was removed.
A disposable Windows-mounted SQLite WAL database preserved Unicode over 24 concurrent reads and
was cleaned up. Notebook metadata, saved outputs and controls were compared with HEAD unchanged;
code differs only in four path separator replacements. No live model calls were made.

VS Code's visible connection and the user's selected kernel were not inspected or changed.
The user must reopen in the Dev Container and select Docker Python; restart an idle kernel after
switching branches. Fresh-image build and manual Windows scale exercise were not repeated.
Changes are local and uncommitted. Infrastructure validity is not a guarantee of model output quality.

## 2026-09-10 15:03 IST

**User**

Complete the approved checks that historical files and existing containers remain untouched.

**Agent**

Completed: Final preservation checks passed; no additional implementation changes.

**Verification**

Before/after path-size-mtime fingerprints match for all 86 non-cache ML files, both input files,
and 9,359 historical run files. Git reports no ML or input changes. Development container
984462cbe01b (started 07:25:50 UTC) and browser container 87df437773eb (started 06:15:21 UTC)
retain identical IDs/start times. Copied infrastructure matches b66a57c and whitespace checks pass.

## 2026-09-10 15:14 IST

**User**

Fix the Layer 2 notebook cell after Docker resolved its Windows path literally and failed before run creation.

**Agent**

Completed: Corrected all four notebook-controlled input/run paths to portable forward-slash
literals and replaced the damaged failure separator with ASCII. The Layer 2 cell itself retains
valid Python identifiers and indentation; the formatting damage in the pasted chat text was not
present in the notebook. Tightened the structure test so Windows-only paths cannot return.

**Verification**

All three code cells compile in Docker; both Layer 2 input paths exist at /app. The focused
structure suite passed all 8 tests in 116.404s and git diff --check passed. No run was created,
resumed or invoked, and no model call occurred. An existing user notebook kernel was detected and
left running; it was not restarted or interrupted.
