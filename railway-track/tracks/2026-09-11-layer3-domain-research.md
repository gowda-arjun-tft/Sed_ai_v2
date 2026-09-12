# Layer 3 persistent domain research

## 2026-09-11 — implementation opened

**User**

Connect preparation to one persistent Deep Agent per domain, with native planning,
retrievable memory, document reading, Docker-volume checkpoints and independent Markdown
reports. Add linked research-only runs; preserve historical preparation and Layer 4.
No live searches, uploads or research execution are authorized by this implementation.

**Agent**

Implemented on `layer3-v1`. Reused installed Deep Agents 0.7.7, upload receipts, source safety,
atomic publication and logging. Deep Agents Builder guided native todos, CompositeBackend,
summarization and AsyncSqliteSaver; Prompt Framework guided the three new generic prompts.
Preserved the existing dirty worktree. No application research budget or content repair.

- Fresh schema-9 runs freeze research capability version 1 and continue preparation into up to
  five native domain graphs. Linked research-only runs copy/hash settled preparation into a new
  run, preserving parent bytes and file IDs. Old preparation-only runs retain their behavior.
- Added private notes, read-only evidence/input routes and accessible full-history archives;
  explicit 250K/100K compaction with final 300K/350K input accounting, and a 128K search ceiling.
  Coverage remains model-authored. No shell, delegation, deletion or final synthesizer.
- Added actual file-input document reading, domain-authorized IDs, new-document preparation under
  the shared registry lock, exact-question caches and conservative uncertain-upload recovery.
  Failed prepared documents are not automatically retried; other research continues.
- Persist final Markdown and receipts immediately; same-thread checkpoint recovery, cancellation,
  independent publication, safe progress/usage logs and final-publication replay remain operational.
- Notebook/CLI/PowerShell offer new full, linked research-only, explicit resume and upload-only
  actions. Layer 2 and the disabled Layer 4 cell retain their code/controls and saved outputs.
  Layer 4's historical harness and compactor were not changed.
- Development alone gained a dedicated checkpoint volume outside `/app`. Docker was found at
  the user's per-user installation, not PATH. Its existing kernel answered an idle diagnostic
  before development was rebuilt/recreated; the browser container was not restarted.

**Verification**

Completed 2026-09-11, offline only:

- Full Docker suite: **197 tests passed in 194.281 seconds**. Actual installed graph/tool/checkpoint
  behavior was exercised with fake model transport and blocked network calls. Earlier Windows
  checkpoint: 192 tests passed before the final recovery/control additions; it is not the final count.
- Tests cover multiple tool turns, seven-domain concurrency capped at five, native todos/notes,
  exact output publication, zero-source scheduling, parent preservation, explicit action conflicts,
  cancellation, same-thread recovery, missing-checkpoint refusal and response-receipt replay.
- Forced compaction retained early evidence and complete tool-message groups; native file permissions
  blocked cross-domain/host access and evidence writes. Complete assembled input checks were exercised.
- Installed SDK HTTP fakes verify actual file inputs, no search JSON-mode binding, URL/hash upload
  deduplication, registered-ID authorization, uncertain acceptance and cached response recovery.
  A replay bug uncovered by these tests was fixed: SDK responses use the same permissive decoding
  on replay as on initial receipt, not an added strict provider-envelope validator.
- Three focused notebook/CLI control tests passed after final PowerShell wiring. Notebook JSON and
  all three code cells compile; production function docstrings and the 350-line file limit pass.
- Docker compilation (`ML tests docker`), `pip check`, Compose quiet validation, PowerShell parsing
  and `git diff --check` pass. No Python dependency upgrades were introduced.
- Linux `/usr/local/bin/python`, Deep Agents 0.7.7, mounted checkpoint storage and SQLite preflight
  verified. A disposable SQLite record written in development was read from a fresh network-isolated
  container using the same volume, then only that fixture was removed.
- Browser container ID remained `87df437773eb1ecf856430cdab11832f560409d82e427db6c7176257d24bec18`,
  with unchanged start time `2026-09-11T04:06:31.152392899Z`. Reports and historical runs were not executed.

**Remaining user action / limits:** VS Code may need to reconnect to the recreated development service,
reload the saved notebook and select a fresh Docker kernel. Unsaved editor buffers must be preserved;
the notebook UI itself was not automatically reloaded. No live search, upload, research run or paid
comparison was performed. Offline passing tests establish orchestration and preservation, not real
responsibility coverage, citation correctness, extraction quality or guaranteed document readability.
