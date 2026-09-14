# Module names, single-cell workflow and repository cleanup

## 2026-09-14 13:53 IST

**User**

Rename Layer 2/3 to domain_decider/research_module, combine notebook execution and consolidate current documentation. Preserve dirty work, historical artifacts, prompts, harness and frozen recovery policies. No paid execution or container restart.

**Agent**

Completed: renamed the packages to domain_decider/research_module at the same depth, updated
imports/mocks/CLI dispatch and consolidated the notebook into one preflighted execution cell.
Explicit domain reuse/resume, research resume, linked research and upload-only remain available.
The notebook passes the newly completed domain run to research exactly once and stops on domain
failure/partial status. New cell output is empty; original notebook/kernel/output bytes are backed up.
Prompts, harness, frozen keys, thread identities, run prefixes, model settings and policies are unchanged.
Consolidated current docs into root README, combined architecture overview and docker/development.md.
Updated repository instructions and repaired moved-path links without rewriting dated findings.
All changes are local; no commit, live model call, upload, research execution or container restart.

Recoverable pre-change copies (including untracked files), manifest, interrupted fixture and check
logs are under `outputs/rename-backup-20260914/`. This backup intentionally preserves pre-existing
dirty changes; a rollback should be reviewed file by file, not copied over newer work blindly.

Final layout:

```text
ML/deep_research/
  domain_decider/{backend,ML/prompts,plugins,docs}
  research_module/{backend,ML/providers,ML/prompts}
  docs/Research_Architecture_Overview.md
README.md
docker/development.md
CDI_Layer2_Layer3.ipynb  (one code cell)
```

Removed two verified unused constants: RUN_PREFIX and CHECKPOINT_PACKAGE_VERSION.
Production Python against the saved dirty baseline: **4,317 → 4,315 lines (-2)**.
Notebook executable source: **128 → 135 lines (+7)** including handoff/preflight/status;
the combined workflow adds no production orchestration module or harness abstraction.
Package/directory moves, stale bytecode and duplicate documents are not counted as Python reductions.

Deleted documents (all recoverable in the backup):

- Former `layer2/README.md` and `layer3/README.md` (guidance consolidated).
- `ML/deep_research/docs/README.md` (history index consolidated).
- `ML/deep_research/docs/html/260908_Deep_Research_Target_Architecture_ENG.html`.
- `ML/deep_research/docs/html/260908_Document_Ingestion_Design_ENG.html`.
- `ML/deep_research/docs/html/260908_Layer2_Domain_Design_And_Fact_Memory_ENG.html`.
- `ML/deep_research/docs/html/260908_Layer3_Cost_And_Context_Baseline_ENG.html`.
- `ML/deep_research/docs/html/260908_Layer3_Layer4_World_Model_Redesign_ENG.html`.

Removed module-local stale bytecode/empty retired directories, empty `tests/fixtures` and
the now-empty duplicate HTML directory. Kept all Markdown originals, standalone historical HTML,
audits, quality benchmark, Jira material, run outputs and shared helpers with retained callers.

Retained cleanup candidates: 20 pre-existing missing function/method docstrings in research
retrieval, source storage, text extraction and the provider adapter. No new gaps were introduced.
These are documentation debt, not evidence of dead code. The thin backend runner and shared
model/persistence/checkpoint helpers have active callers; they were not removed.

**Verification**

- Pre-change Windows compute baseline: **160 offline tests passed**.
- Final Docker suite: **162 tests passed** (157.198 seconds), plus 18 earlier focused Windows checks.
  Includes public imports, notebook actions, failure handoff, uploads, linked runs, budgets,
  sequential research, tool/memory isolation and checkpoint recovery.
- A native fixture interrupted before renaming resumed afterward on Windows with identical
  thread/checkpoint paths, saved source responses and completed report bytes. Completed sibling
  calls remained 3→3; interrupted sibling calls continued 1→4 without resetting its ledger.
  Docker's retained same-thread recovery tests also passed.
- Seven production prompts, the domain plugin and user input files matched pre-change SHA-256.
  Notebook metadata/kernel matched exactly. Historical run inventory sizes/timestamps were unchanged.
- AST comparison against backed-up production files passed after normalizing only approved imports,
  package descriptions and the two deleted constants. No harness behavior changed.
- Docker diagnostics imported both renamed packages and dependencies with Linux `/usr/local/bin/python`.
  Both CLI help commands passed; old executable package imports are absent, with no wrappers.
- Docker compilation, pip check and quiet Compose validation passed. PowerShell parsed successfully.
  Source-length checks and existing docstring checks passed; extended audit found only the 20
  unchanged pre-existing docstring gaps above. Current documentation links resolve.
- `git diff --check` passed. Development and browser container IDs/start times were unchanged.
  No live model, research, search or upload quality claims are made.
